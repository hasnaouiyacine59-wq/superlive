import argparse
import json
import os
import random
import shutil
import sys
import time
from pathlib import Path

import requests

from camoufox import Camoufox
from camoufox.utils import launch_options
from camoufox.pkgman import CamoufoxFetcher
CamoufoxFetcher.cleanup = staticmethod(lambda: False)
from super_email import get_2fa
import super_db
import f_vpn as vpn

parser = argparse.ArgumentParser()
parser.add_argument("-n", "--nordvpn", nargs="?", const="random", default=None,
                    help="Enable NordVPN rotation (optionally specify country code, e.g. -n fr)")
args = parser.parse_args()

URL = "https://superlive.chat/fr/nonlogin-messages"

result_dir = Path("results_register")
if result_dir.exists():
    shutil.rmtree(result_dir)
result_dir.mkdir(parents=True, exist_ok=True)

FAILED = False


def cleanup():
    global FAILED
    FAILED = True
    if result_dir.exists():
        shutil.rmtree(result_dir)
        print(f"\n  [!] Cleaned up {result_dir}")
        time.sleep(5)


def fail(msg):
    print(f"\n  [!] FAIL: {msg}")
    cleanup()
    sys.exit(1)


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


opts = launch_options(
    geoip=True, humanize=0.05, block_webrtc=True,
    block_images=False, disable_coop=True,
    main_world_eval=True, window=(1280, 720), debug=False,
    headless=os.environ.get("HEADLESS", "false").lower() == "true", i_know_what_im_doing=True,
)


def dump_full_html(page, prefix):
    for attempt in range(3):
        try:
            html = page.evaluate("() => document.documentElement.outerHTML")
            break
        except Exception as e:
            if "Execution context was destroyed" in str(e) and attempt < 2:
                print(f"  [*] Navigation during dump, retrying ({attempt+1}/2)...")
                page.wait_for_timeout(2000)
                continue
            raise
    path = result_dir / f"{prefix}_superlive_full.html"
    path.write_text(html, encoding="utf-8")
    print(f"  [*] {prefix}: Full HTML saved ({len(html)} chars)")


def dump_visible_elements(page, prefix):
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


def dump_clickable(page, prefix):
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


