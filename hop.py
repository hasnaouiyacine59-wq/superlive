import os
import random
from pathlib import Path

import numpy as np
import cv2
import requests
import speech_recognition as sr
from pydub import AudioSegment

from camoufox import Camoufox
from camoufox.utils import launch_options
from get_2FA import get_2fa

result_dir = Path("results")
result_dir.mkdir(parents=True, exist_ok=True)

DOMAINS = [
    "alpha804.eu.org", "alpha-sig.eu.org", "beta-sig.eu.org",
    "bitcoin-plazza.eu.org", "c0rner-bit.eu.org", "dark0s-market.eu.org",
    "gamma-sig.eu.org", "iblogg.eu.org", "lg-salmi.nl.eu.org",
    "m0rd05.eu.org", "sec4891.eu.org", "techstreet07.eu.org",
    "vaya.eu.org", "w0rld.int.eu.org", "ziw05tempemail.eu.org",
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
    geoip=True, humanize=True, block_webrtc=True,
    block_images=False, disable_coop=True,
    main_world_eval=True, window=(1280, 720), debug=True,
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
        page.wait_for_timeout(500)
        return True
    print(f"  [!] {label} not found")
    return False

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
        try:
            Path("results/recaptcha_audio_frame.html").write_text(frame.content())
            print(f"  [*] Saved audio challenge frame HTML")
        except Exception:
            pass
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

    # Check if a new challenge appeared (eyes icon)
    if retries > 0 and click_image_match(page, "results/eyes.png", "eyes_verification", threshold=0.7, click_on_match=False):
        print(f"  [*] Eyes icon detected — new challenge appeared, solving audio again ({retries-1} retries left)")
        return solve_audio_challenge(page, frame, retries=retries - 1)

    for p in [mp3_path, wav_path]:
        try:
            os.remove(p)
        except Exception:
            pass
    return True

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
    page.wait_for_timeout(1500)
    return True

def click_captcha_image(page):
    return click_image_match(page, "src/captcha.png", "captcha")

def click_p_email_image(page):
    return click_image_match(page, "src/p_email.png", "p_email")

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
    print(f"  [*] Triggering captcha...")
    grecaptcha_loaded = page.evaluate("mw:() => { return typeof grecaptcha !== 'undefined' && typeof grecaptcha.execute === 'function'; }")
    if grecaptcha_loaded:
        result = page.evaluate("mw:() => { try { if (grecaptcha.enterprise) { grecaptcha.enterprise.execute(); return 'enterprise.execute()'; } } catch(e) {} try { grecaptcha.execute(); return 'execute()'; } catch(e) {} try { grecaptcha.execute('6Ld9_e8sAAAAAIPwD7J3mrBiQno-h86lHiFfQ_Nk'); return 'execute(sitekey)'; } catch(e) {} return 'failed'; }")
        print(f"  [*] grecaptcha.{result}")
        page.wait_for_timeout(1500)
    else:
        print(f"  [*] grecaptcha not available in main world either, checking iframes...")
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
        clicked_checkbox = True
        print(f"  [*] Image match already clicked the captcha checkbox")
    elif len(recaptcha_iframes) <= 2:
        print("  [*] Only 2 recaptcha iframes present; skipping captcha handling")

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
                    # print(f"  [*] Clicked captcha element ({sel}) at ({x:.0f}, {y:.0f})")
                    page.wait_for_timeout(1500)
                    clicked_checkbox = True
                    break
        except Exception:
            continue
    if not clicked_checkbox:
        if recaptcha_iframes:
            info = recaptcha_iframes[0]
            if info['rect']:
                x = info['rect']['x'] + 20
                y = info['rect']['y'] + info['rect']['height'] / 2
                page.mouse.click(x, y)
                print(f"  [*] Clicked first recaptcha iframe at ({x:.0f}, {y:.0f})")
                page.wait_for_timeout(1500)
                clicked_checkbox = True
        if not clicked_checkbox:
            print(f"  [*] Could not click any recaptcha iframe")
    if clicked_checkbox:
        print(f"  [*] Looking for audio challenge button...")
        try:
            challenge_frame = page.wait_for_selector(
                "iframe[src*='recaptcha/enterprise/bframe'], iframe[src*='recaptcha/api2/bframe']",
                timeout=8000
            )
            if challenge_frame:
                print(f"  [*] Challenge iframe appeared")
                page.wait_for_timeout(500)
                frame = None
                for f in page.frames:
                    if 'bframe' in f.url and 'recaptcha' in f.url:
                        frame = f
                        break
                if frame:
                    print(f"  [*] Found challenge frame: {frame.url[:100]}...")
                    page.wait_for_timeout(500)
                    for audio_sel in [
                        "#recaptcha-audio-button:not([disabled])",
                        "#recaptcha-audio-button",
                        "button.rc-button-audio:not([disabled])",
                        "button[aria-label*='audio' i]",
                        "button[aria-label*='صوت' i]",
                        "button[aria-label*='سمعي' i]",
                        "button#recaptcha-audio-button",
                    ]:
                        try:
                            btn = frame.wait_for_selector(audio_sel, timeout=5000)
                            if btn:
                                btn.click()
                                print(f"  [*] Clicked audio challenge button: {audio_sel}")
                                page.wait_for_timeout(1500)
                                solve_audio_challenge(page, frame)
                                break
                        except Exception:
                            continue
                    else:
                        print(f"  [*] Audio button not found in challenge frame")
                        try:
                            Path("results/recaptcha_challenge_frame.html").write_text(frame.content())
                            print(f"  [*] Saved challenge frame HTML")
                        except Exception:
                            pass
                else:
                    print(f"  [*] Could not find challenge frame by URL")
        except Exception as e:
            print(f"  [*] Challenge iframe did not appear: {e}")
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

def fill_input(page, sel, value):
    for attempt in range(3):
        try:
            el = page.wait_for_selector(sel, timeout=3000)
            if el:
                el.fill(value)
                print(f"  [*] Filled {sel} with '{value}'")
                page.wait_for_timeout(500)
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

print("=" * 60)
print("  HOP – auto-register with captcha/OTP handling")
print("=" * 60)

username, email, password = generate_credentials()
print(f"\n  [*] Username: {username}")
print(f"  [*] Email:    {email}")
print(f"  [*] Password: {password}")

with Camoufox(**opts) as browser:
    page = browser.new_page()
    page.set_default_timeout(30000)
    page.set_viewport_size({"width": 1280, "height": 720})

    # Navigate
    print(f"\n  [+] Navigating to https://superlive.chat/fr/nonlogin-messages")
    page.goto("https://superlive.chat/fr/nonlogin-messages", wait_until="load", timeout=120000)
    page.wait_for_timeout(4000)

    # Click S'inscrire
    print(f"\n  [+] Looking for 'S'inscrire' button...")
    click_text(page, "S'inscrire")
    page.wait_for_timeout(2500)

    # Click email method button
    click_p_email_image(page)
    page.wait_for_timeout(2500)

    # Click "S'enregistrer avec l'adresse e-mail" to choose registration (not login)
    print(f"\n  [+] Clicking register-with-email button...")
    clicked_register = find_and_click(page, "register with email", ["s'enregistrer avec l'adresse e-mail", "s'enregistrer avec", "enregistrer avec l'adresse e-mail"])
    if not clicked_register:
        print("  [!] Register-with-email button was not clicked")
    page.wait_for_timeout(2500)

    # Fill email
    print(f"\n  [+] Filling email with {email}...")
    fill_input(page, "input[type='email'], input[name='email'], input[id*='email'], input[placeholder*='email' i]", email)
    page.wait_for_timeout(500)

    # Check if password field already exists (full form visible)
    password_visible = page.evaluate("() => !!document.querySelector('input[name=\"password\"]')")
    if not password_visible:
        print(f"  [*] Password field not found — looking for continue button")
        has_continue = page.evaluate("""() => {
            const all = document.querySelectorAll('button, a, [role="button"], input[type="submit"]');
            const kws = ['continue', 'suivant', 'next', 'استمرار', 'متابعة'];
            for (const el of all) {
                const t = el.textContent.toLowerCase().trim();
                if (kws.some(kw => t.includes(kw))) return true;
            }
            return false;
        }""")
        if has_continue:
            print(f"  [*] Continue button found — clicking via CSS selector h-14")
            try:
                el = page.wait_for_selector('button.h-14', timeout=3000)
                el.click()
                print("  [*] Clicked Continue (h-14 selector)")
            except Exception:
                print("  [!] h-14 button not found, trying keyword fallback")
                find_and_click(page, "continue", ["continue", "suivant", "next", "استمرار", "متابعة"])
            page.wait_for_timeout(2500)
        else:
            print(f"  [!] No continue button found on page")
    else:
        print(f"  [*] Password field already visible")

    # Fill password (appears after continue or already visible)
    print(f"\n  [+] Filling password...")
    fill_input(page, "input[name='password']", password)
    page.wait_for_timeout(500)
    print(f"\n  [+] Filling confirm password...")
    fill_input(page, "input[name='passwordRepeat']", password)
    page.wait_for_timeout(500)

    # Click continue to submit password and trigger OTP
    print(f"\n  [+] Clicking continue (password step)...")
    find_and_click(page, "continue", ['continue', 'suivant', 'inscription', 'استمرار', 'متابعة'])
    page.wait_for_timeout(2500)

    # now wait and search for captcha / OTP
    page.wait_for_timeout(2500)
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        print(f"  [*] Captcha check attempt {attempt}/{max_attempts}")
        result = handle_captcha(page)
        if result == "otp":
            print(f"  [*] OTP step reached — fetching and filling code...")
            fill_otp(page, email)
            page.wait_for_timeout(500)
            find_and_click(
                page, "OTP continue/verify button",
                keywords=['تحقق', 'verify', 'continue', 'التالي', 'submit', 'إرسال'],
            )
            page.wait_for_timeout(2500)
        elif result:
            print(f"  [*] Captcha handled (attempt {attempt})")
            page.wait_for_timeout(2500)
        else:
            print(f"  [*] No captcha or OTP — form likely submitted successfully")
            otp_now = page.evaluate("""() => {
                const otpInput = document.querySelector('#otp-code-0, input[autocomplete='one-time-code']');
                if (otpInput) return true;
                return document.body.innerText.includes('أدخل رمز التحقق') || document.body.innerText.includes('verification code');
            }""")
            if otp_now:
                print(f"  [*] OTP detected on post-submit page — filling code...")
                fill_otp(page, email)
                page.wait_for_timeout(500)
                find_and_click(
                    page, "OTP continue/verify button",
                    keywords=['تحقق', 'verify', 'continue', 'التالي', 'submit', 'إرسال'],
                )
                page.wait_for_timeout(2500)
            break

    print("\n  [+] Flow complete. Exiting in 10s...")
    page.wait_for_timeout(5000)
    import sys; sys.exit(0)
