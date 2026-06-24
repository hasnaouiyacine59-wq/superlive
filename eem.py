import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
import sys

HOST = "imap.gmail.com"
PORT = 993
USERNAME = "kalawssimatrix@gmail.com"
PASSWORD = "onxzzjwponsfoogk"


def list_emails(target_email):
    mail = imaplib.IMAP4_SSL(HOST, PORT)
    mail.login(USERNAME, PASSWORD)
    mail.select("INBOX")

    _, msg_ids = mail.search(None, f'TO "{target_email}"')
    ids = msg_ids[0].split()
    print(f"Emails TO {target_email}: {len(ids)}")

    if not ids:
        print("  No TO matches — trying FROM SuperLive + filtering by TO...")
        _, from_ids = mail.search(None, 'FROM "noreply@superlivellc.com"')
        all_from = from_ids[0].split() if from_ids[0] else []
        filtered = []
        for mid in all_from[-100:]:
            _, hdr = mail.fetch(mid, '(BODY.PEEK[HEADER.FIELDS (TO)])')
            raw_to = hdr[0][1].decode(errors="ignore")
            if target_email in raw_to:
                filtered.append(mid)
        ids = filtered
        print(f"  Found {len(ids)} via fallback")

    for mid in ids[-30:]:
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

        frm = msg.get("From", "")
        dt = parsedate_to_datetime(msg.get("Date"))

        print(f"\n{'='*60}")
        print(f"From:    {frm}")
        print(f"Date:    {dt}")
        print(f"Subject: {subject}")
        print(f"Body:    {body[:300]}")

    mail.logout()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python eem.py <email>")
        sys.exit(1)
    list_emails(sys.argv[1])
