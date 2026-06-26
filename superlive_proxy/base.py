import argparse
import json
import os
import random
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import cv2
import requests
import speech_recognition as sr
from pydub import AudioSegment

from camoufox import Camoufox
from camoufox.utils import launch_options
from super_email import get_2fa
import vpn

parser = argparse.ArgumentParser()
parser.add_argument("-p", "--proxy", action="store_true", help="Route traffic through Tor SOCKS5 proxy on localhost:9050")
parser.add_argument("-s", "--static-proxy", type=str, metavar="FILE", help="Use a random HTTP proxy from a file (format: user:pass@host:port per line)")
parser.add_argument("-n", "--nordvpn", action="store_true", help="Enable NordVPN cycling between sessions")
args = parser.parse_args()

PROXY_HOST = os.environ.get("PROXY_HOST", "localhost")
PROXY_PORT = int(os.environ.get("PROXY_PORT", "9050"))
API_HOST = os.environ.get("API_HOST", "127.0.0.1")
API_PORT = int(os.environ.get("API_PORT", "5000"))
PROXY_SOCKS = f"socks5://{PROXY_HOST}:{PROXY_PORT}"
PROXY_SOCKS5H = f"socks5h://{PROXY_HOST}:{PROXY_PORT}"
use_proxy = args.proxy

session = requests.Session()

# Load static proxy list
static_proxies = []
selected_proxy = None
if args.static_proxy:
    with open(args.static_proxy) as f:
        for line in f:
            line = line.strip()
            if line and "@" in line:
                userpass, hostport = line.split("@", 1)
                username, password = userpass.split(":", 1)
                host, port = hostport.rsplit(":", 1)
                static_proxies.append((host, int(port), username, password))
    if static_proxies:
        selected_proxy = random.choice(static_proxies)
        host, port, user, pw = selected_proxy
        print(f"  [*] Using proxy: {user}:****@{host}:{port}")
        session.proxies.update({"http": f"http://{user}:{pw}@{host}:{port}", "https": f"http://{user}:{pw}@{host}:{port}"})
        use_proxy = True

if use_proxy and not static_proxies:
    session.proxies.update({"http": PROXY_SOCKS5H, "https": PROXY_SOCKS5H})

result_dir = Path("results")
if result_dir.exists():
    shutil.rmtree(result_dir)
result_dir.mkdir(parents=True, exist_ok=True)

DOMAINS = [
    "alpha804.eu.org", "alpha-sig.eu.org", "beta-sig.eu.org",
    "bitcoin-plazza.eu.org", "c0rner-bit.eu.org", "dark0s-market.eu.org",
    "iblogg.eu.org", "lg-salmi.nl.eu.org",
    "sec4891.eu.org", "techstreet07.eu.org",
    "vaya.eu.org",
]


def random_username():
    adjectives = ["cool", "fast", "mega", "neo", "super", "ultra", "hyper", "epic", "omega", "alpha",
                  "dark", "shadow", "storm", "thunder", "blaze", "frost", "crystal", "phantom", "cyber", "nova"]
    nouns = ["wolf", "tiger", "eagle", "panda", "dragon", "hawk", "lion", "fox", "shark", "phoenix",
             "raider", "ninja", "pilot", "rider", "hunter", "knight", "ghost", "viper", "runner", "storm"]
    adj = random.choice(adjectives)
    noun = random.choice(nouns)
    num = random.randint(10, 9999)
    return f"{adj}{noun}{num}"


def generate_credentials():
    domain = random.choice(DOMAINS)
    username = random_username()
    password = username + "!Aa1"
    email = f"{username}@{domain}"
    return username, email, password


proxy_opts = {}
firefox_user_prefs = {}
if selected_proxy:
    h, p, u, pw = selected_proxy
    proxy_opts = {"proxy": {"server": f"http://{h}:{p}", "username": u, "password": pw}}
    firefox_user_prefs = {
        "network.trr.mode": 3,
        "network.trr.uri": "https://cloudflare-dns.com/dns-query",
        "network.trr.bootstrapAddress": "1.1.1.1",
    }
elif use_proxy:
    proxy_opts = {"proxy": {"server": PROXY_SOCKS}}
headless_env = os.environ.get("HEADLESS", "false").lower()
if headless_env == "virtual":
    headless_mode = "virtual"
elif headless_env in ("true", "1"):
    headless_mode = True
else:
    headless_mode = False
opts = launch_options(
    geoip=True, humanize=0.3, block_webrtc=True,
    block_images=False, disable_coop=True,
    main_world_eval=True, window=(1280, 720), debug=True,
    headless=headless_mode,
    firefox_user_prefs=firefox_user_prefs,
    **proxy_opts,
)


def click_text(page, text_fragment):
    clicked = page.evaluate("""(frag) => {
        const all = document.querySelectorAll('button, a, [role="button"], input[type="submit"]');
        for (const el of all) {
            if (el.textContent.toLowerCase().includes(frag.toLowerCase())) {
                el.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
                return el.outerHTML.slice(0, 150);
            }
        }
        return null;
    }""", text_fragment)
    if clicked:
        print(f"  [*] Clicked element containing '{text_fragment}': {clicked}")
    else:
        print(f"  [!] No element with text '{text_fragment}' found")
    page.wait_for_timeout(500)
    return bool(clicked)


def dump_full_html(page, prefix="step1"):
    html = page.evaluate("() => document.documentElement.outerHTML")
    path = result_dir / f"{prefix}_superlive_full.html"
    path.write_text(html, encoding="utf-8")
    print(f"  [*] {prefix}: Full HTML saved ({len(html)} chars)")