def dump_iframes(page, prefix):
    iframes = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('iframe')).map(f => ({
            src: (f.src || '').slice(0, 200),
            id: f.id, name: f.name, title: f.title,
            width: f.width, height: f.height,
            visible: f.offsetWidth > 0 && f.offsetHeight > 0,
        }));
    }""")
    path = result_dir / f"{prefix}_superlive_iframes.json"
    path.write_text(json.dumps(iframes, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  [*] {prefix}: Iframes saved ({len(iframes)} items)")


def dump_all(page, prefix):
    dump_full_html(page, prefix)
    dump_visible_elements(page, prefix)
    dump_clickable(page, prefix)
    dump_iframes(page, prefix)


def identify_screen(page):
    screens = [
        ("register_vs_login", """() => {
            const all = document.querySelectorAll('button');
            const has_register = [...all].some(b => b.textContent.toLowerCase().includes("s'enregistrer avec") && b.offsetHeight > 0);
            const has_login = [...all].some(b => b.textContent.toLowerCase().includes('connectez-vous avec') && b.offsetHeight > 0);
            return has_register && has_login;
        }"""),
        ("email_input", """() => {
            const el = document.querySelector('#otp-email, #email, input[name="email"], input[type="email"]');
            return !!el && el.offsetHeight > 0 && !document.querySelector('input[type="password"], input[name*="password" i]');
        }"""),
        ("otp", """() => {
            const single = document.querySelector('#otp-code-0, input[autocomplete="one-time-code"]');
            if (single) return true;
            const inputs = document.querySelectorAll('input[maxlength="1"], input[inputmode="numeric"][maxlength]');
            let count = 0;
            for (const inp of inputs) {
                if (inp.offsetHeight > 0) count++;
            }
            return count >= 4;
        }"""),
        ("reg_form", """() => {
            const email = document.querySelector('#otp-email, #email, input[name="email"], input[type="email"]');
            const pass = document.querySelector('input[type="password"], input[name*="password" i], [autocomplete="new-password"]');
            if (!email || !pass || email.offsetHeight <= 0 || pass.offsetHeight <= 0) return false;
            const otpInputs = document.querySelectorAll('input[maxlength="1"], input[inputmode="numeric"][maxlength]');
            let otpCount = 0;
            for (const inp of otpInputs) {
                if (inp.offsetHeight > 0) otpCount++;
            }
            return otpCount < 4;
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
            const btn = document.querySelector('button.rounded-full.border');
            if (btn && btn.className.includes('hover:bg-unique-label-100') && btn.offsetHeight > 0) return true;
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
        try:
            if page.evaluate(js):
                return name
        except Exception:
            pass
    return None


def detect_screen(page, label="", max_retries=3, delay=3):
    screen = identify_screen(page)
    attempts = 0
    while screen == "loading" and attempts < max_retries:
        print(f"  [*] Loading detected — sleeping {delay}s and re-checking (attempt {attempts+1}/{max_retries})")
        page.wait_for_timeout(delay * 1000)
        screen = identify_screen(page)
        attempts += 1
    if screen == "loading":
        print(f"  [*] Still loading after {max_retries} retries — continuing anyway")
    return screen


def fill_input(page, sel, value):
    time.sleep(random.uniform(0.3, 0.8))
    for attempt in range(3):
        try:
            el = page.wait_for_selector(sel, timeout=3000)
            if el:
                el.fill(value)
                print(f"  [*] Filled {sel}")
                page.wait_for_timeout(200)
                return True
        except Exception:
            pass
        page.wait_for_timeout(500)
    try:
        filled = page.evaluate("""(s, v) => {
            const el = document.querySelector(s);
            if (el) { el.value = v; el.dispatchEvent(new Event('input', {bubbles: true})); return true; }
            return false;
        }""", sel, value)
        if filled:
            print(f"  [*] JS-filled {sel}")
            return True
    except Exception:
        pass
    print(f"  [!] Could not fill {sel}")
    return False


def fill_field(page, value, selectors):
    for sel in selectors:
        if fill_input(page, sel, value):
            return True
    return False


def find_and_click(page, label, keywords):
    print(f"  [*] Looking for {label}...")
    time.sleep(random.uniform(0.3, 0.8))
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
    return False


def click_text(page, text_fragment):
    time.sleep(random.uniform(0.3, 0.8))
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


def fill_reg_form(page, email, password):
    email_selectors = ["#email", "input[name='email']", "input[type='email']", "input[placeholder*='email' i]", "input[placeholder*='e-mail' i]"]
    pass_selectors = ["#password", "input[name='password']", "input[type='password']"]
    pass2_selectors = ["#passwordRepeat", "#password2", "input[name='passwordRepeat']", "input[name='password2']", "input[placeholder*='confirm' i]"]
    fill_field(page, email, email_selectors)
    fill_field(page, password, pass_selectors)
    fill_field(page, password, pass2_selectors)
    page.wait_for_timeout(500)
    find_and_click(page, "Continuer", ["continuer", "continue", "suivant", "next", "إرسال", "submit"])
    print("  [*] Waiting for Continue button spinner to disappear...")
    for _ in range(15):
        spinning = page.evaluate("""() => {
            const allBtns = document.querySelectorAll('button');
            for (const b of allBtns) {
                if (b.querySelector('.animate-spin, svg.animate-spin, [class*="animate-spin"]')) return true;
            }
            return false;
        }""")
        if not spinning:
            break
        page.wait_for_timeout(1000)
    page.wait_for_timeout(2000)
    for attempt in range(5):
        has_captcha = page.evaluate("""() => {
            return !!document.querySelector('iframe[src*="recaptcha/enterprise/bframe"], iframe[src*="recaptcha/api2/bframe"]');
        }""")
        if has_captcha:
            print("  [*] Captcha detected after Continue — solving")
            solve_captcha(page)
            break
        else:
            print(f"  [*] No captcha detected after Continue (attempt {attempt+1}/5), sleeping 8s...")
            page.wait_for_timeout(8000)
    else:
        print("  [*] No captcha appeared after Continue — checking current screen")
        current = identify_screen(page)
        print(f"  [*] Current screen after no captcha: {current}")

    error_text = page.evaluate("""() => {
        const el = document.querySelector('[class*="error"], [class*="alert"], [class*="message"], p.text-red-500, div.text-red-500');
        if (el && el.textContent.includes('échoué')) return el.textContent.trim();
        const all = document.querySelectorAll('p, div, span');
        for (const e of all) {
            if (e.textContent.includes('La vérification') && e.textContent.includes('échoué')) return e.textContent.trim();
        }
        return null;
    }""")
    if error_text:
        print(f"  [!] Device verification failed — error: {error_text}")
        print("  [*] Retrying Continue click...")
        page.wait_for_timeout(2000)
        find_and_click(page, "Continuer", ["continuer", "continue", "suivant", "next", "إرسال", "submit"])
        page.wait_for_timeout(3000)
        for attempt in range(5):
            has_captcha = page.evaluate("""() => {
                return !!document.querySelector('iframe[src*="recaptcha/enterprise/bframe"], iframe[src*="recaptcha/api2/bframe"]');
            }""")
            if has_captcha:
                print("  [*] Captcha detected after retry — solving")
                solve_captcha(page)
                break
            else:
                print(f"  [*] No captcha after retry (attempt {attempt+1}/5), sleeping 8s...")
                page.wait_for_timeout(8000)


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


def find_bframe(page):
    for f in page.frames:
        if 'bframe' in f.url and 'recaptcha' in f.url:
            return f
    return None


def wait_for_captcha(page, timeout=30):
    poll_start = time.time()
    while time.time() - poll_start < timeout:
        try:
            has_bframe = page.evaluate("""() => {
                return !!document.querySelector('iframe[src*="recaptcha/enterprise/bframe"], iframe[src*="recaptcha/api2/bframe"]');
            }""")
            if has_bframe:
                print(f"  [*] Captcha detected via bframe after {time.time()-poll_start:.0f}s")
                return True
        except Exception:
            return False
        page.wait_for_timeout(500)
    print(f"  [*] No captcha appeared within {timeout}s")
    return False


def click_verify_and_wait(page, btn, timeout=20):
    btn.click()
    print("  [*] Clicked verify button")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            after = identify_screen(page)
            if after and after != "otp":
                return True
        except Exception:
            return True
        still_spinning = page.evaluate("""() => {
            const btns = document.querySelectorAll('button');
            let btn = null;
            for (const b of btns) {
                const t = b.textContent.toLowerCase().trim();
                if (t === 'verify' || t === 'vérifier' || b.type === 'submit') { btn = b; break; }
            }
            if (!btn) return false;
            return btn.disabled || btn.className.includes('opacity-50') || btn.className.includes('cursor-not-allowed') || !!btn.querySelector('.animate-spin, .spinner, [class*="spinner"]');
        }""")
        if not still_spinning:
            print(f"  [*] Verify spinner cleared after {time.time()-(deadline-timeout):.1f}s")
            return True
        page.wait_for_timeout(500)
    print(f"  [!] Verify spinner did not clear within {timeout}s")
    return False


def fill_otp(page, email):
    print(f"  [*] Fetching OTP code from email...")
    for otp_fetch_attempt in range(5):
        code = get_2fa(email, retries=3, delay=4)
        if code:
            break
        print(f"  [!] No OTP code found (attempt {otp_fetch_attempt+1}/5)")
    else:
        return False
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
            click_verify_and_wait(page, verify_btn)
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
                click_verify_and_wait(page, verify_btn)
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


def solve_audio_challenge(page):
    import numpy as np
    import cv2
    import speech_recognition as sr
    from pydub import AudioSegment

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
            if retry < max_retries - 1:
                click_audio_refresh(page)
                page.wait_for_timeout(2000)
                continue
            fail("could not extract audio link 5/5")

        print(f"  [*] Audio URL: {audio_url[:120]}...")
        try:
            resp = requests.get(audio_url, timeout=15, headers={
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
            fail("audio download failed")

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
            fail("audio conversion failed")

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
            fail("audio transcription failed")

        frame = find_bframe(page)
        if not frame:
            print(f"  [!] BFrame lost before filling response (retry {retry+1}/{max_retries})")
            if retry < max_retries - 1:
                click_audio_refresh(page)
                page.wait_for_timeout(2000)
                continue
            fail("bframe lost before filling response")
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
                fail("audio input element not found")
        except Exception:
            if retry < max_retries - 1:
                click_audio_refresh(page)
                page.wait_for_timeout(2000)
                continue
            fail("audio input exception")

        frame = find_bframe(page)
        if not frame:
            print(f"  [!] BFrame lost before clicking verify (retry {retry+1}/{max_retries})")
            if retry < max_retries - 1:
                click_audio_refresh(page)
                page.wait_for_timeout(2000)
                continue
            fail("bframe lost before clicking verify")
        try:
            verify_btn = frame.wait_for_selector(
                "#recaptcha-verify-button, button[type='submit'], .verify-button",
                timeout=5000
            )
            if verify_btn:
                verify_btn.click()
                print("  [*] Clicked recaptcha verify button")
                page.wait_for_timeout(8000)
        except Exception:
            if retry < max_retries - 1:
                click_audio_refresh(page)
                page.wait_for_timeout(2000)
                continue
            fail("verify button not found")

        for p in [mp3_path, wav_path]:
            try:
                os.remove(p)
            except Exception:
                pass
        return True

    fail("audio challenge failed")


def click_image_match(page, template_path, label, threshold=0.7, click_on_match=True):
    import numpy as np
    import cv2

    screenshot_path = result_dir / "match_screenshot.png"
    page.screenshot(path=str(screenshot_path), full_page=False)
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
            print(f"  [*] captcha.png not found — closing session")
            return False
    try:
        page.wait_for_timeout(3000)
    except Exception:
        pass
    return True


def solve_captcha(page):
    import numpy as np
    import cv2

    print(f"  [*] Solving captcha...")
    src_dir = os.path.join(os.path.dirname(__file__), "src")
    for attempt in range(5):
        custom_btn = page.evaluate("""() => {
            const btn = document.querySelector('button.rounded-full.border');
            if (btn && btn.className.includes('hover:bg-unique-label-100') && btn.offsetHeight > 0) {
                btn.click();
                return true;
            }
            return false;
        }""")
        if custom_btn:
            print(f"  [*] Clicked custom captcha trigger button")
            page.wait_for_timeout(2000)
        else:
            if not click_captcha_checkbox(page, src_dir):
                print(f"  [*] Captcha checkbox click failed — closing session")
                fail("captcha checkbox failed")
            page.wait_for_timeout(2000)

        poll_start = time.time()
        bframe_detected = False
        while time.time() - poll_start < 20:
            has_bframe = page.evaluate("""() => !!document.querySelector(
                'iframe[src*="recaptcha/enterprise/bframe"], iframe[src*="recaptcha/api2/bframe"]'
            )""")
            if has_bframe:
                print(f"  [*] BFrame detected after {time.time()-poll_start:.0f}s")
                bframe_detected = True
                break
            page.wait_for_timeout(1000)
        if not bframe_detected:
            print(f"  [*] No bframe appeared within 20s")
        else:
            page.wait_for_timeout(2000)

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
            page.wait_for_timeout(1000)
            audio_btn = frame.query_selector("#recaptcha-audio-button, button[aria-label*='audio' i], a[aria-label*='audio' i]")
            if audio_btn:
                audio_btn.click()
                print("  [*] Switched to audio challenge")
                page.wait_for_timeout(2000)
            else:
                print("  [*] Audio button not found in bframe — challenge may already be audio")
            solve_audio_challenge(page)
        else:
            print(f"  [!] No challenge frame found on attempt {attempt+1}")
        page.wait_for_timeout(2000)
        still_captcha = page.evaluate("""() => {
            return !!document.querySelector('iframe[src*="recaptcha/enterprise/bframe"], iframe[src*="recaptcha/api2/bframe"]');
        }""")
        if not still_captcha:
            print(f"  [*] Captcha resolved after attempt {attempt+1}")
            time.sleep(3)
            after_screen = identify_screen(page)
            print(f"  [*] Screen after captcha resolve: {after_screen}")
            return True
        print(f"  [*] Captcha still present — retrying ({attempt+1}/5)")
        page.wait_for_timeout(2000)
    fail("captcha solve failed")


def type_test_chat(page):
    page.wait_for_timeout(10000)
    chat = page.query_selector('textarea[placeholder="Chat"]')
    if chat:
        greetings = ["hi bb", "hi gorgeous", "hi sexy"]
        text = random.choice(greetings)
        chat.click()
        page.wait_for_timeout(500)
        chat.fill(text)
        page.wait_for_timeout(300)
        page.keyboard.press("Enter")
        print(f"  [*] Sent: \"{text}\"")
    else:
        print("  [!] Chat field not found")


def run():
    url = URL

    if args.nordvpn:
        vpn.disconnect()
        time.sleep(2)
        if args.nordvpn == "random":
            ok = vpn.connect_random()
        else:
            ok = vpn.connect_country(args.nordvpn)
        if not ok:
            print("  [!] VPN connection failed — aborting")
            cleanup()
            sys.exit(1)
        print("  [+] VPN connected — proceeding")
        print()

    username, email, password = generate_credentials()
    print("=" * 60)
    print(f"  SUPER REGISTER")
    print("=" * 60)
    print(f"\n  [*] Username: {username}")
    print(f"  [*] Email:    {email}")
    print(f"  [*] Password: {password}")

    super_db.create_accounts_table()
    print(f"\n  [+] Visiting {url}")

    time.sleep(3)

    try:
        with Camoufox(**opts) as browser:
            page = browser.new_page()
            page.set_default_timeout(30000)
            page.set_viewport_size({"width": 1280, "height": 720})

            print(f"\n  [+] Navigating to {url}")
            page.goto(url, wait_until="load", timeout=80000)
            print(f"  [+] Page load event fired — waiting 4s for JS render")
            page.wait_for_timeout(4000)
            dump_all(page, "initial")

            screen = detect_screen(page, "initial")
            print(f"\n  [*] Screen detected: {screen}")
            print_form_title(page)
            if not screen:
                fail("unknown screen on initial load")

            if screen == "home":
                print(f"\n  [*] Step 1: Clicking S'inscrire")
                if not click_text(page, "S'inscrire"):
                    fail("step 1 — S'inscrire not found")
                page.wait_for_timeout(2000)
                dump_all(page, "after_inscrire")
                screen = detect_screen(page, "after_inscrire")
                print(f"  [*] Screen after click: {screen}")
                if not screen:
                    fail("step 1 — no screen detected after click")

            if screen == "provider_picker":
                print(f"\n  [*] Step 2: Clicking Poursuivre avec Email")
                if not click_text(page, "Poursuivre avec Email"):
                    fail("step 2 — Poursuivre avec Email not found")
                page.wait_for_timeout(2000)
                dump_all(page, "after_provider_picker")
                screen = detect_screen(page, "after_provider_picker")
                print(f"  [*] Screen after click: {screen}")
                if not screen:
                    fail("step 2 — no screen detected after click")

            if screen == "register_vs_login":
                print(f"\n  [*] Step 3: Clicking register with email")
                if not find_and_click(page, "register with email", [
                    "s'enregistrer avec l'adresse e-mail",
                    "s'enregistrer avec",
                    "enregistrer avec l'adresse e-mail"
                ]):
                    fail("step 3 — register with email not found")
                page.wait_for_timeout(2000)
                dump_all(page, "after_register_vs_login")
                screen = detect_screen(page, "after_register_vs_login")
                print(f"  [*] Screen after click: {screen}")
                if not screen:
                    fail("step 3 — no screen detected after click")

            if screen == "email_input":
                print(f"\n  [*] Step 4: Filling email and continuing")
                if not fill_field(page, email, ["#otp-email", "#email", "input[name='email']", "input[type='email']"]):
                    fail("step 4 — could not fill email")
                page.wait_for_timeout(500)
                if not find_and_click(page, "Continuer", ["continuer", "continue", "suivant", "next", "إرسال", "submit"]):
                    fail("step 4 — Continuer button not found")
                for _ in range(15):
                    spinning = page.evaluate("""() => {
                        const allBtns = document.querySelectorAll('button');
                        for (const b of allBtns) {
                            if (b.querySelector('.animate-spin, svg.animate-spin, [class*="animate-spin"]')) return true;
                        }
                        return false;
                    }""")
                    if not spinning:
                        print("  [*] Spinner gone")
                        break
                    page.wait_for_timeout(1000)
                page.wait_for_timeout(2000)
                dump_all(page, "after_email")
                screen = detect_screen(page, "after_email")
                print(f"  [*] Screen after email: {screen}")
                if not screen:
                    fail("step 4 — no screen detected after email")

            if screen == "otp":
                print(f"\n  [*] Step 4b: OTP screen detected")
                fill_otp(page, email)
                page.wait_for_timeout(3000)
                dump_all(page, "after_otp")
                screen = detect_screen(page, "after_otp")
                print(f"  [*] Screen after OTP: {screen}")
                if screen is None:
                    print("  [*] Screen was None — waiting 5s and retrying...")
                    page.wait_for_timeout(5000)
                    dump_all(page, "after_otp_retry_none")
                    screen = detect_screen(page, "after_otp_retry_none")
                    print(f"  [*] Screen after OTP retry: {screen}")
                if screen == "otp":
                    print("  [*] Still on OTP screen — polling for verify button or captcha")
                    for attempt in range(3):
                        poll_deadline = time.time() + 25
                        while time.time() < poll_deadline:
                            has_bframe = page.evaluate("""() => !!document.querySelector('iframe[src*="recaptcha/enterprise/bframe"], iframe[src*="recaptcha/api2/bframe"]')""")
                            if has_bframe:
                                print("  [*] Captcha appeared while waiting for verify")
                                solve_captcha(page)
                                page.wait_for_timeout(2000)
                                after_c = identify_screen(page)
                                if after_c and after_c != "otp" and after_c != "captcha":
                                    screen = after_c
                                    print(f"  [*] Screen after captcha solve: {screen}")
                                break
                            verify_btn = page.query_selector("button:has-text('Verify'), button:has-text('Vérifier'), button[type='submit']")
                            if verify_btn:
                                ready = page.evaluate("""(b) => {
                                    if (b.disabled) return false;
                                    if (b.className.includes('opacity-50') || b.className.includes('cursor-not-allowed')) return false;
                                    if (b.querySelector('.animate-spin, .spinner, [class*="spinner"]')) return false;
                                    return true;
                                }""", verify_btn)
                                if ready:
                                    print("  [*] Clicking verify button...")
                                    click_verify_and_wait(page, verify_btn)
                                    break
                            cur = identify_screen(page)
                            if cur and cur != "otp":
                                screen = cur
                                print(f"  [*] Screen changed while waiting: {screen}")
                                break
                            page.wait_for_timeout(500)
                        page.wait_for_timeout(3000)
                        dump_all(page, f"after_otp_retry_{attempt+1}")
                        screen = detect_screen(page, f"after_otp_retry_{attempt+1}")
                        print(f"  [*] Screen after OTP retry {attempt+1}: {screen}")
                        if screen != "otp":
                            break
                if not screen:
                    fail("step 4b — no screen detected after OTP")

            if screen == "gender":
                print(f"\n  [*] Step 4c: Gender selection")
                super_db.save_account(username, email, password, status="ready", obs="gender_screen_reached")
                print("  [*] Account saved to DB with status=ready")
                for gender_attempt in range(3):
                    if screen != "gender":
                        break
                    if gender_attempt > 0:
                        print(f"  [*] Gender retry attempt {gender_attempt+1}/3")
                    if not find_and_click(page, "Homme", ["homme"]):
                        if gender_attempt == 2:
                            fail("step 4c — Homme button not found")
                        page.wait_for_timeout(2000)
                        continue
                    page.wait_for_timeout(1000)
                    if not find_and_click(page, "Confirmer", ["confirmer", "confirm"]):
                        if gender_attempt == 2:
                            fail("step 4c — Confirmer button not found")
                        page.wait_for_timeout(2000)
                        continue
                    page.wait_for_timeout(3000)
                    dump_all(page, f"after_gender_{gender_attempt}")
                    screen = detect_screen(page, f"after_gender_{gender_attempt}")
                    print(f"  [*] Screen after gender: {screen}")
                if screen == "messages":
                    print(f"\n  [*] Messages screen detected — registration complete")
                    print("  [*] Visiting profile...")
                    for _retry in range(3):
                        try:
                            page.goto("https://superlive.chat/fr/profile/49194780", wait_until="load", timeout=120000)
                            break
                        except Exception as _e:
                            print(f"  [!] Profile nav failed (retry {_retry+1}/3): {_e}")
                            page.wait_for_timeout(5000)
                    page.wait_for_timeout(3000)
                    dump_all(page, "profile")
                    screen = detect_screen(page, "after_profile_nav")
                    print(f"  [*] Screen after profile nav: {screen}")
                    if screen is None:
                        print("  [*] Screen was None, waiting 5s and retrying...")
                        page.wait_for_timeout(5000)
                        dump_all(page, "profile_retry")
                        screen = detect_screen(page, "profile_retry")
                        print(f"  [*] Screen after retry: {screen}")
                    if screen == "profile":
                        print(f"\n  [*] Profile screen detected — account activated")
                        super_db.save_account(username, email, password, status="activated", obs="profile_reached")
                        print("  [*] Account saved to DB with status=activated")
                        print("  [*] Clicking profile picture to go live...")
                        el = page.query_selector("img[alt=\"Nom d'utilisateur\"]")
                        if el:
                            el.click()
                        page.wait_for_timeout(5000)
                        dump_all(page, "after_profile_pic_click")
                        screen = detect_screen(page, "after_profile_pic_click")
                        print(f"  [*] Screen after profile pic click: {screen}")
                        if screen == "stream":
                            print(f"\n  [*] Stream screen reached from livestream nav")
                            super_db.save_account(username, email, password, status="activated", obs="stream_from_livestream")
                            print("  [*] Clicking first image 4 times...")
                            page.wait_for_timeout(500)
                            for _ in range(4):
                                click_image_match(page, os.path.join(os.path.dirname(__file__), "src", "first.png"), "first", threshold=0.7)
                                page.wait_for_timeout(100)
                            page.wait_for_timeout(500)
                            dump_all(page, "after_stream_clicks")
                            type_test_chat(page)
                        cleanup()
                        # input("  [+] Done — press Enter to exit")
                        return
                if not screen:
                    for retry in range(3):
                        print(f"  [*] Screen is None — sleeping 3s and re-checking (attempt {retry+1}/3)")
                        page.wait_for_timeout(3000)
                        screen = detect_screen(page, f"after_gender_retry_{retry+1}")
                        print(f"  [*] Screen after gender retry {retry+1}: {screen}")
                        if screen:
                            break
                    if not screen:
                        fail("step 4c — no screen detected after gender")

            if screen == "messages":
                print(f"\n  [*] Step 4d: Messages screen detected — registration complete")
                print("  [*] Visiting profile...")
                for _retry in range(3):
                    try:
                        page.goto("https://superlive.chat/fr/profile/49194780", wait_until="load", timeout=120000)
                        break
                    except Exception as _e:
                        print(f"  [!] Profile nav failed (retry {_retry+1}/3): {_e}")
                        page.wait_for_timeout(5000)
                page.wait_for_timeout(3000)
                dump_all(page, "profile")
                screen = detect_screen(page, "after_profile_nav")
                print(f"  [*] Screen after profile nav: {screen}")
                if screen is None:
                    print("  [*] Screen was None, waiting 5s and retrying...")
                    page.wait_for_timeout(5000)
                    dump_all(page, "profile_retry")
                    screen = detect_screen(page, "profile_retry")
                    print(f"  [*] Screen after retry: {screen}")

            if screen == "profile":
                print(f"\n  [*] Step 4e: Profile screen detected — account activated")
                super_db.save_account(username, email, password, status="activated", obs="profile_reached")
                print("  [*] Account saved to DB with status=activated")
                print("  [*] Clicking profile picture to go live...")
                el = page.query_selector("img[alt=\"Nom d'utilisateur\"]")
                if el:
                    el.click()
                page.wait_for_timeout(5000)
                dump_all(page, "after_profile_pic_click")
                screen = detect_screen(page, "after_profile_pic_click")
                print(f"  [*] Screen after profile pic click: {screen}")

            if screen == "stream":
                print(f"\n  [*] Step 4f: Stream screen detected")
                super_db.save_account(username, email, password, status="activated", obs="stream_reached")
                print("  [*] Account saved to DB with status=activated")
                print("  [*] Clicking first image 4 times...")
                page.wait_for_timeout(500)
                for _ in range(4):
                    click_image_match(page, os.path.join(os.path.dirname(__file__), "src", "first.png"), "first", threshold=0.7)
                    page.wait_for_timeout(100)
                page.wait_for_timeout(500)
                dump_all(page, "after_stream_clicks")
                type_test_chat(page)
                cleanup()

            if screen == "reg_form":
                print(f"\n  [*] Step 5: Filling registration form")
                fill_reg_form(page, email, password)
                page.wait_for_timeout(3000)
                dump_all(page, "after_reg_form")
                screen = detect_screen(page, "after_reg_form")
                print(f"  [*] Screen after reg form: {screen}")
                if screen == "otp":
                    print(f"\n  [*] Step 4b: OTP screen detected after reg form")
                    fill_otp(page, email)
                    page.wait_for_timeout(3000)
                    dump_all(page, "after_otp_from_reg")
                    screen = detect_screen(page, "after_otp_from_reg")
                    print(f"  [*] Screen after OTP: {screen}")
                    if screen == "otp":
                        print("  [*] Still on OTP screen — polling for verify button or captcha")
                        for attempt in range(3):
                            poll_deadline = time.time() + 25
                            while time.time() < poll_deadline:
                                has_bframe = page.evaluate("""() => !!document.querySelector('iframe[src*="recaptcha/enterprise/bframe"], iframe[src*="recaptcha/api2/bframe"]')""")
                                if has_bframe:
                                    print("  [*] Captcha appeared while waiting for verify")
                                    solve_captcha(page)
                                    page.wait_for_timeout(2000)
                                    after_c = identify_screen(page)
                                    if after_c and after_c != "otp" and after_c != "captcha":
                                        screen = after_c
                                        print(f"  [*] Screen after captcha solve: {screen}")
                                    break
                                verify_btn = page.query_selector("button:has-text('Verify'), button:has-text('Vérifier'), button[type='submit']")
                                if verify_btn:
                                    ready = page.evaluate("""(b) => {
                                        if (b.disabled) return false;
                                        if (b.className.includes('opacity-50') || b.className.includes('cursor-not-allowed')) return false;
                                        if (b.querySelector('.animate-spin, .spinner, [class*="spinner"]')) return false;
                                        return true;
                                    }""", verify_btn)
                                    if ready:
                                        print("  [*] Clicking verify button...")
                                        click_verify_and_wait(page, verify_btn)
                                        break
                                cur = identify_screen(page)
                                if cur and cur != "otp":
                                    screen = cur
                                    print(f"  [*] Screen changed while waiting: {screen}")
                                    break
                                page.wait_for_timeout(500)
                            page.wait_for_timeout(3000)
                            dump_all(page, f"after_otp_retry_{attempt+1}")
                            screen = detect_screen(page, f"after_otp_retry_{attempt+1}")
                            print(f"  [*] Screen after OTP retry {attempt+1}: {screen}")
                            if screen != "otp":
                                break
                    if screen == "gender":
                        print(f"\n  [*] Step 4c: Gender screen detected after OTP")
                        if not find_and_click(page, "Homme", ["homme"]):
                            fail("step 4c — Homme button not found")
                        page.wait_for_timeout(1000)
                        if not find_and_click(page, "Confirmer", ["confirmer", "confirm"]):
                            fail("step 4c — Confirmer button not found")
                        page.wait_for_timeout(3000)
                        dump_all(page, "after_gender_from_reg")
                        screen = detect_screen(page, "after_gender_from_reg")
                        print(f"  [*] Screen after gender: {screen}")
                    if screen == "messages":
                        print(f"\n  [*] Messages screen detected after reg flow")
                        print("  [*] Visiting profile...")
                        for _retry in range(3):
                            try:
                                page.goto("https://superlive.chat/fr/profile/49194780", wait_until="load", timeout=120000)
                                break
                            except Exception as _e:
                                print(f"  [!] Profile nav failed (retry {_retry+1}/3): {_e}")
                                page.wait_for_timeout(5000)
                        page.wait_for_timeout(3000)
                        dump_all(page, "profile_from_reg")
                        screen = detect_screen(page, "after_profile_from_reg")
                        print(f"  [*] Screen after profile nav: {screen}")
                        if screen is None:
                            print("  [*] Screen was None, waiting 5s and retrying...")
                            page.wait_for_timeout(5000)
                            dump_all(page, "profile_retry_from_reg")
                            screen = detect_screen(page, "profile_retry_from_reg")
                            print(f"  [*] Screen after retry: {screen}")
                    if screen == "profile":
                        print(f"\n  [*] Profile screen detected after reg flow")
                        super_db.save_account(username, email, password, status="activated", obs="profile_reached")
                        print("  [*] Account saved to DB with status=activated")
                        print("  [*] Clicking profile picture to go live...")
                        el = page.query_selector("img[alt=\"Nom d'utilisateur\"]")
                        if el:
                            el.click()
                        page.wait_for_timeout(5000)
                        dump_all(page, "after_profile_pic_click")
                        screen = detect_screen(page, "after_profile_pic_click")
                        print(f"  [*] Screen after profile pic click: {screen}")
                        if screen == "stream":
                            print(f"\n  [*] Stream screen reached from livestream nav")
                            super_db.save_account(username, email, password, status="activated", obs="stream_from_livestream")
                            print("  [*] Clicking first image 4 times...")
                            page.wait_for_timeout(500)
                            for _ in range(4):
                                click_image_match(page, os.path.join(os.path.dirname(__file__), "src", "first.png"), "first", threshold=0.7)
                                page.wait_for_timeout(100)
                            page.wait_for_timeout(500)
                            dump_all(page, "after_stream_clicks")
                            type_test_chat(page)
                        cleanup()
                        return
                if not screen:
                    fail("step 5 — no screen detected after reg form")

            print(f"\n  [+] Registration flow complete — all steps passed")
            cleanup()
    finally:
        if args.nordvpn:
            vpn.disconnect()
            print("  [+] VPN disconnected")


if __name__ == "__main__":
    run()
