import json
import re
import zipfile
from pathlib import Path

import requests

from camoufox.pkgman import INSTALL_DIR

# Fetch latest release info
headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
resp = requests.get(
    "https://api.github.com/repos/daijro/camoufox/releases/latest",
    headers=headers,
    timeout=30,
)
resp.raise_for_status()
data = resp.json()

# Find the Linux x86_64 asset
for asset in data["assets"]:
    if "lin.x86_64" in asset["name"]:
        url = asset["browser_download_url"]
        name = asset["name"]
        break
else:
    raise RuntimeError("No Linux x86_64 asset found")

# Parse version from filename
m = re.match(r"camoufox-(.+?)-(.+?)-lin\.x86_64\.zip", name)
version, release = m.group(1), m.group(2)

# Download
print(f"Downloading Camoufox {version}-{release} ({name})...")
r = requests.get(url, headers=headers, timeout=300, stream=True)
r.raise_for_status()

# Extract
INSTALL_DIR.mkdir(parents=True, exist_ok=True)
zip_path = Path("/tmp/camoufox.zip")
with open(zip_path, "wb") as f:
    for chunk in r.iter_content(chunk_size=8192):
        f.write(chunk)

with zipfile.ZipFile(zip_path) as zf:
    zf.extractall(str(INSTALL_DIR))

zip_path.unlink()

# Write version
(INSTALL_DIR / "version.json").write_text(
    json.dumps({"version": version, "release": release})
)

print(f"Camoufox installed at {INSTALL_DIR}")
