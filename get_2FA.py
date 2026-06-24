import imaplib
import email
import random
from email.header import decode_header
from email.utils import parsedate_to_datetime
import re
import time

HOST = "imap.gmail.com"
PORT = 993
USERNAME = "kalawssimatrix@gmail.com"
PASSWORD = "onxzzjwponsfoogk"

# USERNAME = "andrmidal84a@gmail.com"

# PASSWORD = "efahsruujuerkazj"

def get_2fa(target_email=None, retries=10, delay=4):
    for attempt in range(1, retries + 1):
        try:
            mail = imaplib.IMAP4_SSL(HOST, PORT)
            mail.login(USERNAME, PASSWORD)
            mail.select("INBOX")

            _, msg_ids = mail.search(None, f'FROM "noreply@superlivellc.com"' + (f' TO "{target_email}"' if target_email else ""))
            ids = msg_ids[0].split()[-20:]
            print(f"[2FA] attempt {attempt}/{retries} — {len(ids)} emails found")

            best_code = None
            best_time = None
            best_id = None

            for mid in ids:
                _, data = mail.fetch(mid, "(RFC822)")
                msg = email.message_from_bytes(data[0][1])

                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_payload(decode=True).decode(errors="ignore")
                            break
                else:
                    body = msg.get_payload(decode=True).decode(errors="ignore")

                raw_subject = msg.get("Subject", "")
                parts = decode_header(raw_subject)
                subject = "".join(
                    p.decode(enc or "utf-8") if isinstance(p, bytes) else p
                    for p, enc in parts
                )
                match = re.search(r'(\d{6})', body)
                if not match:
                    match = re.search(r'(?<![A-Z0-9])([A-Z0-9]{6})(?![A-Z0-9])', subject, re.IGNORECASE)
                if not match:
                    match = re.search(r'(?:Your verification code is|Votre code de v[eé]rification est)\s*:\s*\n\s*([A-Z0-9]{3} [A-Z0-9]{3})', body, re.IGNORECASE)
                if not match:
                    match = re.search(r'(?<![A-Z0-9])([A-Z0-9]{3} [A-Z0-9]{3})(?![A-Z0-9])', body)
                if not match:
                    match = re.search(r'(?:enter the following code|following code)[^\n]*\n+\s*([A-Z0-9]{6})', body, re.IGNORECASE)
                if not match:
                    match = re.search(r'(?<![A-Z0-9])([A-Z0-9]{6})(?![A-Z0-9])', body, re.IGNORECASE)
                if not match:
                    print(f"[2FA DEBUG] subject: {subject!r} | body snippet: {body[:300]}")
                if match:
                    code_candidate = match.group(1).replace(" ", "").upper()
                    date_str = msg.get("Date")
                    try:
                        msg_time = parsedate_to_datetime(date_str)
                    except Exception:
                        msg_time = None
                    if best_time is None or (msg_time and msg_time > best_time):
                        best_time = msg_time
                        best_code = code_candidate
                        best_id = mid
                        print(f"[2FA] newer code: {best_code} at {msg_time}")

            if best_code:
                mail.store(best_id, '+FLAGS', '\\Deleted')
                mail.expunge()
                mail.logout()
                return best_code

            mail.logout()
        except Exception as e:
            print(f"[2FA] attempt {attempt} error: {e}")

        wait = random.randint(3, 5)
        print(f"[2FA] waiting {wait}s before next attempt...")
        time.sleep(wait)

    return None

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python get_2FA.py <email>")
        sys.exit(1)
    code = get_2fa(sys.argv[1])
    print(f"2FA Code: {code}")
