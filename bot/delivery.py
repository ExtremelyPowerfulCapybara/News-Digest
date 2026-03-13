# ─────────────────────────────────────────────
#  delivery.py  —  Sends email to subscribers
#  Reads from subscribers.csv if it exists,
#  falls back to SUBSCRIBERS env var.
# ─────────────────────────────────────────────

import csv
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


def send_email(html: str, plain: str) -> None:
    today = date.today()
    months_es = ["","enero","febrero","marzo","abril","mayo","junio",
                 "julio","agosto","septiembre","octubre","noviembre","diciembre"]
    today_str   = f"{today.day} de {months_es[today.month]} de {today.year}"
    subject     = f"{NEWSLETTER_NAME} — {today_str}"
    subscribers = load_subscribers()

    if not subscribers:
        print("  [delivery] No subscribers found, skipping send.")
        return

    print(f"  [delivery] Sending to {len(subscribers)} subscriber(s)...")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        for recipient in subscribers:
            msg            = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"]    = EMAIL_SENDER
            msg["To"]      = recipient
            msg.attach(MIMEText(plain, "plain"))
            msg.attach(MIMEText(html,  "html"))
            server.sendmail(EMAIL_SENDER, recipient, msg.as_string())
            print(f"  [delivery] Sent to {recipient}")
    print("  [delivery] Done.")
