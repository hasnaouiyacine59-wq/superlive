import imaplib
import email
import random
import re
import socket
import sys
import time
from email.header import decode_header
from email.utils import parsedate_to_datetime

HOST = "imap.gmail.com"
PORT = 993
USERNAME = "kalawssimatrix@gmail.com"
PASSWORD = "onxzzjwponsfoogk"

socket.setdefaulttimeout(15)


def decode_subject(raw):
    parts = decode_header(raw)
    return "".join(
        p.decode(enc or "utf-8") if isinstance(p, bytes) else p
        for p, enc in parts
    )


def get_body(msg):
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                return part.get_payload(decode=True).decode(errors="ignore")
    return msg.get_payload(decode=True).decode(errors="ignore")


def search_email(target):
    mail = imaplib.IMAP4_SSL(HOST, PORT)
    mail.login(USERNAME, PASSWORD)
    mail.select("INBOX")

    mids_to_fetch = set()

    # 1. Direct TO search
    _, ids = mail.search(None, f'TO "{target}"')
    mids_to_fetch.update(ids[0].split() if ids[0] else [])

    # 2. FROM SuperLive + check headers/body for target
    _, ids = mail.search(None, 'FROM "noreply@superlivellc.com"')
    for mid in (ids[0].split() if ids[0] else []):
        _, hdr = mail.fetch(mid, '(BODY.PEEK[HEADER.FIELDS (FROM TO DATE SUBJECT)])')
        raw = hdr[0][1].decode(errors="ignore")
        if target in raw:
            mids_to_fetch.add(mid)

    print(f"Total emails for {target}: {len(mids_to_fetch)}\n")

    for mid in sorted(mids_to_fetch):
        _, data = mail.fetch(mid, "(RFC822)")
        msg = email.message_from_bytes(data[0][1])

        frm = msg.get("From", "")
        to = msg.get("To", "")
        dt = parsedate_to_datetime(msg.get("Date"))
        subject = decode_subject(msg.get("Subject", ""))

        body = get_body(msg)
        code_match = re.search(r"(\d{6})", body)
        code = code_match.group(1) if code_match else "N/A"

        print(f"{'='*60}")
        print(f"ID:      {mid.decode() if isinstance(mid, bytes) else mid}")
        print(f"From:    {frm}")
        print(f"To:      {to}")
        print(f"Date:    {dt}")
        print(f"Subject: {subject}")
        print(f"Code:    {code}")
        print(f"Body:    {body[:200]}")
        print()

    mail.logout()


def list_all():
    mail = imaplib.IMAP4_SSL(HOST, PORT)
    mail.login(USERNAME, PASSWORD)
    mail.select("INBOX")
    _, ids = mail.search(None, 'FROM "noreply@superlivellc.com"')
    print(f"Total SuperLive emails: {len(ids[0].split()) if ids[0] else 0}\n")
    for mid in (ids[0].split() if ids[0] else [])[-50:]:
        _, hdr = mail.fetch(mid, '(BODY.PEEK[HEADER.FIELDS (FROM TO DATE SUBJECT)])')
        raw = hdr[0][1].decode(errors="ignore")
        print(f"{mid.decode():>6} | {raw.strip()}")
        print()
    mail.logout()


def get_2fa(target_email=None, retries=10, delay=4):
    for attempt in range(1, retries + 1):
        try:
            mail = imaplib.IMAP4_SSL(HOST, PORT)
            mail.login(USERNAME, PASSWORD)
            mail.select("INBOX")

            _, msg_ids = mail.search(None, f'FROM "noreply@superlivellc.com"' + (f' TO "{target_email}"' if target_email else ""))
            ids = msg_ids[0].split()[-20:]
            print(f"[2FA] attempt {attempt}/{retries} — {len(ids)} emails found")

            if not ids:
                _, hdr_ids = mail.search(None, 'FROM "noreply@superlivellc.com"')
                for mid in (hdr_ids[0].split() if hdr_ids[0] else [])[-100:]:
                    _, hdr = mail.fetch(mid, '(BODY.PEEK[HEADER.FIELDS (TO)])')
                    raw = hdr[0][1].decode(errors="ignore")
                    if target_email and target_email in raw:
                        ids.append(mid)
                print(f"  [*] Fallback found {len(ids)} emails")

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

                match = re.search(r"(\d{6})", body)
                if match:
                    code_candidate = match.group(1)
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
                mail.store(best_id, "+FLAGS", "\\Deleted")
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
    if len(sys.argv) < 2:
        print("Usage: python super_email.py <email>")
        print("       python super_email.py --list        # show all recent SuperLive emails")
        sys.exit(1)
    if sys.argv[1] == "--list":
        list_all()
    else:
        search_email(sys.argv[1])
