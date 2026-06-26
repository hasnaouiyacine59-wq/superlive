import random
import subprocess
import time

COUNTRIES = [
    "al", "ar", "am", "au", "at",
    "bs", "be", "ba", "br", "bg",
    "ca", "cl", "co", "cr", "hr",
    "cy", "cz", "dk", "do", "ec",
    "eg", "ee", "fi", "fr", "ge",
    "de", "gr", "hk", "hu", "is",
    "in", "id", "ie", "il", "it",
    "jp", "kz", "ke", "lv", "lt",
    "lu", "my", "mt", "mx", "md",
    "mc", "me", "nl", "nz", "ng",
    "mk", "no", "pk", "pa", "py",
    "pe", "ph", "pl", "pt", "ro",
    "rs", "sg", "sk", "si", "za",
    "kr", "es", "lk", "se", "ch",
    "tw", "th", "tr", "ug", "ua",
    "ae", "gb", "us", "uy", "vn",
    "zm",
]


def connect_random():
    country = random.choice(COUNTRIES)
    print(f"[VPN] Connecting to NordVPN — {country} ...")
    subprocess.run(["nordvpn", "c", country], capture_output=True, timeout=30)
    time.sleep(5)
    result = subprocess.run(["nordvpn", "status"], capture_output=True, text=True, timeout=10)
    if "Connected" in result.stdout:
        print(f"[VPN] Connected via {country}")
        return True
    print("[VPN] Not connected, retrying...")
    return False


def disconnect():
    subprocess.run(["nordvpn", "d"], capture_output=True, timeout=30)


def is_connected():
    result = subprocess.run(["nordvpn", "status"], capture_output=True, text=True, timeout=10)
    return "Connected" in result.stdout
