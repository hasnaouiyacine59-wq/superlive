import random
import os
from pathlib import Path
from typing import List

import numpy as np
import cv2
import requests
import speech_recognition as sr
from pydub import AudioSegment

from camoufox import Camoufox, DefaultAddons
from camoufox.utils import launch_options
from db.db import insert_account
from get_2FA import get_2fa


DOMAINS = [
    "alpha804.eu.org",
    "alpha-sig.eu.org",
    "beta-sig.eu.org",
    "bitcoin-plazza.eu.org",
    "c0rner-bit.eu.org",
    "dark0s-market.eu.org",
    "gamma-sig.eu.org",
    "iblogg.eu.org",
    "lg-salmi.nl.eu.org",
    "m0rd05.eu.org",
    "sec4891.eu.org",
    "techstreet07.eu.org",
    "vaya.eu.org",
    "w0rld.int.eu.org",
    "ziw05tempemail.eu.org",
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


def random_os() -> List[str]:
    os_list = ["windows", "macos", "linux"]
    count = random.randint(1, 3)
    chosen = random.sample(os_list, count)
    return chosen


def generate_fingerprint_info():
    print("=" * 60)
    print("  CAMOUFOX - Undetectable Browser Test")
    print("  Random device profile each run")
    print("=" * 60)


def find_and_click(page, label, keywords, selectors_extra=None, timeout=3000):
    print(f"  [*] Looking for {label}...")
    result = page.evaluate(f"""() => {{
        const all = document.querySelectorAll('button, a, [role="button"]');
        const keywords = {keywords};
        for (const el of all) {{
            const text = el.textContent.toLowerCase().trim();
            const aria = (el.getAttribute('aria-label') || '').toLowerCase();
            const testid = (el.getAttribute('data-testid') || '').toLowerCase();
            const href = (el.getAttribute('href') || '').toLowerCase();
            for (const kw of keywords) {{
                if (text.includes(kw) || aria.includes(kw) || testid.includes(kw) || href.includes(kw)) {{
                    el.dispatchEvent(new MouseEvent('click', {{bubbles: true, cancelable: true}}));
                    return el.outerHTML.slice(0, 200);
                }}
            }}
        }}
        return null;
    }}""")
    if result:
        print(f"  [*] Clicked {label}: {result}")
        page.wait_for_timeout(2000)
        return True
    print(f"  [!] {label} not found")
    return False


def click_login(page):
    return find_and_click(
        page, "login button",
        keywords=['log in', 'sign in', 'login', 'تسجيل الدخول', 'تسجيل', 'دخول'],
    )


def click_register(page):
    return find_and_click(
        page, "register tab",
        keywords=['أنشاء', 'إنشاء', 'انشاء', 'أنشاء حساب', 'sign up', 'register', 'create account'],
    )


def click_email_signin(page):
    return find_and_click(
        page, "email sign-in button",
        keywords=['البريد الإلكتروني', 'email', 'سجل عن طريق البريد', 'متابعة عبر البريد', 'continue with email'],
        timeout=5000,
    )


def click_register_email(page):
    return find_and_click(
        page, "register email button",
        keywords=['سجل عن طريق البريد', 'register via email', 'sign up with email'],
    )


def fill_email_form(page, email):
    print(f"  [*] Filling email form with {email}...")
    for sel in ["#otp-email", "#email", "input[type='email']"]:
        try:
            el = page.wait_for_selector(sel, timeout=3000)
            if el:
                el.fill(email)
                page.wait_for_timeout(1000)
                print(f"  [*] Filled email field ({sel})")
                break
        except Exception:
            continue
    else:
        print(f"  [!] Could not find email input")
        return False
    return find_and_click(
        page, "continue button",
        keywords=['استمرار', 'continue', 'next', 'متابعة'],
    )


def fill_password_form(page, password):
    print(f"  [*] Filling password form...")
    for sel in ["#otp-password", "#password"]:
        try:
            el = page.wait_for_selector(sel, timeout=3000)
            if el:
                el.fill(password)
                page.wait_for_timeout(500)
                print(f"  [*] Filled password field ({sel})")
                break
        except Exception:
            continue
    else:
        print(f"  [!] Could not find password input")
        return False
    # also fill password repeat if present
    try:
        el2 = page.wait_for_selector("#passwordRepeat", timeout=2000)
        if el2:
            el2.fill(password)
            print(f"  [*] Filled password confirmation")
    except Exception:
        pass
    # click radio/checkbox if needed
    try:
        el3 = page.wait_for_selector("input[type='radio'], input[type='checkbox']", timeout=2000)
        if el3:
            page.evaluate("el => el.click()", el3)
            print(f"  [*] Clicked agreement radio/checkbox")
    except Exception:
        pass
    page.wait_for_timeout(1000)
    return True


def solve_audio_challenge(page, frame):
    print(f"  [*] Solving audio challenge...")
    page.wait_for_timeout(2000)

    # retry getting audio URL (the audio element may take time to load)
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
        page.wait_for_timeout(2000)
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
        text = r.recognize_google(data)
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
            page.wait_for_timeout(3000)
        else:
            print(f"  [!] Verify button not found")
            return False
    except Exception as e:
        print(f"  [!] Could not click verify: {e}")
        return False

    for p in [mp3_path, wav_path]:
        try:
            os.remove(p)
        except Exception:
            pass
    return True


def click_captcha_image(page):
    screenshot_path = Path("results/captcha_screenshot.png")
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(screenshot_path))

    im_screenshot = cv2.imread(str(screenshot_path))
    im_template  = cv2.imread("src/captcha.png")
    if im_screenshot is None:
        print("  [*] Failed to load screenshot for image matching")
        return False
    if im_template is None:
        print("  [*] Failed to load src/captcha.png – skipping image match")
        return False

    result = cv2.matchTemplate(im_screenshot, im_template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    if max_val < 0.7:
        print(f"  [*] captcha.png not found (best match {max_val:.2f})")
        return False

    h, w = im_template.shape[:2]
    cx = max_loc[0] + w // 2
    cy = max_loc[1] + h // 2

    scale_x = page.viewport_size["width"] / im_screenshot.shape[1]
    scale_y = page.viewport_size["height"] / im_screenshot.shape[0]
    page.mouse.click(cx / scale_x, cy / scale_y)
    print(f"  [*] Clicked captcha image match at ({int(cx)}:{int(cy)}) confidence {max_val:.2f}")
    page.wait_for_timeout(3000)
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
        otp_detected = page.evaluate("""() => {
            const otpInput = document.querySelector('#otp-code-0, input[autocomplete='one-time-code']');
            if (otpInput) return true;
            const header = document.body.innerText.includes('أدخل رمز التحقق') || document.body.innerText.includes('verification code');
            if (header) return true;
            return false;
        }""")
        if otp_detected:
            print(f"  [*] OTP verification screen detected (user will implement later)")
            return "otp"
        return False

    print(f"  [*] Captcha detected: {found_captcha}")
    print(f"  [*] Triggering captcha...")

    # 1) Try grecaptcha.execute() programmatically (main world with mw: prefix)
    grecaptcha_loaded = page.evaluate("mw:() => { return typeof grecaptcha !== 'undefined' && typeof grecaptcha.execute === 'function'; }")
    if grecaptcha_loaded:
        result = page.evaluate("mw:() => { try { if (grecaptcha.enterprise) { grecaptcha.enterprise.execute(); return 'enterprise.execute()'; } } catch(e) {} try { grecaptcha.execute(); return 'execute()'; } catch(e) {} try { grecaptcha.execute('6Ld9_e8sAAAAAIPwD7J3mrBiQno-h86lHiFfQ_Nk'); return 'execute(sitekey)'; } catch(e) {} return 'failed'; }")
        print(f"  [*] grecaptcha.{result}")
        page.wait_for_timeout(3000)
    else:
        print(f"  [*] grecaptcha not available in main world either, checking iframes...")

    # Debug: dump all iframes
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

    # 2) Click a visible recaptcha anchor iframe
    clicked_checkbox = False
    if image_match_clicked:
        clicked_checkbox = True
        print(f"  [*] Image match already clicked the captcha checkbox")
    elif len(recaptcha_iframes) <= 2:
        print("  [*] Only 2 recaptcha iframes present; skipping captcha handling")
        dump_html(page, "only_2_iframes_skip")
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
                    print(f"  [*] Clicked captcha element ({sel}) at ({x:.0f}, {y:.0f})")
                    page.wait_for_timeout(3000)
                    clicked_checkbox = True
                    break
        except Exception:
            continue
    if not clicked_checkbox:
        # fallback: try clicking any iframe that looks like recaptcha
        if recaptcha_iframes:
            info = recaptcha_iframes[0]
            if info['rect']:
                x = info['rect']['x'] + 20
                y = info['rect']['y'] + info['rect']['height'] / 2
                page.mouse.click(x, y)
                print(f"  [*] Clicked first recaptcha iframe at ({x:.0f}, {y:.0f})")
                page.wait_for_timeout(3000)
                clicked_checkbox = True
        if not clicked_checkbox:
            print(f"  [*] Could not click any recaptcha iframe")

    # 3) Click the audio challenge button inside the recaptcha challenge popup
    if clicked_checkbox:
        print(f"  [*] Looking for audio challenge button...")
        # wait for challenge iframe to appear
        try:
            challenge_frame = page.wait_for_selector(
                "iframe[src*='recaptcha/enterprise/bframe'], iframe[src*='recaptcha/api2/bframe']",
                timeout=8000
            )
            if challenge_frame:
                print(f"  [*] Challenge iframe appeared")
                page.wait_for_timeout(1000)
                # try to find the frame by URL
                frame = None
                for f in page.frames:
                    if 'bframe' in f.url and 'recaptcha' in f.url:
                        frame = f
                        break
                if frame:
                    print(f"  [*] Found challenge frame: {frame.url[:100]}...")
                    # wait for the audio button to become enabled (challenge loaded)
                    page.wait_for_timeout(2000)
                    # click the audio button - various possible selectors
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
                                page.wait_for_timeout(3000)
                                # solve the audio challenge
                                solve_audio_challenge(page, frame)
                                break
                        except Exception:
                            continue
                    else:
                        print(f"  [*] Audio button not found in challenge frame")
                        # dump the frame content for debugging
                        try:
                            frame_html = frame.content()
                            Path("results/recaptcha_challenge_frame.html").write_text(frame_html)
                            print(f"  [*] Saved challenge frame HTML to results/recaptcha_challenge_frame.html")
                        except Exception:
                            pass
                else:
                    print(f"  [*] Could not find challenge frame by URL")
        except Exception as e:
            print(f"  [*] Challenge iframe did not appear: {e}")
            # check for OTP instead
            otp_detected = page.evaluate("""() => {
                const otpInput = document.querySelector('#otp-code-0, input[autocomplete='one-time-code']');
                if (otpInput) return true;
                if (document.body.innerText.includes('أدخل رمز التحقق')) return true;
                return false;
            }""")
            if otp_detected:
                print(f"  [*] OTP verification screen detected instead of captcha")
                return "otp"
    else:
        print(f"  [*] Skipping audio button (checkbox not clicked)")

    dump_html(page, "captcha_state")
    return True


def dump_html(page, label):
    dump_path = Path("results") / f"superlivetv_followings_{label}.html"
    dump_path.write_text(page.content())
    print(f"  [*] Saved HTML to {dump_path}")


def fill_otp(page, email):
    print(f"  [*] Fetching OTP code from email...")
    code = get_2fa(email, retries=15, delay=4)
    if not code:
        print("  [!] Failed to get OTP code")
        return False

    print(f"  [*] Got OTP code: {code}")

    # try individual digit fields #otp-code-0 .. #otp-code-5
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
        page.wait_for_timeout(1000)
        return True

    # fallback: single input with autocomplete
    try:
        el = page.wait_for_selector(
            "input[autocomplete='one-time-code'], input[name*='otp' i], input[id*='otp' i]",
            timeout=2000,
        )
        if el:
            el.fill(code)
            print(f"  [*] Filled single OTP input")
            page.wait_for_timeout(1000)
            return True
    except Exception:
        pass

    # last resort: paste into any 6+ char input
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
    page.wait_for_timeout(1000)
    return True


def visit_page(browser, url, name, email, password):
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 720})
    print(f"\n  [+] Visiting {name} ({url})...")
    try:
        page.goto(url, wait_until="load", timeout=60000)
    except Exception as e:
        print(f"  [!] Initial load timeout: {e}")
    page.wait_for_timeout(8000)

    dump_path = Path("results") / f"{name}.html"
    dump_path.parent.mkdir(parents=True, exist_ok=True)
    dump_path.write_text(page.content())
    print(f"  [*] Saved initial HTML to {dump_path}")

    click_login(page)
    page.wait_for_timeout(2000)

    login_path = Path("results") / f"{name}_after_login_click.html"
    login_path.write_text(page.content())
    print(f"  [*] Saved HTML after login click to {login_path}")

    click_register(page)
    page.wait_for_timeout(2000)

    register_path = Path("results") / f"{name}_after_register_click.html"
    register_path.write_text(page.content())
    print(f"  [*] Saved HTML after register click to {register_path}")

    click_email_signin(page)
    page.wait_for_timeout(3000)

    email_path = Path("results") / f"{name}_after_email_click.html"
    email_path.write_text(page.content())
    print(f"  [*] Saved HTML after email sign-in click to {email_path}")

    click_register_email(page)
    page.wait_for_timeout(3000)

    reg_email_path = Path("results") / f"{name}_after_register_email_click.html"
    reg_email_path.write_text(page.content())
    print(f"  [*] Saved HTML after register email click to {reg_email_path}")

    fill_email_form(page, email)
    page.wait_for_timeout(3000)

    filled_path = Path("results") / f"{name}_after_email_submit.html"
    filled_path.write_text(page.content())
    print(f"  [*] Saved HTML after email submit to {filled_path}")

    fill_password_form(page, password)
    page.wait_for_timeout(2000)
    dump_html(page, "after_password_filled")

    # click continue
    find_and_click(
        page, "continue button",
        keywords=['استمرار', 'continue', 'next', 'متابعة'],
    )
    page.wait_for_timeout(3000)

    password_path = Path("results") / f"{name}_after_password_submit.html"
    password_path.write_text(page.content())
    print(f"  [*] Saved HTML after password submit to {password_path}")

    # now wait and search for captcha / OTP
    page.wait_for_timeout(5000)
    dump_html(page, "after_password_submit_loaded")
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        print(f"  [*] Captcha check attempt {attempt}/{max_attempts}")
        result = handle_captcha(page)
        if result == "otp":
            print(f"  [*] OTP step reached — fetching and filling code...")
            fill_otp(page, email)
            page.wait_for_timeout(2000)
            find_and_click(
                page, "OTP continue/verify button",
                keywords=['تحقق', 'verify', 'continue', 'التالي', 'submit', 'إرسال'],
            )
            page.wait_for_timeout(5000)
            dump_html(page, f"after_otp_filled")
        elif result:
            print(f"  [*] Captcha handled (attempt {attempt})")
            # wait and check again
            page.wait_for_timeout(5000)
            dump_html(page, f"after_captcha_attempt_{attempt}")
            # loop continues to check again
        else:
            print(f"  [*] No captcha or OTP — form likely submitted successfully")
            dump_html(page, "post_submit_no_captcha")
            # double-check for OTP (may appear after a redirect)
            otp_now = page.evaluate("""() => {
                const otpInput = document.querySelector('#otp-code-0, input[autocomplete='one-time-code']');
                if (otpInput) return true;
                return document.body.innerText.includes('أدخل رمز التحقق') || document.body.innerText.includes('verification code');
            }""")
            if otp_now:
                print(f"  [*] OTP detected on post-submit page — filling code...")
                fill_otp(page, email)
                page.wait_for_timeout(2000)
                find_and_click(
                    page, "OTP continue/verify button",
                    keywords=['تحقق', 'verify', 'continue', 'التالي', 'submit', 'إرسال'],
                )
                page.wait_for_timeout(5000)
                dump_html(page, f"after_otp_filled_post_submit")
            break

    return page


