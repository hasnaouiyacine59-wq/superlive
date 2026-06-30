import os, shutil
from pathlib import Path
import requests
from camoufox.locale import MMDB_FILE

CACHE = Path('/cache/geoip/GeoLite2-City.v2.mmdb')
if CACHE.exists():
    print('GeoIP cache hit')
else:
    headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0'}
    token = os.environ.get('GITHUB_TOKEN')
    if token:
        headers['Authorization'] = f'Bearer {token}'
    r = requests.get('https://api.github.com/repos/P3TERX/GeoLite.mmdb/releases/latest', headers=headers, timeout=30)
    r.raise_for_status()
    url = next((a['browser_download_url'] for a in r.json()['assets'] if 'GeoLite2-City' in a['name']), None)
    if not url:
        raise RuntimeError('GeoLite2-City asset not found in release')
    print('Downloading GeoIP database...')
    r = requests.get(url, headers=headers, timeout=120, stream=True)
    r.raise_for_status()
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE, 'wb') as f:
        for chunk in r.iter_content(8192): f.write(chunk)

if not MMDB_FILE.exists():
    shutil.copy2(CACHE, MMDB_FILE)
    print('GeoIP ready')
else:
    print('GeoIP already installed')
