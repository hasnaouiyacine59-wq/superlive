import os
import random
import subprocess
import time
from pathlib import Path

COUNTRIES = [
    "ad", "ae", "al", "am", "ar", "at", "au", "az",
    "ba", "bd", "be", "bg", "bm", "bn", "bo", "br",
    "bs", "bt", "bz", "ca", "ch", "cl", "co", "cr",
    "cy", "cz", "de", "dk", "do", "dz", "ec", "ee",
    "eg", "es", "fi", "fr", "ge", "gh", "gr", "gt",
    "hk", "hn", "hr", "ht", "hu", "id", "ie", "il",
    "im", "in", "is", "it", "je", "jm", "jo", "jp",
    "ke", "kh", "kr", "ky", "kz", "la", "lb", "li",
    "lk", "lt", "lu", "lv", "ma", "mc", "md", "me",
    "mk", "mm", "mn", "mo", "mt", "mx", "my", "ng",
    "ni", "nl", "no", "np", "nz", "pa", "pe", "pg",
    "ph", "pk", "pl", "pr", "pt", "py", "ro", "rs",
    "sa", "se", "sg", "si", "sk", "th", "tr", "tt",
    "tw", "ua", "uk", "us", "uy", "ve", "vn", "za",
]

MAX_RETRIES = 5

UDP_DIR = Path(__file__).parent / "Fast_vpn" / "udp_files"
AUTH_FILE = Path(__file__).parent / "Fast_vpn" / "fast_auth"
LOG_FILE = "/tmp/fvpn.log"

_openvpn_pid = None


def _get_ovpn_configs():
    if not UDP_DIR.is_dir():
        print(f"[VPN] Directory not found: {UDP_DIR}")
        return []
    return sorted(UDP_DIR.glob("*.ovpn"))


def _extract_country(filename):
    name = filename.stem
    parts = name.split("-", 2)
    return parts[1].lower() if len(parts) >= 2 else None


def _filter_configs(country_code):
    configs = _get_ovpn_configs()
    country_code = country_code.lower()
    matched = [c for c in configs if _extract_country(c) == country_code]
    return matched


def disconnect():
    global _openvpn_pid
    if _openvpn_pid is not None:
        try:
            os.kill(_openvpn_pid, 15)
            for _ in range(10):
                try:
                    os.kill(_openvpn_pid, 0)
                    time.sleep(0.5)
                except OSError:
                    break
        except (OSError, ProcessLookupError):
            pass
        _openvpn_pid = None
    subprocess.run(["pkill", "-f", "openvpn.*fvpn"], capture_output=True, timeout=5)
    time.sleep(1)


def _connect(config_path):
    global _openvpn_pid
    disconnect()

    if not AUTH_FILE.is_file():
        print(f"[VPN] Credential file not found: {AUTH_FILE}")
        print("[VPN] Create it with: echo 'username' > Fast_vpn/fast_auth; echo 'password' >> Fast_vpn/fast_auth; chmod 600 Fast_vpn/fast_auth")
        return False

    # Truncate log
    try:
        open(LOG_FILE, "w").close()
    except OSError:
        pass

    print(f"[VPN] Starting OpenVPN: {config_path.name} ...")
    try:
        proc = subprocess.Popen(
            [
                "openvpn",
                "--config", str(config_path),
                "--auth-user-pass", str(AUTH_FILE),
                "--log", LOG_FILE,
                "--daemon",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        print("[VPN] ERROR: openvpn not found. Install it or check PATH.")
        return False

    proc.communicate(timeout=5)

    # Poll log for "Initialization Sequence Complete"
    deadline = time.time() + 60
    last_size = 0
    while time.time() < deadline:
        time.sleep(2)
        try:
            with open(LOG_FILE) as f:
                content = f.read()
            if len(content) > last_size:
                last_size = len(content)
            if "Initialization Sequence Complete" in content:
                print(f"[VPN] Connected via {config_path.name}")
                # Find the openvpn PID
                result = subprocess.run(
                    ["pgrep", "-f", "openvpn.*fvpn"],
                    capture_output=True, text=True, timeout=5,
                )
                if result.stdout.strip():
                    _openvpn_pid = int(result.stdout.strip().split("\n")[0])
                return True
            if "ERROR" in content or "Fatal" in content:
                print(f"[VPN] OpenVPN error in log:\n{content.strip()}")
                return False
        except OSError:
            pass

    # Timed out — check log for diagnostics
    try:
        with open(LOG_FILE) as f:
            print(f"[VPN] Timed out. Log:\n{f.read().strip()}")
    except OSError:
        print("[VPN] Timed out. No log file.")
    return False


def connect_random():
    configs = _get_ovpn_configs()
    mena_configs = [c for c in configs if _extract_country(c) in COUNTRIES]
    if not mena_configs:
        print("[VPN] No MENA region configs found in udp_files/")
        return False
    tried = set()
    for attempt in range(MAX_RETRIES):
        available = [c for c in mena_configs if c not in tried]
        if not available:
            print("[VPN] All configs exhausted")
            return False
        config = random.choice(available)
        tried.add(config)
        if _connect(config):
            return True
    print("[VPN] Failed to connect after all retries")
    return False


def connect_country(country):
    country = country.lower()
    configs = _filter_configs(country)
    if not configs:
        print(f"[VPN] No config for country '{country}', falling back to random")
        return connect_random()
    random.shuffle(configs)
    for attempt in range(MAX_RETRIES):
        config = configs[attempt % len(configs)]
        if _connect(config):
            return True
        print(f"[VPN] Retrying {country} ({attempt+2}/{MAX_RETRIES})...")
    print(f"[VPN] Failed to connect to {country} after all retries")
    return False


def is_connected():
    if _openvpn_pid is None:
        return False
    try:
        os.kill(_openvpn_pid, 0)
        return True
    except OSError:
        return False
