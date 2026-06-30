import json, re, shutil, zipfile
from pathlib import Path
import requests
from camoufox.pkgman import INSTALL_DIR

CACHE = Path('/cache/camoufox')
if (CACHE / 'version.json').exists():
    print('Camoufox cache hit')
else:
    headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'}
    r = requests.get('https://api.github.com/repos/daijro/camoufox/releases/latest', headers=headers, timeout=30)
    r.raise_for_status()
    for a in r.json()['assets']:
        if 'lin.x86_64' in a['name']:
            url, name = a['browser_download_url'], a['name']
            break
    m = re.match(r'camoufox-(.+?)-(.+?)-lin\.x86_64\.zip', name)
    ver, rel = m.group(1), m.group(2)
    print(f'Downloading Camoufox {ver}-{rel}...')
    r = requests.get(url, headers=headers, timeout=300, stream=True)
    r.raise_for_status()
    zp = Path('/tmp/cf.zip')
    with open(zp, 'wb') as f:
        for chunk in r.iter_content(8192): f.write(chunk)
    CACHE.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zp) as zf: zf.extractall(str(CACHE))
    (CACHE / 'version.json').write_text(json.dumps({'version': ver, 'release': rel}))
    zp.unlink()

if not INSTALL_DIR.exists() or not any(INSTALL_DIR.iterdir()):
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    for item in CACHE.iterdir():
        dest = INSTALL_DIR / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)
    print('Camoufox ready')
else:
    print('Camoufox already installed')
