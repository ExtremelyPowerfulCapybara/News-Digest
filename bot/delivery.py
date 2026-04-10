# ─────────────────────────────────────────────
#  delivery.py  —  Sends email to subscribers
#  Reads from subscribers.csv if it exists,
#  falls back to SUBSCRIBERS env var.
# ─────────────────────────────────────────────

import csv
import os
import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from config import EMAIL_SENDER, EMAIL_PASSWORD, SUBSCRIBERS, NEWSLETTER_NAME

import pathlib
REPO_ROOT       = pathlib.Path(__file__).parent.parent
SUBSCRIBERS_CSV = REPO_ROOT / "subscribers.csv"


def load_subscribers() -> list[str]:
    """
    Loads active subscriber emails from subscribers.csv if it exists.
    Falls back to SUBSCRIBERS from config (env var) if CSV is missing.
    """
    if SUBSCRIBERS_CSV.exists():
        emails = []
        with open(SUBSCRIBERS_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("active", "true").strip().lower() == "true":
                    email = row.get("email", "").strip()
                    if email:
                        emails.append(email)
        print(f"  [delivery] Loaded {len(emails)} subscriber(s) from subscribers.csv")
        return emails
    else:
        print(f"  [delivery] No subscribers.csv found, using SUBSCRIBERS env var ({len(SUBSCRIBERS)} subscriber(s))")
        return SUBSCRIBERS


def send_email(html: str, plain: str, sentiment_label: str = "Cautious") -> None:
    today = date.today()
    months_es = ["","enero","febrero","marzo","abril","mayo","junio",
                 "julio","agosto","septiembre","octubre","noviembre","diciembre"]
    today_str   = f"{today.day} de {months_es[today.month]} de {today.year}"
    subject     = f"{sentiment_label} | {NEWSLETTER_NAME} — {today_str}"
    subscribers = load_subscribers()

    if not subscribers:
        print("  [delivery] No subscribers found, skipping send.")
        return

    print(f"  [delivery] Sending to {len(subscribers)} subscriber(s)...")
    smtp_port = int(os.environ.get("SMTP_PORT", 587))
    use_ssl   = os.environ.get("SMTP_USE_SSL", "false").lower() == "true"
    try:
        print(f"  [delivery] Connecting to SMTP ({'SSL' if use_ssl else 'STARTTLS'}:{smtp_port})...")
        if use_ssl:
            import ssl as _ssl
            ctx = _ssl.create_default_context()
            server_cm = smtplib.SMTP_SSL("smtp.gmail.com", smtp_port, timeout=30, context=ctx)
        else:
            server_cm = smtplib.SMTP("smtp.gmail.com", smtp_port, timeout=30)
        with server_cm as server:
            if not use_ssl:
                server.ehlo()
                server.starttls()
                server.ehlo()
            print("  [delivery] Connection established, authenticating...")
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            print("  [delivery] SMTP login successful")
            for recipient in subscribers:
                msg            = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"]    = EMAIL_SENDER
                msg["To"]      = recipient
                msg.attach(MIMEText(plain, "plain"))
                msg.attach(MIMEText(html,  "html"))
                server.sendmail(EMAIL_SENDER, recipient, msg.as_string())
                print(f"  [delivery] Sent to {recipient}")
        print(f"  [delivery] Done — {len(subscribers)} email(s) sent.")
    except Exception as e:
        print(f"  [delivery] Email send failed: {e}")
        raise
