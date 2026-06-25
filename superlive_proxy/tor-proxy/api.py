from flask import Flask, jsonify
import socket, requests, os, time, threading, logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = Flask(__name__)

SOCKS_PORT   = int(os.environ.get("SOCKS_PORT",   9050))
CONTROL_PORT = int(os.environ.get("CONTROL_PORT", 9051))
API_PORT     = int(os.environ.get("API_PORT",     5000))

def tor_cmd(cmd: bytes) -> tuple:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            s.connect(("127.0.0.1", CONTROL_PORT))
            s.sendall(b'AUTHENTICATE ""\r\n')
            s.recv(1024)
            s.sendall(cmd)
            resp = s.recv(4096).decode()
            return "250" in resp, resp.strip()
    except Exception as e:
        return False, str(e)

def _new_circuit():
    tor_cmd(b"SIGNAL NEWNYM\r\n")

def _keepalive():
    """Keep Tor warm by making a request every 60s to prevent idle circuit loss."""
    proxies = {
        "http":  f"socks5h://127.0.0.1:{SOCKS_PORT}",
        "https": f"socks5h://127.0.0.1:{SOCKS_PORT}",
    }
    while True:
        time.sleep(60)
        try:
            requests.get("https://api.ipify.org", proxies=proxies, timeout=15)
            logging.info("keepalive ok")
        except Exception as e:
            logging.warning("keepalive failed: %s", e)

# start background threads
threading.Thread(target=_keepalive, daemon=True).start()

IP_SERVICES = [
    "https://api.ipify.org",
    "https://icanhazip.com",
    "https://ifconfig.me/ip",
    "https://ipecho.net/plain",
    "https://checkip.amazonaws.com",
]

def _wait_for_circuit(timeout=10):
    """Poll bootstrap status instead of fixed sleep."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        ok, detail = tor_cmd(b"GETINFO status/bootstrap-phase\r\n")
        if ok and "PROGRESS=100" in detail:
            return True
        time.sleep(0.5)
    return False

def _get_ip_via_tor():
    proxies = {
        "http":  f"socks5h://127.0.0.1:{SOCKS_PORT}",
        "https": f"socks5h://127.0.0.1:{SOCKS_PORT}",
    }
    # try all services in parallel, return first success
    from concurrent.futures import ThreadPoolExecutor, as_completed
    def fetch(url):
        return requests.get(url, proxies=proxies, timeout=30).text.strip()
    with ThreadPoolExecutor(max_workers=len(IP_SERVICES)) as ex:
        futures = {ex.submit(fetch, url): url for url in IP_SERVICES}
        for f in as_completed(futures):
            try:
                return f.result()
            except Exception as e:
                logging.warning("IP service %s failed: %s", futures[f], e)
    raise RuntimeError("all IP services failed")

@app.route("/reset-ip")
def reset_ip():
    old_ip = None
    try:
        old_ip = _get_ip_via_tor()
    except Exception:
        pass
    _new_circuit()
    _wait_for_circuit(timeout=15)
    # wait until IP actually changes (up to 30s)
    deadline = time.time() + 30
    new_ip = old_ip
    while time.time() < deadline:
        try:
            new_ip = _get_ip_via_tor()
            if new_ip != old_ip:
                break
        except Exception:
            pass
        time.sleep(2)
    return jsonify({"status": "ok", "old_ip": old_ip, "new_ip": new_ip})

@app.route("/ip")
def get_ip():
    try:
        return jsonify({"ip": _get_ip_via_tor()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/ip/<country>")
def get_ip_from_country(country):
    try:
        node = "{" + country.lower() + "}"
        ok, resp = tor_cmd(f"SETCONF ExitNodes={node} StrictNodes=1\r\n".encode())
        if not ok:
            return jsonify({"error": "failed to set exit country", "detail": resp}), 500
        # retry up to 3 circuits
        for attempt in range(3):
            _new_circuit()
            _wait_for_circuit()
            try:
                ip = _get_ip_via_tor()
                return jsonify({"ip": ip, "country": country.lower()})
            except Exception:
                if attempt == 2:
                    raise
        return jsonify({"error": "no exit node found"}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def _fingerprint_for_ip(target_ip: str) -> str | None:
    """Query Tor consensus to find relay fingerprint by exit IP."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            s.connect(("127.0.0.1", CONTROL_PORT))
            s.sendall(b'AUTHENTICATE ""\r\n')
            s.recv(1024)
            s.sendall(b"GETINFO ns/all\r\n")
            data = b""
            while True:
                chunk = s.recv(65536)
                data += chunk
                if b"250 OK" in data:
                    break
        # parse: each relay block has "r <name> <b64fp> ... <ip> ..."
        for line in data.decode(errors="ignore").splitlines():
            if line.startswith("r "):
                parts = line.split()
                ip = parts[6] if len(parts) > 6 else ""
                if ip == target_ip:
                    import base64
                    fp_bytes = base64.b64decode(parts[2] + "==")
                    return fp_bytes.hex().upper()
    except Exception as e:
        logging.warning("fingerprint lookup failed: %s", e)
    return None

@app.route("/set-exit-ip/<path:ip>")
def set_exit_ip(ip):
    """Set a specific exit node by its IP address."""
    fp = _fingerprint_for_ip(ip)
    if not fp:
        return jsonify({"error": f"no relay found for IP {ip}"}), 404
    ok, resp = tor_cmd(f"SETCONF ExitNodes={fp} StrictNodes=1\r\n".encode())
    if ok:
        _new_circuit()
    return jsonify({"status": "ok" if ok else "error", "fingerprint": fp, "ip": ip})
    ok, resp = tor_cmd(b"SETCONF ExitNodes= StrictNodes=0\r\n")
    return jsonify({"status": "ok" if ok else "error", "detail": resp})

excluded_countries = set()

@app.route("/exclude-country/<country>")
def exclude_country(country):
    excluded_countries.add(country.lower())
    nodes = ",".join("{" + c + "}" for c in excluded_countries)
    ok, resp = tor_cmd(f"SETCONF ExcludeExitNodes={nodes} StrictNodes=1\r\n".encode())
    if ok:
        _new_circuit()
    return jsonify({"status": "ok" if ok else "error", "excluded_countries": list(excluded_countries)})

@app.route("/exclude-country/<country>", methods=["DELETE"])
def unexclude_country(country):
    excluded_countries.discard(country.lower())
    nodes = ",".join("{" + c + "}" for c in excluded_countries) or ""
    strict = "1" if excluded_countries else "0"
    ok, resp = tor_cmd(f"SETCONF ExcludeExitNodes={nodes} StrictNodes={strict}\r\n".encode())
    if ok:
        _new_circuit()
    return jsonify({"status": "ok" if ok else "error", "excluded_countries": list(excluded_countries)})

@app.route("/status")
def status():
    ok, detail = tor_cmd(b"GETINFO status/bootstrap-phase\r\n")
    ready = "PROGRESS=100" in detail
    return jsonify({"bootstrapped": ready, "detail": detail})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=API_PORT)
