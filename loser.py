import json
import os
import random
import time
from pathlib import Path

import numpy as np
import cv2
import requests
import speech_recognition as sr
from pydub import AudioSegment

from camoufox import Camoufox, DefaultAddons
from camoufox.utils import launch_options
from get_2FA import get_2fa

result_dir = Path("results")
result_dir.mkdir(parents=True, exist_ok=True)

DOMAINS = [
    "alpha804.eu.org", "alpha-sig.eu.org", "beta-sig.eu.org",
    "bitcoin-plazza.eu.org", "c0rner-bit.eu.org", "dark0s-market.eu.org",
    "gamma-sig.eu.org", "iblogg.eu.org", "lg-salmi.nl.eu.org",
    "m0rd05.eu.org", "sec4891.eu.org", "techstreet07.eu.org",
    "vaya.eu.org",  "ziw05tempemail.eu.org",
    "ziw0tempemail.eu.org",
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
    geoip=True, humanize=0.1, block_webrtc=True,
    block_images=False, disable_coop=True,
    main_world_eval=True, window=(1280, 720), debug=True,
    locale="fr-FR",
    exclude_addons=[DefaultAddons.UBO],
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


def find_and_click(page, label, keywords):
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
        return True
    print(f"  [!] {label} not found")
    return False


def click_selector(page, selector, index=0):
    try:
        el = page.locator(selector).nth(index)
        if el.count() > index:
            el.click()
            print(f"  [*] Clicked selector '{selector}' [{index}]")
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


def fill_field(page, value, selectors):
    for sel in selectors:
        if fill_input(page, sel, value):
            return True
    return False


def wait_until_gone(page, check, timeout=8):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not check(page):
            return True
        page.wait_for_timeout(1000)
    return False

def wait_until_next_step(page, old_check, new_check, timeout=8):
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
    page.wait_for_timeout(500)
    return True


def click_captcha_image(page):
    return click_image_match(page, "src/captcha.png", "captcha")


def click_p_email_image(page):
    return click_image_match(page, "src/p_email.png", "p_email")


def solve_audio_challenge(page, frame, retries=3):
    print(f"  [*] Solving audio challenge...")
    page.wait_for_timeout(500)
    audio_url = None
    for attempt in range(5):
        audio_url = frame.evaluate("""() => {
            const audio = document.querySelector('audio');
            if (!audio) return null;
            const src = audio.querySelector('source');
            return src ? src.src : audio.src;
        }""")
        if audio_url:
            break
        page.wait_for_timeout(500)
        print(f"  [*] Waiting for audio element (attempt {attempt+1})...")
    if not audio_url:
        print(f"  [!] Could not extract audio URL")
        return False
    print(f"  [*] Audio URL: {audio_url[:120]}...")
    mp3_path = "/tmp/recaptcha_audio.mp3"
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
        return False
    wav_path = "/tmp/recaptcha_audio.wav"
    try:
        AudioSegment.from_mp3(mp3_path).export(wav_path, format="wav")
    except Exception as e:
        print(f"  [!] Conversion failed: {e}")
        return False
    try:
        r = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            r.adjust_for_ambient_noise(source, duration=0.5)
            data = r.record(source)
        text = r.recognize_google(data, language="fr-FR")
        print(f"  [*] Transcribed: {text}")
    except Exception as e:
        print(f"  [!] Transcription failed: {e}")
        return False
    try:
        input_el = frame.wait_for_selector(
            "#audio-response, input[type='text'], .rc-audiochallenge-response-input",
            timeout=5000
        )
        if input_el:
            input_el.fill(text)
            print(f"  [*] Typed response: {text}")
        else:
            print(f"  [!] Response input not found")
            return False
    except Exception as e:
        print(f"  [!] Could not fill response: {e}")
        return False
    try:
        verify_btn = frame.wait_for_selector(
            "#recaptcha-verify-button, button[type='submit'], .verify-button",
            timeout=5000
        )
        if verify_btn:
            verify_btn.click()
            print(f"  [*] Clicked verify button")
            page.wait_for_timeout(2500)
        else:
            print(f"  [!] Verify button not found")
            return False
    except Exception as e:
        print(f"  [!] Could not click verify: {e}")
        return False
    if retries > 0 and click_image_match(page, "results/eyes.png", "eyes_verification", threshold=0.7, click_on_match=False):
        print(f"  [*] Eyes icon detected — new challenge appeared, solving audio again ({retries-1} retries left)")
        return solve_audio_challenge(page, frame, retries=retries - 1)
    for p in [mp3_path, wav_path]:
        try:
            os.remove(p)
        except Exception:
            pass
    return True


def handle_captcha(page):
    print(f"  [*] Searching for captcha...")
    image_match_clicked = click_captcha_image(page)
    if image_match_clicked:
        found_captcha = "image match"
    else:
        captcha_keywords = [
            'captcha', 'recaptcha', 'g-recaptcha', 'hcaptcha', 'turnstile',
            'cf-turnstile', 'challenge',
        ]
        found_captcha = page.evaluate(f"""() => {{
            const keywords = {captcha_keywords};
            const badge = document.querySelector('.grecaptcha-badge');
            if (badge) return 'grecaptcha-badge found';
            const turnstile = document.querySelector('.cf-turnstile, .cf-turnstile-wrapper');
            if (turnstile) return 'cf-turnstile found';
            const iframes = document.querySelectorAll('iframe');
            for (const f of iframes) {{
                const src = (f.src || '').toLowerCase();
                for (const kw of keywords) {{
                    if (src.includes(kw)) return 'captcha iframe: ' + src.slice(0, 100);
                }}
            }}
            const hcaptcha = document.querySelector('.h-captcha');
            if (hcaptcha) return 'hcaptcha found';
            const all = document.querySelectorAll('[class*=\"captcha\" i], [id*=\"captcha\" i]');
            if (all.length > 0) return 'captcha element: ' + all[0].outerHTML.slice(0, 100);
            return null;
        }}""")
    if not found_captcha:
        print(f"  [*] No captcha detected, checking for OTP...")
        otp_detected = page.evaluate("""(arabic) => {
            const otpInput = document.querySelector(`#otp-code-0, input[autocomplete='one-time-code']`);
            if (otpInput) return true;
            const header = document.body.innerText.includes(arabic) || document.body.innerText.includes('verification code');
            if (header) return true;
            return false;
        }""", "أدخل رمز التحقق")
        if otp_detected:
            print(f"  [*] OTP verification screen detected")
            return "otp"
        return False
    print(f"  [*] Captcha detected: {found_captcha}")
    print(f"  [*] Captcha present — will trigger via form submit button")
    iframe_info = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('iframe')).map(f => ({
            src: (f.src || '').slice(0, 150),
            title: f.title,
            width: f.width,
            height: f.height,
            id: f.id,
            visible: f.offsetWidth > 0 && f.offsetHeight > 0,
            rect: f.getBoundingClientRect(),
        }));
    }""")
    recaptcha_iframes = [i for i in iframe_info if 'recaptcha' in i['src']]
    if recaptcha_iframes:
        print(f"  [*] Found {len(recaptcha_iframes)} recaptcha iframes:")
        for i, info in enumerate(recaptcha_iframes):
            print(f"      [{i}] {info['src'][:100]} | {info['width']}x{info['height']} visible={info['visible']}")
    else:
        print(f"  [*] No recaptcha iframes found on page")
        print(f"  [*] All iframes: {[i['src'][:80] for i in iframe_info]}")
    clicked_checkbox = False
    if image_match_clicked:
        print(f"  [*] Image match clicked a captcha element — checking for challenge...")
        page.wait_for_timeout(1000)
        try:
            challenge_frame = page.wait_for_selector(
                "iframe[src*='recaptcha/enterprise/bframe'], iframe[src*='recaptcha/api2/bframe']",
                timeout=3000
            )
            if challenge_frame:
                clicked_checkbox = True
                print(f"  [*] Challenge iframe appeared after image click")
        except Exception:
            print(f"  [*] No challenge iframe — treating as invisible recaptcha")
    if not clicked_checkbox and recaptcha_iframes:
        is_invisible = len([i for i in recaptcha_iframes if 'size=invisible' in i['src']]) > 0 or len(recaptcha_iframes) <= 2
        if is_invisible:
            print(f"  [*] Invisible reCAPTCHA — checking for tokens...")
            tokens = page.evaluate("() => Array.from(document.querySelectorAll('.g-recaptcha-response')).map(t => t.value)")
            filled = [t for t in tokens if t]
            if filled:
                print(f"  [*] Tokens already present ({len(filled)}/{len(tokens)})")
                return True
            print(f"  [*] Waiting for grecaptcha.execute() to generate tokens...")
            for wait_i in range(15):
                page.wait_for_timeout(1000)
                tokens = page.evaluate("() => Array.from(document.querySelectorAll('.g-recaptcha-response')).map(t => t.value)")
                filled = [t for t in tokens if t]
                if filled:
                    print(f"  [*] Tokens generated ({len(filled)}/{len(tokens)}) after {wait_i+1}s")
                    return True
            print(f"  [!] No tokens appeared — execute may have failed")
            return False
    for sel in [
        "iframe[src*='recaptcha/enterprise/anchor']:not([src*='size=invisible'])",
        "iframe[src*='recaptcha/enterprise/anchor']",
        "iframe[src*='recaptcha'][title='reCAPTCHA']",
        "iframe[src*='recaptcha']",
        ".grecaptcha-badge",
    ]:
        try:
            el = page.wait_for_selector(sel, timeout=3000)
            if el:
                box = el.bounding_box()
                if box and box['width'] > 0 and box['height'] > 0:
                    x = box['x'] + 20
                    y = box['y'] + box['height'] / 2
                    page.mouse.click(x, y)
                    page.wait_for_timeout(1000)
                    clicked_checkbox = True
                    break
        except Exception:
            continue
    if not clicked_checkbox:
        if recaptcha_iframes:
            reg_iframes = [i for i in recaptcha_iframes if '6Ld9_e8s' in i['src']]
            info = reg_iframes[0] if reg_iframes else recaptcha_iframes[0]
            if info['rect']:
                x = info['rect']['x'] + 20
                y = info['rect']['y'] + info['rect']['height'] / 2
                page.mouse.click(x, y)
                print(f"  [*] Clicked recaptcha iframe at ({x:.0f}, {y:.0f})")
                page.wait_for_timeout(1000)
                clicked_checkbox = True
        if not clicked_checkbox:
            print(f"  [*] Could not click any recaptcha iframe")
    if clicked_checkbox:
        print(f"  [*] Looking for challenge frame...")
        page.wait_for_timeout(500)
        frame = None
        for f in page.frames:
            if 'bframe' in f.url and 'recaptcha' in f.url:
                frame = f
                break
        if not frame:
            try:
                page.wait_for_selector(
                    "iframe[src*='recaptcha/enterprise/bframe'], iframe[src*='recaptcha/api2/bframe']",
                    state="attached", timeout=3000
                )
                for f in page.frames:
                    if 'bframe' in f.url and 'recaptcha' in f.url:
                        frame = f
                        break
            except Exception:
                pass
        if frame:
            print(f"  [*] Found challenge frame: {frame.url[:100]}...")
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
            page.wait_for_timeout(500)
            frame_html = frame.evaluate("() => document.documentElement.outerHTML")
            challenge_path = result_dir / f"challenge_frame.html"
            challenge_path.write_text(frame_html, encoding="utf-8")
            print(f"  [*] Challenge frame HTML saved ({len(frame_html)} chars)")
            audio_clicked = False
            for audio_sel in [
                "#recaptcha-audio-button:not([disabled])",
                "#recaptcha-audio-button",
                "button.rc-button-audio:not([disabled])",
                "button[aria-label*='audio' i]",
                "button[aria-label*='son' i]",
                "button[aria-label*='défi audio' i]",
                "button[aria-label*='défi sonore' i]",
                "button[aria-label*='صوت' i]",
                "button[aria-label*='سمعي' i]",
                "button#recaptcha-audio-button",
            ]:
                try:
                    btn = frame.wait_for_selector(audio_sel, timeout=3000)
                    if btn:
                        btn.click()
                        print(f"  [*] Clicked audio challenge button: {audio_sel}")
                        page.wait_for_timeout(1000)
                        solve_audio_challenge(page, frame)
                        audio_clicked = True
                        break
                except Exception:
                    continue
            if not audio_clicked:
                print(f"  [*] Audio button not found — trying verify/continue button...")
                for verify_sel in [
                    "#recaptcha-verify-button:not([disabled])",
                    "#recaptcha-verify-button",
                    "button[aria-label*='vérifier' i]",
                    "button[aria-label*='verify' i]",
                    "button[aria-label*='submit' i]",
                    "button.rc-button-default:not([disabled])",
                    "button.rc-button-default",
                    "#verify-button:not([disabled])",
                    "button:not([disabled])",
                ]:
                    try:
                        btn = frame.wait_for_selector(verify_sel, timeout=2000)
                        if btn and btn.is_visible():
                            btn.click()
                            print(f"  [*] Clicked verify button: {verify_sel}")
                            page.wait_for_timeout(1500)
                            break
                    except Exception:
                        continue
        else:
            print(f"  [*] No challenge frame detected")
            otp_detected = page.evaluate("""(arabic) => {
                const otpInput = document.querySelector(`#otp-code-0, input[autocomplete='one-time-code']`);
                if (otpInput) return true;
                if (document.body.innerText.includes(arabic)) return true;
                return false;
            }""", "أدخل رمز التحقق")
            if otp_detected:
                print(f"  [*] OTP verification screen detected instead of captcha")
                return "otp"
    else:
        print(f"  [*] Skipping audio button (checkbox not clicked)")
    return True


def fill_otp(page, email):
    print(f"  [*] Fetching OTP code from email...")
    code = get_2fa(email, retries=15, delay=4)
    if not code:
        print("  [!] Failed to get OTP code")
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
            return True
    except Exception:
        pass
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
    page.wait_for_timeout(500)
    return True


print("=" * 60)
print("  LOST – dump HTML elements from superlive.chat")
print("=" * 60)

username, email, password = generate_credentials()
print(f"\n  [*] Username: {username}")
print(f"  [*] Email:    {email}")
print(f"  [*] Password: {password}")

with Camoufox(**opts) as browser:
    page = browser.new_page()
    page.set_default_timeout(30000)
    page.set_viewport_size({"width": 1280, "height": 720})

    print(f"\n  [+] Navigating to https://superlive.chat/fr/nonlogin-messages")
    MAX_RETRIES = 3
    for nav_attempt in range(1, MAX_RETRIES + 1):
        page.goto("https://superlive.chat/fr/nonlogin-messages", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)
        found_btn = False
        for _ in range(30):
            has_btn = page.evaluate("""() => {
                const all = document.querySelectorAll('button, a, [role="button"]');
                for (const el of all) {
                    const text = (el.textContent || '').trim().toLowerCase();
                    if ((text.includes("s'inscrire") || text.includes("s’inscrire")) && el.offsetHeight > 0)
                        return true;
                }
                return false;
            }""")
            if has_btn:
                found_btn = True
                break
            page.wait_for_timeout(500)
        if found_btn:
            print(f"  [*] Page loaded — S'inscrire button found")
            page.wait_for_timeout(2000)
            break
        if nav_attempt < MAX_RETRIES:
            print(f"  [!] S'inscrire not found on attempt {nav_attempt}/{MAX_RETRIES}, reloading...")
        else:
            print(f"  [!] S'inscrire not found after {MAX_RETRIES} reloads, proceeding anyway...")

    # ── Step 1: dump initial page state ──
    print(f"\n{'='*60}")
    print("  STEP 1: dumping initial page state")
    print(f"{'='*60}")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(1000)
    dump_all(page, "step1")
    print(f"  [+] Step 1 dumps saved to {result_dir}/")
    page.wait_for_timeout(3000)

    # ── Step 2: click S'inscrire, wait, dump ──
    print(f"\n{'='*60}")
    print("  STEP 2: clicking S'inscrire and dumping")
    print(f"{'='*60}")
    print(f"\n  [+] Looking for 'S'inscrire' button...")
    clicked = click_text(page, "S'inscrire")
    page.wait_for_timeout(1500)
    ok = wait_until_next_step(
        page,
        old_check=lambda p: p.evaluate("() => [...document.querySelectorAll('button, a, span, div')].some(el => el.offsetHeight > 0 && el.textContent.trim().includes(\"S'inscrire\"))"),
        new_check=lambda p: p.evaluate("() => !!document.querySelector('button[class*=\"border-unique-label-100\"]')"),
    )
    if not ok:
        print(f"  [!] No signup modal appeared — retrying...")
        click_text(page, "S'inscrire")
        page.wait_for_timeout(3000)
    dump_all(page, "step2")
    print(f"  [+] Step 2 dumps saved to {result_dir}/")
    page.wait_for_timeout(3000)

    # ── Step 3: click "Poursuivre avec Email", wait, dump ──
    print(f"\n{'='*60}")
    print("  STEP 3: clicking email signup button and dumping")
    print(f"{'='*60}")
    print(f"\n  [+] Looking for email signup button...")
    clicked_email = False
    deadline = time.time() + 15
    while time.time() < deadline:
        btn = page.evaluate("""() => {
            const all = document.querySelectorAll('button, a, [role="button"]');
            for (const el of all) {
                const text = (el.textContent || '').trim().toLowerCase();
                if (text.includes('poursuivre avec email') && el.offsetHeight > 0)
                    return el.outerHTML.slice(0, 200);
            }
            return null;
        }""")
        if btn:
            clicked = click_text(page, "Poursuivre avec Email")
            if clicked:
                clicked_email = True
                break
        page.wait_for_timeout(500)
    if not clicked_email:
        print(f"  [!] Could not find or click 'Poursuivre avec Email'")
    page.wait_for_timeout(1500)
    if clicked_email:
        ok = wait_until_next_step(
            page,
            old_check=lambda p: p.evaluate("() => [...document.querySelectorAll('button, a, span, div')].some(el => el.offsetHeight > 0 && el.textContent.trim().includes('Poursuivre avec Email'))"),
            new_check=lambda p: p.evaluate("() => !!document.querySelector('#email, #otp-email')"),
        )
        if not ok:
            print(f"  [!] Email signup form not detected — retrying...")
            click_text(page, "Poursuivre avec Email")
            page.wait_for_timeout(1500)
    dump_all(page, "step3")
    print(f"  [+] Step 3 dumps saved to {result_dir}/")
    page.wait_for_timeout(3000)

    # ── Step 4: click "S'enregistrer avec l'adresse e-mail", wait, dump ──
    print(f"\n{'='*60}")
    print("  STEP 4: clicking register-with-email and dumping")
    print(f"{'='*60}")
    register_btn_exists = page.evaluate("""() => {
        const all = document.querySelectorAll('button, a, [role="button"]');
        for (const el of all) {
            if (el.offsetHeight === 0) continue;
            const text = el.textContent.toLowerCase().trim();
            if (text.includes("s'enregistrer avec l'adresse e-mail") || text.includes("s'enregistrer avec")) {
                return true;
            }
        }
        return false;
    }""")
    if not register_btn_exists:
        print(f"  [!] 'S'enregistrer avec l'adresse e-mail' button not found — dumping state")
        dump_all(page, "step4_missing")
    find_and_click(page, "register with email", [
        "s'enregistrer avec l'adresse e-mail",
        "s'enregistrer avec",
        "enregistrer avec l'adresse e-mail"
    ])
    page.wait_for_timeout(1500)
    ok = wait_until_next_step(
        page,
        old_check=lambda p: p.evaluate("() => [...document.querySelectorAll('button, a, span, div')].some(el => el.offsetHeight > 0 && (el.textContent.toLowerCase().includes('enregistrer avec')))"),
        new_check=lambda p: p.evaluate("() => !!document.querySelector('#otp-email, #email')"),
    )
    if not ok:
        print(f"  [!] Registration form not detected — retrying click...")
        find_and_click(page, "register with email", [
            "s'enregistrer avec l'adresse e-mail",
            "s'enregistrer avec",
            "enregistrer avec l'adresse e-mail"
        ])
        page.wait_for_timeout(1500)
    dump_all(page, "step4")
    print(f"  [+] Step 4 dumps saved to {result_dir}/")
    page.wait_for_timeout(3000)

    # ── Step 5: fill #otp-email with generated email, dump ──
    print(f"\n{'='*60}")
    print("  STEP 5: filling email input and dumping")
    print(f"{'='*60}")
    if not fill_field(page, email, ["#otp-email", "#email", "input[name='email']", "input[type='email']"]):
        dump_all(page, "step5_fail")
    page.wait_for_timeout(500)
    dump_all(page, "step5")
    print(f"  [+] Step 5 dumps saved to {result_dir}/")
    page.wait_for_timeout(3000)

    # ── Step 6: fill registration form (two-stage), click Continuer, dump ──
    print(f"\n{'='*60}")
    print("  STEP 6: filling registration form and continuing")
    print(f"{'='*60}")
    email_selectors = ["#email", "input[name='email']", "input[type='email']", "input[placeholder*='email' i]", "input[placeholder*='e-mail' i]"]
    pass_selectors = ["#password", "input[name='password']", "input[type='password']"]
    pass2_selectors = ["#passwordRepeat", "#password2", "input[name='passwordRepeat']", "input[name='password2']", "input[placeholder*='confirm' i]"]
    def otp_dialog_visible(p):
        return bool(p.evaluate("""() => {
            const otp = document.querySelector('#otp-code-0, input[autocomplete="one-time-code"]');
            if (otp) return true;
            return document.body.innerText.includes('code de vérification') || document.body.innerText.includes('verification code');
        }"""))
    has_password = page.evaluate("() => !!document.querySelector('#password')")
    if has_password:
        print(f"  [*] Password field found — filling all fields")
        if not fill_field(page, email, email_selectors):
            dump_all(page, "step6_fill_email_fail")
        fill_field(page, password, pass_selectors)
        fill_field(page, password, pass2_selectors)
    else:
        print(f"  [*] Password field NOT found — filling email first")
        if not fill_field(page, email, email_selectors):
            dump_all(page, "step6_fill_email_fail")
        find_and_click(page, "Continuer/Submit email", [
            "continuer", "continue", "suivant", "next", "إرسال", "submit"
        ])
        otp_found = False
        for _ in range(12):
            page.wait_for_timeout(1000)
            if otp_dialog_visible(page):
                otp_found = True
                break
        if otp_found:
            for otp_attempt in range(2):
                print(f"  [*] OTP dialog detected — fetching code (attempt {otp_attempt+1})...")
                code = get_2fa(email, retries=8, delay=4)
                if code:
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
                    print(f"  [*] Filled {fields_filled}/6 OTP digit fields")
                    find_and_click(page, "OTP Verify", ['تحقق', 'verify', 'vérifier', 'التالي', 'submit', 'إرسال'])
                    page.wait_for_timeout(2000)
                    wait_until_gone(page, lambda p: bool(
                        p.evaluate("() => document.querySelector('#otp-code-0, input[autocomplete=\"one-time-code\"]')")
                    ))
                    print(f"  [*] OTP fields gone — verification submitted")
                    page.wait_for_timeout(1500)
                    break
                else:
                    print(f"  [!] Failed to get OTP code — clicking resend...")
                    click_text(page, "Renvoyer le code")
                    page.wait_for_timeout(2000)
            else:
                print(f"  [!] All OTP fetch attempts failed")
        print(f"  [*] Now filling password fields")
        for _ in range(10):
            has_pw = page.evaluate("() => !!document.querySelector('#password, input[name=\"password\"]')")
            if has_pw:
                break
            page.wait_for_timeout(1000)
        fill_field(page, password, pass_selectors)
        fill_field(page, password, pass2_selectors)

    find_and_click(page, "Continuer", [
        "continuer", "continue", "suivant", "next", "إرسال", "submit"
    ])
    page.wait_for_timeout(3000)
    ok = wait_until_next_step(
        page,
        old_check=lambda p: bool(p.evaluate("() => [...document.querySelectorAll('button, a')].some(el => el.offsetHeight > 0 && ['continuer', 'continue', 'suivant', 'next'].some(k => el.textContent.trim().toLowerCase().includes(k)))")),
        new_check=lambda p: bool(p.evaluate("() => !document.querySelector('#email, #password')")),
    )
    if not ok:
        print(f"  [!] Form still visible — retrying click...")
        find_and_click(page, "Continuer", [
            "continuer", "continue", "suivant", "next", "إرسال", "submit"
        ])
        page.wait_for_timeout(2000)
    dump_all(page, "step6")
    print(f"  [+] Step 6 dumps saved to {result_dir}/")
    page.wait_for_timeout(3000)

    # ── Step 7: handle captcha/OTP, dump ──
    print(f"\n{'='*60}")
    print("  STEP 7: handling captcha/OTP and dumping")
    print(f"{'='*60}")
    page.wait_for_timeout(2500)
    max_attempts = 4
    for attempt in range(1, max_attempts + 1):
        print(f"  [*] Captcha check attempt {attempt}/{max_attempts}")
        result = handle_captcha(page)
        if result == "otp":
            print(f"  [*] OTP step reached — fetching and filling code...")
            fill_otp(page, email)
            find_and_click(page, "OTP continue/verify button",
                keywords=['تحقق', 'verify', 'continue', 'التالي', 'submit', 'إرسال'])
            page.wait_for_timeout(1500)
            wait_until_gone(page, lambda p: bool(
                p.evaluate("() => document.querySelector('#otp-code-0, input[autocomplete=\"one-time-code\"]')")
            ))
            print(f"  [*] OTP fields gone — verification submitted")
            page.wait_for_timeout(1000)
            print(f"  [*] Filling registration form after OTP verification...")
            fill_field(page, email, ["#email", "input[name='email']", "input[type='email']", "input[placeholder*='email' i]", "input[placeholder*='e-mail' i]"])
            fill_field(page, password, ["#password", "input[name='password']", "input[type='password']"])
            fill_field(page, password, ["#passwordRepeat", "#password2", "input[name='passwordRepeat']", "input[name='password2']", "input[placeholder*='confirm' i]"])
        if result:
            print(f"  [*] Submitting form to trigger captcha...")
            find_and_click(page, "Continuer", [
                "continuer", "continue", "suivant", "next", "إرسال", "submit"
            ])
            page.wait_for_timeout(3000)
            form_gone = page.evaluate("() => !document.querySelector('#email, #password')")
            if form_gone:
                print(f"  [*] Form gone — submission likely succeeded")
                break
            challenge_frame = None
            for f in page.frames:
                if 'bframe' in f.url and 'recaptcha' in f.url:
                    challenge_frame = f
                    break
            if challenge_frame:
                print(f"  [*] Challenge frame detected: {challenge_frame.url[:80]}...")
                try:
                    challenge_frame.wait_for_load_state("domcontentloaded", timeout=3000)
                except Exception:
                    pass
                frame_html = challenge_frame.evaluate("() => document.documentElement.outerHTML")
                challenge_path = result_dir / f"challenge_{attempt}.html"
                challenge_path.write_text(frame_html, encoding="utf-8")
                print(f"  [*] Challenge frame HTML saved ({len(frame_html)} chars)")
                audio_clicked = False
                for audio_sel in [
                    "#recaptcha-audio-button:not([disabled])",
                    "#recaptcha-audio-button",
                    "button.rc-button-audio:not([disabled])",
                    "button[aria-label*='audio' i]",
                    "button[aria-label*='son' i]",
                    "button[aria-label*='défi audio' i]",
                    "button[aria-label*='défi sonore' i]",
                    "button[aria-label*='صوت' i]",
                    "button[aria-label*='سمعي' i]",
                    "button#recaptcha-audio-button",
                ]:
                    try:
                        btn = challenge_frame.wait_for_selector(audio_sel, timeout=3000)
                        if btn and btn.is_visible():
                            btn.click()
                            print(f"  [*] Clicked audio challenge button: {audio_sel}")
                            page.wait_for_timeout(1000)
                            solve_audio_challenge(page, challenge_frame)
                            audio_clicked = True
                            break
                    except Exception:
                        continue
                if not audio_clicked:
                    print(f"  [*] Finput challenge (no buttons) — waiting for auto-resolution...")
                    for wait_s in range(20):
                        page.wait_for_timeout(1000)
                        tokens = page.evaluate("() => Array.from(document.querySelectorAll('.g-recaptcha-response')).map(t => t.value)")
                        filled = [t for t in tokens if t]
                        if len(filled) >= 2:
                            print(f"  [*] Fallback captcha token appeared after {wait_s+1}s")
                            break
                        form_gone = page.evaluate("() => !document.querySelector('#email, #password')")
                        if form_gone:
                            print(f"  [*] Form gone after challenge — registration succeeded")
                            break
                    else:
                        print(f"  [*] Fallback challenge not resolved — trying grecaptcha.execute()")
                        page.evaluate("mw:() => { try { grecaptcha.enterprise.execute(); } catch(e) { try { grecaptcha.execute(); } catch(e2) {} } }")
                        page.wait_for_timeout(3000)
                try:
                    page.wait_for_timeout(2000)
                    form_gone = page.evaluate("() => !document.querySelector('#email, #password')")
                    if form_gone:
                        print(f"  [*] Form gone after challenge — registration succeeded")
                        break
                except Exception as e:
                    print(f"  [*] Page navigated after challenge (likely success): {e}")
                    break
            else:
                print(f"  [*] No challenge frame after clicking — trying again...")
        else:
            print(f"  [*] No captcha or OTP detected — checking page state")
            page.wait_for_timeout(3000)
            otp_now = page.evaluate("""() => {
                const otpInput = document.querySelector('#otp-code-0, input[autocomplete="one-time-code"]');
                if (otpInput) return true;
                return document.body.innerText.includes('أدخل رمز التحقق') || document.body.innerText.includes('verification code');
            }""")
            if otp_now:
                print(f"  [*] OTP detected — filling code...")
                fill_otp(page, email)
                find_and_click(page, "OTP continue/verify button",
                    keywords=['تحقق', 'verify', 'continue', 'التالي', 'submit', 'إرسال'])
                page.wait_for_timeout(1500)
                wait_until_gone(page, lambda p: bool(
                    p.evaluate("() => document.querySelector('#otp-code-0, input[autocomplete=\"one-time-code\"]')")
                ))
                print(f"  [*] OTP fields gone — verification submitted")
                page.wait_for_timeout(1000)
                print(f"  [*] Filling registration form after OTP verification...")
                fill_field(page, email, ["#email", "input[name='email']", "input[type='email']", "input[placeholder*='email' i]", "input[placeholder*='e-mail' i]"])
                fill_field(page, password, ["#password", "input[name='password']", "input[type='password']"])
                fill_field(page, password, ["#passwordRepeat", "#password2", "input[name='passwordRepeat']", "input[name='password2']", "input[placeholder*='confirm' i]"])
                continue
            form_gone = page.evaluate("() => !document.querySelector('#email, #password')")
            if form_gone:
                print(f"  [*] Registration form gone — submission likely succeeded")
                break
            print(f"  [*] Form still visible — submitting again...")
            find_and_click(page, "Continuer", [
                "continuer", "continue", "suivant", "next", "إرسال", "submit"
            ])
            page.wait_for_timeout(2500)
    dump_all(page, "step7")
    print(f"  [+] Step 7 dumps saved to {result_dir}/")
    page.wait_for_timeout(3000)

    page.wait_for_timeout(3000)