def dump_visible_elements(page, prefix="step1"):
    elements = page.evaluate("""() => {
        const all = document.querySelectorAll('*');
        const seen = new Set();
        const result = [];
        for (const el of all) {
            const tag = el.tagName.toLowerCase();
            const rect = el.getBoundingClientRect();
            const visible = rect.width > 0 && rect.height > 0;
            const text = (el.textContent || '').trim().slice(0, 120);
            const id = el.id;
            const cls = el.className;
            const key = tag + id + cls;
            if (seen.has(key) || !visible) continue;
            seen.add(key);
            result.push({
                tag, id, class: cls,
                text: text.slice(0, 80),
                rect: {x: ~~rect.x, y: ~~rect.y, w: ~~rect.width, h: ~~rect.height},
                childCount: el.children.length,
            });
        }
        return result;
    }""")
    path = result_dir / f"{prefix}_superlive_elements.json"
    path.write_text(json.dumps(elements, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  [*] {prefix}: Visible elements saved ({len(elements)} items)")


def dump_clickable(page, prefix="step1"):
    clickables = page.evaluate("""() => {
        const all = document.querySelectorAll('button, a, [role="button"], input, select, textarea, [onclick]');
        return Array.from(all).map(el => ({
            tag: el.tagName.toLowerCase(),
            id: el.id,
            class: el.className.slice(0, 80),
            text: (el.textContent || '').trim().slice(0, 100),
            href: (el.href || '').slice(0, 120),
            type: el.type || '',
            name: el.name || '',
            placeholder: el.placeholder || '',
            rect: el.getBoundingClientRect(),
        }));
    }""")
    path = result_dir / f"{prefix}_superlive_clickables.json"
    path.write_text(json.dumps(clickables, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  [*] {prefix}: Clickable elements saved ({len(clickables)} items)")


def dump_iframes(page, prefix="step1"):
    iframes = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('iframe')).map(f => ({
            src: (f.src || '').slice(0, 200),
            id: f.id,
            name: f.name,
            title: f.title,
            width: f.width,
            height: f.height,
            visible: f.offsetWidth > 0 && f.offsetHeight > 0,
        }));
    }""")
    path = result_dir / f"{prefix}_superlive_iframes.json"
    path.write_text(json.dumps(iframes, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  [*] {prefix}: Iframes saved ({len(iframes)} items)")


def dump_scripts(page, prefix="step1"):
    scripts = page.evaluate("""() => {
        return Array.from(document.scripts).map(s => ({
            src: (s.src || '').slice(0, 200),
            id: s.id,
            type: s.type || 'text/javascript',
            async: s.async,
            defer: s.defer,
            textLength: (s.textContent || '').length,
        }));
    }""")
    path = result_dir / f"{prefix}_superlive_scripts.json"
    path.write_text(json.dumps(scripts, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  [*] {prefix}: Scripts saved ({len(scripts)} items)")


def dump_forms(page, prefix="step1"):
    forms = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('form')).map(f => ({
            id: f.id,
            name: f.name,
            action: (f.action || '').slice(0, 150),
            method: f.method,
            inputs: Array.from(f.querySelectorAll('input, select, textarea')).map(i => ({
                type: i.type || 'text', name: i.name, id: i.id,
                placeholder: i.placeholder, required: i.required,
            })),
        }));
    }""")
    path = result_dir / f"{prefix}_superlive_forms.json"
    path.write_text(json.dumps(forms, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  [*] {prefix}: Forms saved ({len(forms)} items)")


def find_and_click(page, label, keywords, dump_prefix=None):
    print(f"  [*] Looking for {label}...")
    result = page.evaluate(f"""() => {{
        const all = document.querySelectorAll('button, a, [role="button"]');
        const keywords = {keywords};
        for (const el of all) {{
            const text = el.textContent.toLowerCase().trim();
            const aria = (el.getAttribute('aria-label') || '').toLowerCase();
            const testid = (el.getAttribute('data-testid') || '').toLowerCase();
            const href = (el.getAttribute('href') || '').toLowerCase();
            const cls = el.className.toLowerCase();
            for (const kw of keywords) {{
                if (text.includes(kw) || aria.includes(kw) || testid.includes(kw) || href.includes(kw) || cls.includes(kw)) {{
                    el.removeAttribute('disabled');
                    el.dispatchEvent(new MouseEvent('click', {{bubbles: true, cancelable: true}}));
                    return el.outerHTML.slice(0, 200);
                }}
            }}
        }}
        return null;
    }}""")
    if result:
        print(f"  [*] Clicked {label}: {result}")
        page.wait_for_timeout(300)
        return True
    print(f"  [!] {label} not found")
    if dump_prefix:
        dump_all(page, dump_prefix)
    return False


def click_selector(page, selector, index=0):
    try:
        el = page.locator(selector).nth(index)
        if el.count() > index:
            el.click()
            print(f"  [*] Clicked selector '{selector}' [{index}]")
            page.wait_for_timeout(300)
            return True
    except Exception as e:
        print(f"  [!] Selector '{selector}' [{index}] failed: {e}")
    return False


def fill_input(page, sel, value):
    for attempt in range(3):
        try:
            el = page.wait_for_selector(sel, timeout=3000)
            if el:
                el.fill(value)
                print(f"  [*] Filled {sel} with '{value}'")
                page.wait_for_timeout(300)
                return True
        except Exception:
            pass
        page.wait_for_timeout(500)
    try:
        filled = page.evaluate(f"""(s, v) => {{
            const el = document.querySelector(s);
            if (el) {{ el.value = v; el.dispatchEvent(new Event('input', {{bubbles: true}})); return true; }}
            return false;
        }}""", sel, value)
        if filled:
            print(f"  [*] JS-filled {sel}")
            return True
    except Exception:
        pass
    print(f"  [!] Could not fill {sel}")
    return False


def fill_field(page, value, selectors, dump_prefix=None):
    for sel in selectors:
        if fill_input(page, sel, value):
            return True
    if dump_prefix:
        dump_all(page, dump_prefix)
        screen = identify_screen(page)
        print(f"  [*] Screen after fill failure: {screen}")
    return False


def wait_until_next_step(page, old_check, new_check, timeout=8):
    import time
    deadline = time.time() + timeout
    while time.time() < deadline:
        old_gone = not old_check(page) if old_check else True
        new_arrived = new_check(page) if new_check else False
        if old_gone or new_arrived:
            return True
        page.wait_for_timeout(1000)
    return False


def dump_all(page, prefix):
    dump_full_html(page, prefix)
    dump_visible_elements(page, prefix)
    dump_clickable(page, prefix)
    dump_iframes(page, prefix)
    dump_scripts(page, prefix)
    dump_forms(page, prefix)


def identify_screen(page):
    screens = [
        ("otp", """() => {
            return !!document.querySelector('#otp-code-0, input[autocomplete="one-time-code"]');
        }"""),
        ("reg_form", """() => {
            return !!document.querySelector('#password') && document.querySelector('#password').offsetHeight > 0;
        }"""),
        ("email_input", """() => {
            return !!document.querySelector('#otp-email, #email') && document.querySelector('#otp-email, #email').offsetHeight > 0;
        }"""),
        ("register_vs_login", """() => {
            const all = document.querySelectorAll('button');
            const has_register = [...all].some(b => b.textContent.toLowerCase().includes("s'enregistrer avec") && b.offsetHeight > 0);
            const has_login = [...all].some(b => b.textContent.toLowerCase().includes('connectez-vous avec') && b.offsetHeight > 0);
            return has_register && has_login;
        }"""),
        ("gender", """() => {
            const h3 = document.querySelector('h3');
            if (!h3 || !h3.textContent.includes('Genre')) return false;
            const btns = document.querySelectorAll('button');
            return [...btns].some(b => b.textContent.trim() === 'Homme' && b.offsetHeight > 0);
        }"""),
        ("provider_picker", """() => {
            const btns = document.querySelectorAll('button[class*="border-unique-label-100"]');
            if (btns.length === 0) return false;
            return [...btns].some(b => b.offsetHeight > 0 && (
                b.textContent.toLowerCase().includes('poursuivre') ||
                b.textContent.toLowerCase().includes('continue with') ||
                b.textContent.toLowerCase().includes('avec email') ||
                b.textContent.toLowerCase().includes('avec google')
            ));
        }"""),
        ("captcha", """() => {
            const bframe = document.querySelector('iframe[src*="recaptcha/enterprise/bframe"], iframe[src*="recaptcha/api2/bframe"]');
            if (!bframe) return false;
            const r = bframe.getBoundingClientRect();
            if (r.width === 0 || r.height === 0) return false;
            for (let el = bframe; el; el = el.parentElement) {
                const s = window.getComputedStyle(el);
                if (s.display === 'none' || s.visibility === 'hidden') return false;
            }
            return true;
        }"""),
        ("stream", """() => {
            return !!document.querySelector('[id^="video-container-"], .swiper-slide-active video, textarea[placeholder="Chat"]');
        }"""),
        ("messages", """() => {
            const hasMessagesNav = [...document.querySelectorAll('a')].some(a => a.textContent.trim() === 'Messages' && a.offsetHeight > 0);
            const hasCenter = [...document.querySelectorAll('h4')].some(h => h.textContent.includes('Commencer la discussion') && h.offsetHeight > 0);
            const hasInbox = !!document.querySelector('.spl-user-name');
            return (hasMessagesNav && hasInbox) || hasCenter;
        }"""),
        ("loading", """() => {
            return !!document.querySelector('.animate-spin, .animate-pulse, [class*="animate-spin"], [class*="animate-pulse"]');
        }"""),
        ("home", """() => {
            const btns = document.querySelectorAll('button');
            const has_inscrire = [...btns].some(b => b.textContent.trim() === "S'inscrire" && b.offsetHeight > 0);
            const has_connecter = [...btns].some(b => b.textContent.trim() === 'Se connecter' && b.offsetHeight > 0);
            return has_inscrire && has_connecter;
        }"""),
        ("profile", r"""() => {
            const hasProfileImg = !!document.querySelector('img[alt="Nom d\'utilisateur"]');
            const hasButtons = [...document.querySelectorAll('button')].some(
                b => b.textContent.includes('APPELS PRIVES') || b.textContent.includes('Message')
            );
            return hasProfileImg && hasButtons;
        }"""),
    ]
    for name, js in screens:
        if page.evaluate(js):
            return name
    return None


def print_form_title(page):
    title = page.evaluate("""() => {
        const h = document.querySelector('h1, h2, h3, h4, h5');
        if (h) return h.textContent.trim().slice(0, 80);
        const titleEl = document.querySelector('[class*="title"], [class*="heading"], .modal-header');
        if (titleEl) return titleEl.textContent.trim().slice(0, 80);
        const p = document.querySelector('.text-lg.font-medium, .text-center.text-lg');
        if (p) return p.textContent.trim().slice(0, 80);
        return null;
    }""")
    if title:
        print(f"  [*] Form title: {title}")
    forms = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('form')).map(f => ({
            id: f.id,
            inputs: Array.from(f.querySelectorAll('input')).map(i => i.name || i.id || i.type).join(', '),
        }));
    }""")
    for f in forms:
        print(f"  [*] Form: id='{f['id']}' inputs=[{f['inputs']}]")


def navigate_and_click_profile(page):
    print(f"  [*] Messages page — navigating to target profile")
    time.sleep(5)
    try:
        page.goto("https://superlive.chat/fr/profile/49194780", wait_until="load", timeout=60000)
        page.wait_for_load_state("networkidle", timeout=30000)
        page.wait_for_timeout(3000)
        print(f"  [*] Clicking profile image")
        img = page.locator('img[alt="Nom d\'utilisateur"]')
        if img.count() > 0:
            img.first.click()
            print(f"  [*] Clicked profile image")
            page.wait_for_timeout(2000)
            dump_all(page, "after_profile_click")
        else:
            print(f"  [!] Profile image not found")
    except Exception as e:
        print(f"  [!] Profile navigation failed: {e}")


def do_profile_action(page):
    time.sleep(3)
    print(f"  [*] Clicking profile image")
    img = page.locator('img[alt="Nom d\'utilisateur"]')
    if img.count() > 0:
        img.first.click()
        print(f"  [*] Clicked profile image")
        page.wait_for_timeout(2000)
        dump_all(page, "after_profile_click")
    else:
        print(f"  [!] Profile image not found")


SCREEN_ACTIONS = {
    "home": lambda p: click_text(p, "S'inscrire"),
    "provider_picker": lambda p: click_text(p, "Poursuivre avec Email"),
    "register_vs_login": lambda p: find_and_click(p, "register with email", [
        "s'enregistrer avec l'adresse e-mail",
        "s'enregistrer avec",
        "enregistrer avec l'adresse e-mail"
    ]),
    "email_input": lambda p: (
        fill_field(p, email, ["#otp-email", "#email", "input[name='email']", "input[type='email']"], dump_prefix="email_fill_fail"),
        p.wait_for_timeout(500),
        find_and_click(p, "Continuer", ["continuer", "continue", "suivant", "next", "إرسال", "submit"]),
    ),
    "reg_form": lambda p: fill_reg_form(p, email, password),
    "otp": lambda p: fill_otp(p, email),
    "loading": lambda p: p.wait_for_timeout(3000),
    "gender": lambda p: (
        find_and_click(p, "Homme", ["homme"]),
        p.wait_for_timeout(1000),
        find_and_click(p, "Confirmer", ["confirmer", "confirm"], dump_prefix="confirmer_fail"),
    ),
    "profile": lambda p: do_profile_action(p),
    "stream": lambda p: (
        print("  [*] Stream page reached — clicking first/second images"),
        p.wait_for_timeout(2000),
        click_image_match(p, os.path.join(os.path.dirname(__file__), "src", "first.png"), "first", threshold=0.7) and (
            p.wait_for_timeout(2000),
            click_image_match(p, os.path.join(os.path.dirname(__file__), "src", "second.png"), "second", threshold=0.7),
        ),
    ),
    "messages": lambda p: navigate_and_click_profile(p),
}


def wait_for_captcha(page, timeout=45):
    cap_path = os.path.join(os.path.dirname(__file__), "src", "cap.png")
    poll_start = time.time()
    image_check_interval = 0
    while time.time() - poll_start < timeout:
        try:
            has_bframe = page.evaluate("""() => {
                return !!document.querySelector('iframe[src*="recaptcha/enterprise/bframe"], iframe[src*="recaptcha/api2/bframe"]');
            }""")
            if has_bframe:
                print(f"  [*] Captcha detected via bframe after {time.time()-poll_start:.0f}s")
                return True
        except Exception:
            print(f"  [*] Page closed during captcha poll")
            return False
        image_check_interval += 1
        if image_check_interval % 10 == 0 and os.path.exists(cap_path):
            try:
                page.screenshot(path="/tmp/otp_after_verify.png")
                cap_ref = cv2.imread(cap_path, cv2.IMREAD_GRAYSCALE)
                shot = cv2.imread("/tmp/otp_after_verify.png", cv2.IMREAD_GRAYSCALE)
                if cap_ref is not None and shot is not None and shot.shape[0] >= cap_ref.shape[0] and shot.shape[1] >= cap_ref.shape[1]:
                    result = cv2.matchTemplate(shot, cap_ref, cv2.TM_CCOEFF_NORMED)
                    _, max_val, _, _ = cv2.minMaxLoc(result)
                    if max_val > 0.8:
                        print(f"  [*] Captcha detected via image match ({max_val:.2f}) after {time.time()-poll_start:.0f}s")
                        return True
            except Exception:
                pass
        page.wait_for_timeout(500)
    print(f"  [*] No captcha appeared within {timeout}s")
    return False


def fill_otp(page, email):
    print(f"  [*] Fetching OTP code from email...")
    for otp_fetch_attempt in range(5):
        code = get_2fa(email, retries=3, delay=4)
        if code:
            break
        print(f"  [!] No OTP code found (attempt {otp_fetch_attempt+1}/5) — exiting")
        sys.exit(1)
    print(f"  [*] Got OTP code: {code}")
    fields_filled = 0
    for i in range(6):
        try:
            el = page.wait_for_selector(f"#otp-code-{i}", timeout=1000)
            if el and i < len(code):
                el.fill(code[i])
                fields_filled += 1
        except Exception:
            pass
    if fields_filled > 0:
        print(f"  [*] Filled {fields_filled}/6 OTP digit fields")
        page.wait_for_timeout(500)
        verify_btn = page.query_selector("button:has-text('Verify'), button:has-text('Vérifier'), button[type='submit']")
        if verify_btn:
            verify_btn.click()
            print("  [*] Clicked verify button")
        try:
            page.wait_for_timeout(2000)
        except Exception:
            print(f"  [*] Page closed after verify click — OTP verification succeeded")
            return True
        if wait_for_captcha(page):
            solve_captcha(page)
        return True
    try:
        el = page.wait_for_selector(
            "input[autocomplete='one-time-code'], input[name*='otp' i], input[id*='otp' i]",
            timeout=2000,
        )
        if el:
            el.fill(code)
            print(f"  [*] Filled single OTP input")
            page.wait_for_timeout(500)
            if wait_for_captcha(page):
                solve_captcha(page)
                return True
            verify_btn = page.query_selector("button:has-text('Verify'), button:has-text('Vérifier'), button[type='submit']")
            if verify_btn:
                verify_btn.click()
                print("  [*] Clicked verify button")
            try:
                page.wait_for_timeout(2000)
            except Exception:
                print(f"  [*] Page closed after verify click — OTP verification succeeded")
                return True
            if wait_for_captcha(page):
                solve_captcha(page)
            return True
    except Exception:
        pass
    try:
        page.evaluate(f"""() => {{
            const inputs = document.querySelectorAll('input[type="text"], input:not([type])');
            for (const inp of inputs) {{
                if (inp.maxLength >= 6 || inp.placeholder.includes('code') || inp.placeholder.includes('رمز')) {{
                    inp.value = '{code}';
                    inp.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    inp.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    break;
                }}
            }}
        }}""")
        print(f"  [*] OTP code pasted via fallback")
    except Exception:
        print(f"  [*] Page navigated during fallback — OTP accepted")
        return True
    page.wait_for_timeout(2000)
    if wait_for_captcha(page):
        solve_captcha(page)
    return True


def find_bframe(page):
    for f in page.frames:
        if 'bframe' in f.url and 'recaptcha' in f.url:
            return f
    return None


def solve_audio_challenge(page):
    print(f"  [*] Solving audio challenge...")
    page.wait_for_timeout(500)
    mp3_path = "/tmp/recaptcha_audio.mp3"
    wav_path = "/tmp/recaptcha_audio.wav"
    max_retries = 5

    for retry in range(max_retries):
        frame = find_bframe(page)
        if not frame:
            print(f"  [!] BFrame not found (retry {retry+1}/{max_retries})")
            page.wait_for_timeout(2000)
            continue
        audio_url = None
        for attempt in range(5):
            try:
                audio_url = frame.evaluate("""() => {
                    const audio = document.querySelector('audio');
                    if (!audio) return null;
                    const src = audio.querySelector('source');
                    return src ? src.src : audio.src;
                }""")
            except Exception:
                audio_url = None
            if audio_url:
                break
            page.wait_for_timeout(500)
        if not audio_url:
            print(f"  [!] Could not extract audio URL (retry {retry+1}/{max_retries})")
            try:
                bframe_html = frame.evaluate("() => document.body ? document.body.innerText.slice(0, 500) : 'no body'")
                print(f"  [!] BFrame content: {bframe_html}")
                if "Réessayez" in bframe_html or "plus tard" in bframe_html:
                    print(f"  [!] Captcha rate-limited — closing session")
                    page.close()
                    sys.exit(1)
            except Exception as e:
                print(f"  [!] Failed to read bframe: {e}")
            if retry < max_retries - 1:
                click_audio_refresh(page)
                page.wait_for_timeout(2000)
                continue
            return False

        print(f"  [*] Audio URL: {audio_url[:120]}...")
        try:
            resp = session.get(audio_url, timeout=15, headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
                "Accept": "audio/webm,audio/ogg,audio/wav;q=0.9,audio/*;q=0.8",
            })
            resp.raise_for_status()
            with open(mp3_path, "wb") as f:
                f.write(resp.content)
            print(f"  [*] Downloaded audio ({len(resp.content)} bytes)")
        except Exception as e:
            print(f"  [!] Download failed: {e}")
            if retry < max_retries - 1:
                click_audio_refresh(page)
                page.wait_for_timeout(2000)
                continue
            return False

        try:
            import subprocess as _sp
            _sp.run(["ffmpeg", "-y", "-i", mp3_path, wav_path],
                    timeout=30, capture_output=True)
        except Exception as e:
            print(f"  [!] Conversion failed: {e}")
            if retry < max_retries - 1:
                click_audio_refresh(page)
                page.wait_for_timeout(2000)
                continue
            return False

        try:
            r = sr.Recognizer()
            with sr.AudioFile(wav_path) as source:
                r.adjust_for_ambient_noise(source, duration=0.5)
                data = r.record(source)
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                text = pool.submit(r.recognize_google, data, language="fr-FR").result(timeout=15)
            print(f"  [*] Transcribed: {text}")
            page.wait_for_timeout(2000)
            if not find_bframe(page):
                print(f"  [*] Captcha resolved after transcription — no bframe found")
                return True
        except Exception as e:
            print(f"  [!] Transcription failed: {e}")
            if retry < max_retries - 1:
                click_audio_refresh(page)
                page.wait_for_timeout(2000)
                continue
            return False

        frame = find_bframe(page)
        if not frame:
            print(f"  [!] BFrame lost before filling response (retry {retry+1}/{max_retries})")
            if retry < max_retries - 1:
                click_audio_refresh(page)
                page.wait_for_timeout(2000)
                continue
            return False
        try:
            input_el = frame.wait_for_selector(
                "#audio-response, input[type='text'], .rc-audiochallenge-response-input",
                timeout=5000
            )
            if input_el:
                input_el.fill(text)
            else:
                if retry < max_retries - 1:
                    click_audio_refresh(page)
                    page.wait_for_timeout(2000)
                    continue
                return False
        except Exception:
            if retry < max_retries - 1:
                click_audio_refresh(page)
                page.wait_for_timeout(2000)
                continue
            return False

        frame = find_bframe(page)
        if not frame:
            print(f"  [!] BFrame lost before clicking verify (retry {retry+1}/{max_retries})")
            if retry < max_retries - 1:
                click_audio_refresh(page)
                page.wait_for_timeout(2000)
                continue
            return False
        try:
            verify_btn = frame.wait_for_selector(
                "#recaptcha-verify-button, button[type='submit'], .verify-button",
                timeout=5000
            )
            if verify_btn:
                verify_btn.click()
                page.wait_for_timeout(3000)
        except Exception:
            if retry < max_retries - 1:
                click_audio_refresh(page)
                page.wait_for_timeout(2000)
                continue
            return False

        for p in [mp3_path, wav_path]:
            try:
                os.remove(p)
            except Exception:
                pass
        return True

    return False


def click_audio_refresh(page):
    print(f"  [*] Refreshing audio challenge...")
    frame = find_bframe(page)
    if not frame:
        print(f"  [!] BFrame not found for refresh")
        return
    try:
        clicked = frame.evaluate("""() => {
            const btns = document.querySelectorAll('button, a, [role="button"]');
            for (const btn of btns) {
                const text = (btn.textContent || '').toLowerCase().trim();
                const aria = (btn.getAttribute('aria-label') || '').toLowerCase();
                const cls = btn.className.toLowerCase();
                if (aria.includes('get a new challenge') || aria.includes('reload') ||
                    text.includes('reload') || text.includes('try again') ||
                    text.includes('new challenge') || cls.includes('reload')) {
                    btn.click();
                    return true;
                }
            }
            return false;
        }""")
        if not clicked:
            frame.evaluate("""() => {
                const btn = document.querySelector('#recaptcha-reload-button');
                if (btn) btn.click();
            }""")
        print(f"  [*] Audio challenge refreshed")
    except Exception as e:
        print(f"  [!] Failed to refresh audio: {e}")


def click_image_match(page, template_path, label, threshold=0.7, click_on_match=True):
    screenshot_path = result_dir / "match_screenshot.png"
    page.screenshot(path=str(screenshot_path))
    im_screenshot = cv2.imread(str(screenshot_path))
    im_template  = cv2.imread(template_path)
    if im_screenshot is None:
        print(f"  [*] Failed to load screenshot for {label}")
        return False
    if im_template is None:
        print(f"  [*] Failed to load {template_path} – skipping {label}")
        return False
    result = cv2.matchTemplate(im_screenshot, im_template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    if max_val < threshold:
        print(f"  [*] {label} not found (best match {max_val:.2f})")
        return False
    if not click_on_match:
        return True
    h, w = im_template.shape[:2]
    cx = max_loc[0] + w // 2
    cy = max_loc[1] + h // 2
    scale_x = page.viewport_size["width"] / im_screenshot.shape[1]
    scale_y = page.viewport_size["height"] / im_screenshot.shape[0]
    page.mouse.click(cx / scale_x, cy / scale_y)
    print(f"  [*] Clicked {label} at ({int(cx)}:{int(cy)}) confidence {max_val:.2f}")
    try:
        page.wait_for_timeout(1500)
    except Exception:
        pass
    return True


def click_captcha_checkbox(page, src_dir):
    captcha_path = os.path.join(src_dir, "captcha.png")
    if os.path.exists(captcha_path):
        clicked = click_image_match(page, captcha_path, "captcha", threshold=0.7)
        if not clicked:
            print(f"  [*] captcha.png not found — trying anchor iframe")
            els = page.query_selector_all(
                "iframe[src*='recaptcha/anchor'], iframe[title='reCAPTCHA'], .grecaptcha-badge"
            )
            if els:
                el = els[-1]
                box = el.bounding_box()
                if box and box['width'] > 0 and box['height'] > 0:
                    page.mouse.click(box['x'] + 10, box['y'] + box['height'] / 2)
                    page.wait_for_timeout(2000)
                    print(f"  [*] Clicked last captcha anchor iframe")
            else:
                for sel in [
                    "iframe[src*='recaptcha/enterprise/anchor']",
                    "iframe[src*='recaptcha/api2/anchor']",
                    "iframe[title='reCAPTCHA']",
                    ".grecaptcha-badge",
                ]:
                    try:
                        el = page.wait_for_selector(sel, timeout=3000)
                        if el:
                            box = el.bounding_box()
                            if box and box['width'] > 0 and box['height'] > 0:
                                page.mouse.click(box['x'] + 10, box['y'] + box['height'] / 2)
                                page.wait_for_timeout(2000)
                                print(f"  [*] Clicked captcha anchor: {sel}")
                                break
                    except Exception:
                        continue
    try:
        page.wait_for_timeout(3000)
    except Exception:
        pass


def solve_captcha(page):
    print(f"  [*] Solving captcha...")
    src_dir = os.path.join(os.path.dirname(__file__), "src")
    for attempt in range(5):
        click_captcha_checkbox(page, src_dir)
        # Click audio button via image match — keep polling until found
        audio_path = os.path.join(src_dir, "audio.png")
        aud_clicked = False
        poll_start = time.time()
        audio_fail_count = 0
        spinner_seen_at = None
        while time.time() - poll_start < 60:
            page.wait_for_timeout(2000)
            aud = click_image_match(page, audio_path, "audio", threshold=0.7)
            if aud:
                aud_clicked = True
                print(f"  [*] Audio challenge triggered via audio.png")
                break
            audio_fail_count += 1
            still_captcha = page.evaluate("""() => {
                return !!document.querySelector('iframe[src*="recaptcha/enterprise/bframe"], iframe[src*="recaptcha/api2/bframe"]');
            }""")
            if not still_captcha:
                print(f"  [*] Captcha gone while looking for audio — dumping and identifying screen")
                dump_all(page, f"captcha_gone_audio_not_found")
                after_screen = identify_screen(page)
                print(f"  [*] Screen: {after_screen}")
                if after_screen and after_screen in SCREEN_ACTIONS:
                    SCREEN_ACTIONS[after_screen](page)
                return True
            print(f"  [*] Audio not found — re-clicking captcha checkbox")
            click_captcha_checkbox(page, src_dir)
            if audio_fail_count % 3 == 0:
                dump_full_html(page, f"audio_fail_{attempt+1}_{audio_fail_count}")
                has_error = page.evaluate("""() => {
                    return document.body.textContent.includes("La vérification de l'appareil a échoué") ||
                           document.body.textContent.includes("Veuillez réessayer");
                }""")
                if has_error:
                    print(f"  [!] Device verification error detected — dumping all state")
                    dump_all(page, f"audio_device_error_{attempt+1}")
                    print(f"  [!] Device verification failed — exiting script")
                    sys.exit(1)
                # Check bframe state — spinner vs challenge vs blank
                bframe_state = page.evaluate("""() => {
                    const bframe = document.querySelector('iframe[src*="recaptcha/enterprise/bframe"], iframe[src*="recaptcha/api2/bframe"]');
                    if (!bframe) return 'no_bframe';
                    const name = bframe.getAttribute('name') || '';
                    let doc = null;
                    try {
                        doc = bframe.contentDocument || bframe.contentWindow.document;
                    } catch(e) {
                        return 'cross_origin';
                    }
                    if (!doc || !doc.body) return 'no_doc';
                    const html = doc.body.textContent || '';
                    const spinner = doc.querySelector('.rc-spinner, [class*="spinner"], [class*="loading"]');
                    const challenge = doc.querySelector('.rc-audiochallenge-tab, .rc-imagechallenge-tab, #audio-response, audio');
                    const checkbox = doc.querySelector('.recaptcha-checkbox');
                    const errorText = html.includes("vérification de l'appareil") || html.includes("device verification");
                    if (errorText) return 'device_error';
                    if (challenge) return 'challenge';
                    if (spinner || html.includes('Verifying') || html.includes('Vérification')) return 'spinner';
                    if (checkbox) return 'checkbox';
                    return 'unknown';
                }""")
                print(f"  [*] BFrame state: {bframe_state}")
                if bframe_state == 'challenge':
                    print(f"  [*] Challenge already visible but audio.png not matched — breaking out")
                    aud_clicked = True
                    break
                if bframe_state in ('spinner', 'unknown'):
                    now = time.time()
                    if spinner_seen_at is None:
                        spinner_seen_at = now
                    elif now - spinner_seen_at > 12:
                        print(f"  [!] Spinner stuck >12s — re-clicking captcha checkbox to refresh handshake")
                        dump_full_html(page, f"spinner_stuck_{attempt+1}_{audio_fail_count}")
                        spinner_seen_at = None
                        # Re-click captcha checkbox
                        click_captcha_checkbox(page, src_dir)
                        page.wait_for_timeout(3000)
                else:
                    spinner_seen_at = None
        if not aud_clicked:
            print(f"  [*] Audio button never appeared within 60s — skipping challenge")
            continue
        # Find challenge frame and solve audio
        frame = None
        for f in page.frames:
            if 'bframe' in f.url and 'recaptcha' in f.url:
                frame = f
                break
        if not frame:
            try:
                page.wait_for_selector("iframe[src*='recaptcha/enterprise/bframe']", state="attached", timeout=3000)
                for f in page.frames:
                    if 'bframe' in f.url and 'recaptcha' in f.url:
                        frame = f
                        break
            except Exception:
                pass
        if frame:
            try:
                frame.wait_for_load_state("domcontentloaded", timeout=3000)
            except Exception:
                pass
            page.evaluate("""(name) => {
                const iframe = document.querySelector(`iframe[name="${name}"]`);
                if (iframe) {
                    let el = iframe;
                    while (el) {
                        if (el.style) { el.style.display = 'block'; el.style.visibility = 'visible'; }
                        el = el.parentElement;
                    }
                }
            }""", frame.name)
            page.wait_for_timeout(1500)
            solve_audio_challenge(page)
        else:
            print(f"  [!] No challenge frame found on attempt {attempt+1}")
        # Check if captcha resolved
        page.wait_for_timeout(3000)
        still_captcha = page.evaluate("""() => {
            return !!document.querySelector('iframe[src*="recaptcha/enterprise/bframe"], iframe[src*="recaptcha/api2/bframe"]');
        }""")
        if not still_captcha:
            print(f"  [*] Captcha resolved after attempt {attempt+1}")
            time.sleep(5)
            dump_all(page, f"captcha_resolved_{attempt+1}")
            after_screen = identify_screen(page)
            print(f"  [*] Screen after captcha resolve: {after_screen}")
            for _ in range(6):
                if after_screen is not None:
                    break
                print(f"  [*] Screen is None — sleeping 5s and retrying")
                time.sleep(5)
                after_screen = identify_screen(page)
                print(f"  [*] Screen after retry: {after_screen}")
            if after_screen == "otp":
                print(f"  [*] OTP screen detected after captcha — checking for captcha first")
                if wait_for_captcha(page):
                    print(f"  [*] Captcha still present — solving before OTP")
                    solve_captcha(page)
                    page.wait_for_timeout(3000)
                    after_screen = identify_screen(page)
                    print(f"  [*] Screen after pre-OTP captcha solve: {after_screen}")
                    if after_screen != "otp":
                        print(f"  [*] Screen changed from otp to {after_screen} — dispatching action")
                        if after_screen in SCREEN_ACTIONS:
                            SCREEN_ACTIONS[after_screen](page)
                        return True
                print(f"  [*] Filling OTP")
                global email
                for otp_attempt in range(3):
                    fill_otp(page, email)
                    page.wait_for_timeout(3000)
                    after_screen = identify_screen(page)
                    print(f"  [*] Screen after OTP (attempt {otp_attempt+1}): {after_screen}")
                    if after_screen != "otp":
                        break
                    print(f"  [*] OTP screen still present — checking for captcha")
                    if wait_for_captcha(page):
                        print(f"  [*] Captcha blocking OTP — solving")
                        solve_captcha(page)
                        page.wait_for_timeout(3000)
                        after_screen = identify_screen(page)
                        print(f"  [*] Screen after captcha re-solve: {after_screen}")
                        if after_screen != "otp":
                            break
                    else:
                        print(f"  [*] No captcha found — retrying OTP fill")
            if after_screen == "loading":
                print(f"  [*] Loading screen after OTP — sleeping 3s and dumping")
                time.sleep(3)
                dump_all(page, f"after_otp_loading")
                after_screen = identify_screen(page)
                print(f"  [*] Screen after loading: {after_screen}")
            if after_screen in ("stream", "profile"):
                print(f"  [*] Already on {after_screen} after OTP — skipping gender/confirmer flow")
                return True
            recheck_start = time.time()
            recheck_captcha = False
            while time.time() - recheck_start < 12:
                page.wait_for_timeout(1000)
                still_captcha = page.evaluate("""() => {
                    return !!document.querySelector('iframe[src*="recaptcha/enterprise/bframe"], iframe[src*="recaptcha/api2/bframe"]');
                }""")
                if still_captcha:
                    print(f"  [*] Second captcha detected — solving again")
                    solve_captcha(page)
                    recheck_captcha = True
                    break
            if recheck_captcha:
                return True
            if not still_captcha:
                homme_path = os.path.join(src_dir, "homme.png")
                if os.path.exists(homme_path) and click_image_match(page, homme_path, "homme", threshold=0.7):
                    dump_all(page, f"after_captcha_homme")
                    print(f"  [*] Dumped state after captcha+homme")
                else:
                    from_btn = page.evaluate("""() => {
                        const btn = [...document.querySelectorAll('button')].find(b => b.textContent.trim() === 'Homme' && b.offsetHeight > 0);
                        if (btn) { btn.click(); return true; }
                        return false;
                    }""")
                    if from_btn:
                        print(f"  [*] Clicked Homme button via selector")
                page.wait_for_timeout(1000)
                confirmer_ok = find_and_click(page, "Confirmer", ["confirmer", "confirm"], dump_prefix="confirmer_fail")
                if confirmer_ok:
                    dump_all(page, "after_captcha_confirmer")
                    print(f"  [*] Dumped state after captcha+confirmer")
                else:
                    after_screen = identify_screen(page)
                    print(f"  [*] Screen after Confirmer not found: {after_screen}")
                    if after_screen and after_screen in SCREEN_ACTIONS:
                        print(f"  [*] Dispatching action for {after_screen}")
                        SCREEN_ACTIONS[after_screen](page)
                    else:
                        print(f"  [*] Unknown screen — dumping for later analysis")
                        dump_all(page, f"unknown_after_captcha_{after_screen or 'none'}")
            return True
        print(f"  [*] Captcha still present — retrying ({attempt+1}/5)")
        page.wait_for_timeout(2000)
    return False


def fill_reg_form(page, email, password):
    email_selectors = ["#email", "input[name='email']", "input[type='email']", "input[placeholder*='email' i]", "input[placeholder*='e-mail' i]"]
    pass_selectors = ["#password", "input[name='password']", "input[type='password']"]
    pass2_selectors = ["#passwordRepeat", "#password2", "input[name='passwordRepeat']", "input[name='password2']", "input[placeholder*='confirm' i]"]
    fill_field(page, email, email_selectors)
    fill_field(page, password, pass_selectors)
    fill_field(page, password, pass2_selectors)
    page.wait_for_timeout(500)
    find_and_click(page, "Continuer", ["continuer", "continue", "suivant", "next", "إرسال", "submit"])
    page.wait_for_timeout(10000)
    has_captcha = page.evaluate("""() => {
        return !!document.querySelector('iframe[src*="recaptcha/enterprise/bframe"], iframe[src*="recaptcha/api2/bframe"]');
    }""")
    if has_captcha:
        print("  [*] Captcha detected after Continue")
        solve_captcha(page)
    else:
        print("  [*] No captcha detected after Continue")
        page.wait_for_timeout(3000)
        has_captcha = page.evaluate("""() => {
            return !!document.querySelector('iframe[src*="recaptcha/enterprise/bframe"], iframe[src*="recaptcha/api2/bframe"]');
        }""")
        if has_captcha:
            print("  [*] Captcha detected after re-check")
            solve_captcha(page)


def run_session():
    global email, password
    result_dir.mkdir(parents=True, exist_ok=True)
    print("=" * 60)
    print("  BASE – screen-based state machine")
    print("=" * 60)

    username, email, password = generate_credentials()
    print(f"\n  [*] Username: {username}")
    print(f"  [*] Email:    {email}")
    print(f"  [*] Password: {password}")

    if use_proxy and not static_proxies:
        print(f"\n  [+] Resetting Tor circuit...")
        ret = os.system("curl -s http://127.0.0.1:5000/reset-ip")
        if ret == 0:
            print(f"  [*] Tor circuit reset")
            time.sleep(5)
        else:
            print(f"  [!] Tor reset failed (exit {ret})")

    if headless_mode == "virtual":
        opts["headless"] = False
    with Camoufox(from_options=opts, headless=headless_mode) as browser:
        page = browser.new_page()
        page.set_default_timeout(30000)
        page.set_viewport_size({"width": 1280, "height": 720})

        print(f"\n  [+] Checking IP via browser...")
        page.goto("https://api.ipify.org", wait_until="domcontentloaded", timeout=30000)
        ip = page.text_content("body")
        print(f"  [*] Browser IP: {ip.strip() if ip else 'unknown'}")

        print(f"\n  [+] Navigating to https://superlive.chat/fr/nonlogin-messages")
        page.goto("https://superlive.chat/fr/nonlogin-messages", wait_until="domcontentloaded", timeout=120000)
        page.wait_for_timeout(4000)

        step_counter = 1
        email_input_count = 0
        loading_count = 0
        while True:
            print(f"\n{'='*60}")
            print(f"  STEP {step_counter}: dumping current page state")
            print(f"{'='*60}")
            dump_all(page, f"step{step_counter}")
            print(f"  [+] Step {step_counter} dumps saved to {result_dir}/")

            screen = identify_screen(page)
            print(f"\n  [*] Screen detected: {screen}")
            print_form_title(page)
            # Save extra dump for "Commencer la discussion" for later analysis
            title = page.evaluate("""() => {
                const h = document.querySelector('h1, h2, h3, h4, h5');
                if (h) return h.textContent.trim().slice(0, 80);
                const p = document.querySelector('.text-lg.font-medium, .text-center.text-lg');
                if (p) return p.textContent.trim().slice(0, 80);
                return null;
            }""")
            if title and "Commencer la discussion" in title:
                dump_all(page, f"commercer_{step_counter}")
                print(f"  [+] Extra dump saved for '{title}'")

            if screen == "loading":
                loading_count += 1
                print(f"  [*] loading count: {loading_count}/12")
                if loading_count >= 12:
                    print(f"  [!] Loading seen 12 times — treating as home")
                    screen = "home"
                else:
                    time.sleep(3)
                    continue
            else:
                loading_count = 0

            if screen == "email_input":
                email_input_count += 1
                print(f"  [*] email_input count: {email_input_count}/3")
                if email_input_count >= 3:
                    print(f"  [!] email_input seen 3 times — exiting")
                    break
            else:
                email_input_count = 0

            if screen == "captcha":
                print(f"  [*] Captcha screen — stopping loop")
                print(f"STEP {step_counter} [captcha]")
                time.sleep(8)
                break

            action = SCREEN_ACTIONS.get(screen)
            if action:
                print(f"STEP {step_counter} [{screen}]")
                time.sleep(8)
                action(page)
                time.sleep(5)
            else:
                print(f"  [!] Unknown screen: {screen}")
                print(f"STEP {step_counter} [unknown — press Enter to retry]")
                time.sleep(8)

            if screen == "profile":
                print(f"  [+] Profile action done — waiting for next screen")
                page.wait_for_timeout(3000)
                step_counter += 1
                continue

            if screen == "stream":
                print(f"  [+] Stream reached — exiting main loop")
                step_counter += 1
                dump_all(page, f"step{step_counter}")
                break

            step_counter += 1

        print(f"\n  [+] Cleaning up results...")
        shutil.rmtree(result_dir)
        print(f"  [+] Results directory removed")


if __name__ == "__main__":
    if args.nordvpn:
        import signal
        signal.signal(signal.SIGINT, lambda s, f: (print("\n[!] Interrupted"), sys.exit(1)))
        signal.signal(signal.SIGTERM, lambda s, f: (print("\n[!] Terminated"), sys.exit(1)))

        while True:
            if not vpn.connect_random():
                time.sleep(3)
                continue
            try:
                run_session()
            except KeyboardInterrupt:
                print("\n[!] Interrupted — exiting")
                vpn.disconnect()
                sys.exit(1)
            except SystemExit:
                print("[*] Session exited")
            except Exception as e:
                print(f"[!] Session error: {e}")
                import traceback
                traceback.print_exc()

            print("[*] Session finished — reconnecting...")
            time.sleep(3)
    else:
        run_session()
