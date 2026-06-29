import random
import subprocess
import time

COUNTRIES = [
    "dz", "bh", "km", "eg", "iq",
    "jo", "kw", "lb", "ly", "mr",
    "ma", "qa", "so", "tn", "ae",
    "ye",
]

MAX_RETRIES = 5


def fix_dns():
    pass


def _connect(country):
    print(f"[VPN] Connecting to NordVPN — {country} ...")
    result = subprocess.run(
        ["nordvpn", "c", country],
        capture_output=True, text=True, timeout=30,
    )
    output = (result.stdout + result.stderr).strip()
    time.sleep(3)
    if "You are connected" in output:
        print(f"[VPN] Connected via {country}")
        fix_dns()
        return True
    not_connected_lines = [
        line for line in output.split("\n")
        if "A new version of NordVPN" not in line and line.strip()
    ]
    if not_connected_lines:
        print(f"[VPN] Not connected — {not_connected_lines[-1]}")
    else:
        print(f"[VPN] Not connected, retrying...")
    return False


def connect_random():
    tried = set()
    for attempt in range(MAX_RETRIES):
        available = [c for c in COUNTRIES if c not in tried]
        if not available:
            print("[VPN] All countries exhausted")
            return False
        country = random.choice(available)
        tried.add(country)
        if _connect(country):
            return True
    print("[VPN] Failed to connect after all retries")
    return False


def connect_country(country):
    country = country.lower()
    if country not in COUNTRIES:
        print(f"[VPN] Unknown country '{country}', falling back to random")
        return connect_random()
    for attempt in range(MAX_RETRIES):
        if _connect(country):
            return True
        print(f"[VPN] Retrying {country} ({attempt+2}/{MAX_RETRIES})...")
    print(f"[VPN] Failed to connect to {country} after all retries")
    return False


def disconnect():
    subprocess.run(["nordvpn", "d"], capture_output=True, timeout=30)


def is_connected():
    result = subprocess.run(["nordvpn", "status"], capture_output=True, text=True, timeout=10)
    return "Connected" in result.stdout