def main():
    generate_fingerprint_info()

    username, email, password = generate_credentials()
    print(f"\n  [*] Generated credentials:")
    print(f"      Username: {username}")
    print(f"      Email:    {email}")
    print(f"      Password: {password}")

    target_os = random_os()
    print(f"\n  [*] Target OS: {', '.join(target_os)}")
    print(f"  [*] GeoIP: True (spoofed location)")
    print(f"  [*] Humanize: True (realistic mouse movement)")
    print(f"  [*] Block WebRTC: True")
    print(f"  [*] Block Images: False")

    opts = launch_options(
        os=target_os,
        geoip=True,
        humanize=True,
        block_webrtc=True,
        block_images=False,
        disable_coop=True,
        main_world_eval=True,
        exclude_addons=[DefaultAddons.UBO],
        window=(1280, 720),
        debug=True,
    )

    print(f"\n  [*] Launching Camoufox with random fingerprint...\n")

    with Camoufox(**opts) as browser:
        visit_page(browser, "https://superlivetv.com/ar/followings", "superlivetv_followings", email, password)
        input("\n  [*] Browser still open. Press Enter to close...")

    print("\n" + "=" * 60)
    print("  Done. Check the results/ directory for page sources.")
    print("=" * 60)



if __name__ == "__main__":
    main()
