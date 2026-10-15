# Paid Tier & Topic Preferences Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce a freemium model where free subscribers get the full digest unchanged and paid subscribers authenticate on a self-hosted portal, select editorial topic buckets, and receive a filtered digest.

**Architecture:** SQLite database (`subscribers.db`) replaces `subscribers.csv` as the subscriber source of truth. A small Flask app on the VPS handles magic-link auth and preference selection. The delivery pipeline reads from the DB and renders a filtered digest per paid subscriber at send time.

**Tech Stack:** Python 3.11+, SQLite (stdlib), Flask 3.x, smtplib (stdlib), pytest

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Create | `bot/db.py` | SQLite schema, all subscriber + token CRUD |
| Create | `bot/migrate_subscribers.py` | One-time CSV → DB migration script |
| Create | `bot/subscriber_filter.py` | Pure `filter_stories()` function |
| Create | `bot/admin.py` | CLI for manual tier management |
| Modify | `bot/summarizer.py` | Add `category` field to Claude story schema |
| Modify | `bot/delivery.py` | Per-subscriber render + send loop |
| Modify | `bot/main.py` | Call `deliver()` instead of `send_email()` |
| Create | `web/app.py` | Flask portal: auth + preferences routes |
| Create | `web/templates/index.html` | Email input landing page |
| Create | `web/templates/auth_sent.html` | "Check your email" confirmation |
| Create | `web/templates/auth_error.html` | Invalid/expired token page |
| Create | `web/templates/preferences.html` | Topic checkbox form |
| Create | `web/requirements.txt` | Flask dependencies |

---

## Task 1: Database module (`bot/db.py`)

**Files:**
- Create: `bot/db.py`
- Create: `bot/tests/test_db.py`

- [ ] **Step 1: Write failing tests**

Create `bot/tests/test_db.py`:

```python
import json
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("SUBSCRIBERS_DB", db_path)
    import db
    db.init_db()
    return db


def test_upsert_and_get_subscriber(tmp_db):
    tmp_db.upsert_subscriber("a@example.com", tier="free", topics=["latam"])
    sub = tmp_db.get_subscriber("a@example.com")
    assert sub["email"] == "a@example.com"
    assert sub["tier"] == "free"
    assert sub["topics"] == ["latam"]
    assert sub["active"] == 1


def test_upsert_updates_existing(tmp_db):
    tmp_db.upsert_subscriber("a@example.com", tier="free", topics=[])
    tmp_db.upsert_subscriber("a@example.com", tier="paid", topics=["markets", "crypto"])
    sub = tmp_db.get_subscriber("a@example.com")
    assert sub["tier"] == "paid"
    assert sub["topics"] == ["markets", "crypto"]


def test_get_subscribers_active_only(tmp_db):
    tmp_db.upsert_subscriber("active@example.com", active=1)
    tmp_db.upsert_subscriber("inactive@example.com", active=0)
    subs = tmp_db.get_subscribers(active_only=True)
    emails = [s["email"] for s in subs]
    assert "active@example.com" in emails
    assert "inactive@example.com" not in emails


def test_get_subscriber_missing_returns_none(tmp_db):
    assert tmp_db.get_subscriber("nobody@example.com") is None


def test_create_and_consume_token(tmp_db):
    tmp_db.upsert_subscriber("b@example.com")
    token = tmp_db.create_auth_token("b@example.com")
    assert len(token) == 36  # UUID4
    email = tmp_db.consume_auth_token(token)
    assert email == "b@example.com"


def test_token_single_use(tmp_db):
    tmp_db.upsert_subscriber("c@example.com")
    token = tmp_db.create_auth_token("c@example.com")
    tmp_db.consume_auth_token(token)
    assert tmp_db.consume_auth_token(token) is None


def test_token_expired(tmp_db, monkeypatch):
    from datetime import datetime, timedelta, timezone
    tmp_db.upsert_subscriber("d@example.com")
    token = tmp_db.create_auth_token("d@example.com")
    # Manually expire the token
    import sqlite3
    conn = sqlite3.connect(os.environ["SUBSCRIBERS_DB"])
    past = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    conn.execute("UPDATE auth_tokens SET expires_at = ? WHERE token = ?", (past, token))
    conn.commit()
    conn.close()
    assert tmp_db.consume_auth_token(token) is None


def test_token_nonexistent_returns_none(tmp_db):
    assert tmp_db.consume_auth_token("not-a-real-token") is None
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd bot && pytest tests/test_db.py -v
```

Expected: `ModuleNotFoundError: No module named 'db'`

- [ ] **Step 3: Create `bot/db.py`**

```python
# bot/db.py  --  SQLite subscriber store
import json
import os
import pathlib
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

_REPO_ROOT = pathlib.Path(__file__).parent.parent
DB_PATH = os.environ.get("SUBSCRIBERS_DB", str(_REPO_ROOT / "subscribers.db"))


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS subscribers (
                email      TEXT PRIMARY KEY,
                tier       TEXT    NOT NULL DEFAULT 'free',
                topics     TEXT    NOT NULL DEFAULT '[]',
                active     INTEGER NOT NULL DEFAULT 1,
                created_at TEXT    NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS auth_tokens (
                token      TEXT PRIMARY KEY,
                email      TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                used       INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (email) REFERENCES subscribers(email)
            )
        """)
        conn.commit()


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["topics"] = json.loads(d["topics"])
    return d


def get_subscribers(active_only: bool = True) -> list[dict]:
    with _connect() as conn:
        if active_only:
            rows = conn.execute(
                "SELECT * FROM subscribers WHERE active = 1"
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM subscribers").fetchall()
    return [_row_to_dict(r) for r in rows]


def get_subscriber(email: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM subscribers WHERE email = ?", (email,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def upsert_subscriber(
    email: str,
    tier: str = "free",
    topics: list[str] | None = None,
    active: int = 1,
) -> None:
    topics = topics or []
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO subscribers (email, tier, topics, active, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(email) DO UPDATE SET
                tier       = excluded.tier,
                topics     = excluded.topics,
                active     = excluded.active
            """,
            (email, tier, json.dumps(topics), active, now),
        )
        conn.commit()


def create_auth_token(email: str) -> str:
    token = str(uuid.uuid4())
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO auth_tokens (token, email, expires_at, used) VALUES (?, ?, ?, 0)",
            (token, email, expires_at),
        )
        conn.commit()
    return token


def consume_auth_token(token: str) -> str | None:
    """Return email if token is valid and unused. Return None otherwise."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT email, expires_at, used FROM auth_tokens WHERE token = ?",
            (token,),
        ).fetchone()
        if row is None or row["used"]:
            return None
        expires = datetime.fromisoformat(row["expires_at"])
        if datetime.now(timezone.utc) > expires:
            return None
        conn.execute(
            "UPDATE auth_tokens SET used = 1 WHERE token = ?", (token,)
        )
        conn.commit()
        return row["email"]
```

- [ ] **Step 4: Run tests to verify they pass**

```
cd bot && pytest tests/test_db.py -v
```

Expected: 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add bot/db.py bot/tests/test_db.py
git commit -m "feat: add SQLite subscriber database module"
```

---

## Task 2: CSV migration script (`bot/migrate_subscribers.py`)

**Files:**
- Create: `bot/migrate_subscribers.py`
- Create: `bot/tests/test_migrate_subscribers.py`

- [ ] **Step 1: Write failing test**

Create `bot/tests/test_migrate_subscribers.py`:

```python
import csv
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def setup(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("SUBSCRIBERS_DB", db_path)
    import db
    db.init_db()

    csv_path = tmp_path / "subscribers.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["email", "active"])
        writer.writeheader()
        writer.writerow({"email": "alice@example.com", "active": "true"})
        writer.writerow({"email": "bob@example.com",   "active": "false"})

    return db, str(csv_path)


def test_migration_imports_all_rows(setup):
    db, csv_path = setup
    import migrate_subscribers
    migrate_subscribers.migrate(csv_path)

    subs = db.get_subscribers(active_only=False)
    emails = {s["email"] for s in subs}
    assert "alice@example.com" in emails
    assert "bob@example.com" in emails


def test_migration_preserves_active_flag(setup):
    db, csv_path = setup
    import migrate_subscribers
    migrate_subscribers.migrate(csv_path)

    alice = db.get_subscriber("alice@example.com")
    bob   = db.get_subscriber("bob@example.com")
    assert alice["active"] == 1
    assert bob["active"]   == 0


def test_migration_sets_free_tier(setup):
    db, csv_path = setup
    import migrate_subscribers
    migrate_subscribers.migrate(csv_path)

    alice = db.get_subscriber("alice@example.com")
    assert alice["tier"] == "free"
    assert alice["topics"] == []


def test_migration_idempotent(setup):
    db, csv_path = setup
    import migrate_subscribers
    migrate_subscribers.migrate(csv_path)
    migrate_subscribers.migrate(csv_path)  # run twice

    subs = db.get_subscribers(active_only=False)
    assert len(subs) == 2  # no duplicates
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd bot && pytest tests/test_migrate_subscribers.py -v
```

Expected: `ModuleNotFoundError: No module named 'migrate_subscribers'`

- [ ] **Step 3: Create `bot/migrate_subscribers.py`**

```python
# bot/migrate_subscribers.py  --  One-time CSV -> SQLite migration
import csv
import os
import pathlib
import sys

sys.path.insert(0, os.path.dirname(__file__))
import db

_REPO_ROOT = pathlib.Path(__file__).parent.parent
_DEFAULT_CSV = str(_REPO_ROOT / "subscribers.csv")


def migrate(csv_path: str = _DEFAULT_CSV) -> None:
    if not os.path.exists(csv_path):
        print(f"[migrate] No CSV found at {csv_path} -- nothing to do.")
        return

    db.init_db()
    count = 0
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            email  = row.get("email", "").strip()
            active = 0 if row.get("active", "true").strip().lower() == "false" else 1
            if not email:
                continue
            db.upsert_subscriber(email, tier="free", topics=[], active=active)
            count += 1

    print(f"[migrate] Migrated {count} subscriber(s) from {csv_path} to subscribers.db")


if __name__ == "__main__":
    migrate()
```

- [ ] **Step 4: Run tests to verify they pass**

```
cd bot && pytest tests/test_migrate_subscribers.py -v
```

Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add bot/migrate_subscribers.py bot/tests/test_migrate_subscribers.py
git commit -m "feat: add CSV to SQLite migration script"
```

---

## Task 3: Story filter (`bot/subscriber_filter.py`)

**Files:**
- Create: `bot/subscriber_filter.py`
- Create: `bot/tests/test_subscriber_filter.py`

- [ ] **Step 1: Write failing tests**

Create `bot/tests/test_subscriber_filter.py`:

```python
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from subscriber_filter import filter_stories

STORIES = [
    {"headline": "Peso weakens", "category": "latam"},
    {"headline": "S&P hits record", "category": "markets"},
    {"headline": "NATO summit", "category": "geopolitics"},
    {"headline": "Bitcoin rallies", "category": "crypto"},
]


def test_filter_by_single_topic():
    result = filter_stories(STORIES, ["crypto"])
    assert len(result) == 1
    assert result[0]["category"] == "crypto"


def test_filter_by_multiple_topics():
    result = filter_stories(STORIES, ["latam", "markets"])
    categories = {s["category"] for s in result}
    assert categories == {"latam", "markets"}


def test_all_topics_returns_all():
    result = filter_stories(STORIES, ["latam", "markets", "geopolitics", "crypto"])
    assert len(result) == len(STORIES)


def test_empty_topics_returns_full_list():
    result = filter_stories(STORIES, [])
    assert result == STORIES


def test_no_match_falls_back_to_full_list():
    result = filter_stories(STORIES, ["crypto"])
    # Remove crypto story, now no matches for "crypto" in remaining
    no_crypto = [s for s in STORIES if s["category"] != "crypto"]
    result = filter_stories(no_crypto, ["crypto"])
    assert result == no_crypto


def test_story_without_category_excluded():
    stories = [
        {"headline": "Has category", "category": "markets"},
        {"headline": "No category"},
    ]
    result = filter_stories(stories, ["markets"])
    assert len(result) == 1
    assert result[0]["headline"] == "Has category"


def test_empty_stories_returns_empty():
    assert filter_stories([], ["latam"]) == []
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd bot && pytest tests/test_subscriber_filter.py -v
```

Expected: `ModuleNotFoundError: No module named 'subscriber_filter'`

- [ ] **Step 3: Create `bot/subscriber_filter.py`**

```python
# bot/subscriber_filter.py  --  Filter digest stories by subscriber topic preferences

VALID_TOPICS = frozenset({"latam", "markets", "geopolitics", "crypto"})


def filter_stories(stories: list[dict], topics: list[str]) -> list[dict]:
    """
    Return stories whose 'category' field is in topics.
    Falls back to the full list if topics is empty or no stories match,
    so no subscriber ever receives an empty digest.
    """
    if not stories or not topics:
        return stories
    filtered = [s for s in stories if s.get("category") in topics]
    return filtered if filtered else stories
```

- [ ] **Step 4: Run tests to verify they pass**

```
cd bot && pytest tests/test_subscriber_filter.py -v
```

Expected: 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add bot/subscriber_filter.py bot/tests/test_subscriber_filter.py
git commit -m "feat: add story filter for paid tier topic preferences"
```

---

## Task 4: Add `category` field to Claude story schema (`bot/summarizer.py`)

**Files:**
- Modify: `bot/summarizer.py`
- Create: `bot/tests/test_summarizer_category.py`

- [ ] **Step 1: Write failing test**

Create `bot/tests/test_summarizer_category.py`:

```python
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import summarizer


def test_category_field_in_prompt():
    """The Claude prompt must instruct Claude to assign a category field."""
    # Access the prompt template by calling summarize_news with a mock client
    # We check the prompt text directly by inspecting the module source.
    import inspect
    source = inspect.getsource(summarizer)
    assert '"category"' in source
    assert "latam" in source
    assert "markets" in source
    assert "geopolitics" in source
    assert "crypto" in source


def test_category_values_are_valid():
    """filter_stories must recognise all category values from the prompt."""
    from subscriber_filter import VALID_TOPICS
    assert "latam"       in VALID_TOPICS
    assert "markets"     in VALID_TOPICS
    assert "geopolitics" in VALID_TOPICS
    assert "crypto"      in VALID_TOPICS
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd bot && pytest tests/test_summarizer_category.py -v
```

Expected: `test_category_field_in_prompt` FAILS (string not found in source)

- [ ] **Step 3: Add `category` to the Claude prompt in `bot/summarizer.py`**

In the `stories` array schema inside the prompt (around line 48), add the `category` field after `"tag"`:

Find this block:
```python
        "tag": "Uno de: Macro | FX | México | Comercio | Tasas | Mercados | Energía | Política",
```

Replace with:
```python
        "tag": "Uno de: Macro | FX | México | Comercio | Tasas | Mercados | Energía | Política",
        "category": "latam" | "markets" | "geopolitics" | "crypto",
```

In the EN stories block (around line 88), find:
```python
        "tag": "Same tag",
```

Replace with:
```python
        "tag": "Same tag",
        "category": "<same as above>",
```

In the `Reglas:` section (after line 103), add this rule:
```python
- category: Asigna el bucket más relevante: "latam" (México, LatAm económico/político), "markets" (mercados globales, tasas, commodities, FX), "geopolitics" (política internacional, comercio, sanciones), "crypto" (criptomonedas). Usa "latam" para historias ambiguas.
```

- [ ] **Step 4: Run tests to verify they pass**

```
cd bot && pytest tests/test_summarizer_category.py -v
```

Expected: 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add bot/summarizer.py bot/tests/test_summarizer_category.py
git commit -m "feat: add category field to Claude story schema"
```

---

## Task 5: Per-subscriber delivery (`bot/delivery.py` + `bot/main.py`)

**Files:**
- Modify: `bot/delivery.py`
- Modify: `bot/main.py`
- Create: `bot/tests/test_delivery_personalized.py`

- [ ] **Step 1: Write failing tests**

Create `bot/tests/test_delivery_personalized.py`:

```python
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

STORIES = [
    {"headline": "LatAm story",   "category": "latam",       "body": ".", "source": "X", "url": "", "tag": "México", "context_note": {"es": "", "en": ""}},
    {"headline": "Markets story", "category": "markets",     "body": ".", "source": "Y", "url": "", "tag": "Macro",  "context_note": {"es": "", "en": ""}},
    {"headline": "Crypto story",  "category": "crypto",      "body": ".", "source": "Z", "url": "", "tag": "Macro",  "context_note": {"es": "", "en": ""}},
]

DIGEST_ES = {
    "editor_note": "note",
    "narrative_thread": "thread",
    "sentiment": {"label_en": "Cautious", "label_es": "Cauteloso", "position": 50, "context_es": "", "context_en": ""},
    "stories": STORIES,
    "quote": {"text": "q", "attribution": "a"},
}

RENDER_KWARGS = dict(
    digest_es=DIGEST_ES,
    tickers=[],
    secondary_tickers=[],
    currency={},
    week_stories=[],
    issue_number=1,
    is_friday=False,
    wordcloud_filename=None,
    author="Test Author",
)


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("SUBSCRIBERS_DB", str(tmp_path / "test.db"))
    import db
    db.init_db()
    return db


def test_free_subscriber_receives_full_digest(tmp_db):
    tmp_db.upsert_subscriber("free@example.com", tier="free", topics=[])

    captured = []

    def fake_send(html, plain, recipient, sentiment_label):
        captured.append({"recipient": recipient, "html": html})

    with patch("delivery._send_single", side_effect=fake_send), \
         patch("delivery.build_html", return_value="<html>full</html>") as mock_html, \
         patch("delivery.build_plain", return_value="plain"):
        import delivery
        delivery.deliver(**RENDER_KWARGS)

    assert len(captured) == 1
    assert captured[0]["recipient"] == "free@example.com"
    # build_html called with full stories list
    call_digest = mock_html.call_args[1]["digest"]
    assert len(call_digest["stories"]) == 3


def test_paid_subscriber_receives_filtered_digest(tmp_db):
    tmp_db.upsert_subscriber("paid@example.com", tier="paid", topics=["crypto"])

    captured_stories = []

    def fake_html(digest, **kwargs):
        captured_stories.extend(digest["stories"])
        return "<html/>"

    with patch("delivery._send_single"), \
         patch("delivery.build_html", side_effect=fake_html), \
         patch("delivery.build_plain", return_value="plain"):
        import delivery
        delivery.deliver(**RENDER_KWARGS)

    assert len(captured_stories) == 1
    assert captured_stories[0]["category"] == "crypto"


def test_paid_no_topics_falls_back_to_full(tmp_db):
    tmp_db.upsert_subscriber("paid@example.com", tier="paid", topics=[])

    captured_stories = []

    def fake_html(digest, **kwargs):
        captured_stories.extend(digest["stories"])
        return "<html/>"

    with patch("delivery._send_single"), \
         patch("delivery.build_html", side_effect=fake_html), \
         patch("delivery.build_plain", return_value="plain"):
        import delivery
        delivery.deliver(**RENDER_KWARGS)

    assert len(captured_stories) == 3


def test_inactive_subscriber_skipped(tmp_db):
    tmp_db.upsert_subscriber("gone@example.com", tier="free", active=0)

    captured = []
    with patch("delivery._send_single", side_effect=lambda *a, **kw: captured.append(a)), \
         patch("delivery.build_html", return_value="<html/>"), \
         patch("delivery.build_plain", return_value="plain"):
        import delivery
        delivery.deliver(**RENDER_KWARGS)

    assert len(captured) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd bot && pytest tests/test_delivery_personalized.py -v
```

Expected: `ImportError` — `deliver` not defined in `delivery`

- [ ] **Step 3: Rewrite `bot/delivery.py`**

Replace the entire file with:

```python
# bot/delivery.py  --  Per-subscriber email delivery
import os
import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import db
from config import (
    EMAIL_SENDER, EMAIL_PASSWORD, NEWSLETTER_NAME,
    ENVIRONMENT, DEV_RECIPIENT,
)
from renderer import build_html, build_plain
from subscriber_filter import filter_stories


def _send_single(
    html: str,
    plain: str,
    recipient: str,
    sentiment_label: str = "Cautious",
) -> None:
    """Send one email to one recipient via Gmail SMTP."""
    today = date.today()
    months_es = ["","enero","febrero","marzo","abril","mayo","junio",
                 "julio","agosto","septiembre","octubre","noviembre","diciembre"]
    today_str = f"{today.day} de {months_es[today.month]} de {today.year}"
    subject   = f"{sentiment_label} | {NEWSLETTER_NAME} — {today_str}"

    msg            = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = EMAIL_SENDER
    msg["To"]      = recipient
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html,  "html"))

    smtp_port = int(os.environ.get("SMTP_PORT", 587))
    use_ssl   = os.environ.get("SMTP_USE_SSL", "false").lower() == "true"
    if use_ssl:
        import ssl as _ssl
        ctx = _ssl.create_default_context()
        server_cm = smtplib.SMTP_SSL("smtp.gmail.com", smtp_port, timeout=30, context=ctx)
    else:
        server_cm = smtplib.SMTP("smtp.gmail.com", smtp_port, timeout=30)

    with server_cm as server:
        if not use_ssl:
            server.ehlo(); server.starttls(); server.ehlo()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, recipient, msg.as_string())


def deliver(
    digest_es: dict,
    tickers: list,
    secondary_tickers: list,
    currency: dict,
    week_stories: list,
    issue_number: int,
    is_friday: bool,
    wordcloud_filename: str | None,
    author: str,
) -> None:
    """
    Load subscribers from DB. For each active subscriber:
      - free  -> render full digest, send
      - paid  -> filter stories by topics, render, send
    Dev mode sends only to DEV_RECIPIENT.
    """
    db.init_db()
    subscribers = db.get_subscribers(active_only=True)

    if ENVIRONMENT == "dev":
        if not DEV_RECIPIENT:
            print("  [delivery] DEV mode but DEV_RECIPIENT not set — skipping send.")
            return
        print(f"  [delivery] DEV mode — overriding recipients to: {DEV_RECIPIENT}")
        # Find the dev recipient record, or default to free tier
        dev_sub = db.get_subscriber(DEV_RECIPIENT) or {"email": DEV_RECIPIENT, "tier": "free", "topics": []}
        subscribers = [dev_sub]

    if not subscribers:
        print("  [delivery] No subscribers found — skipping send.")
        return

    sentiment_label = digest_es.get("sentiment", {}).get("label_en", "Cautious")
    render_kwargs = dict(
        tickers=tickers,
        secondary_tickers=secondary_tickers,
        currency=currency,
        week_stories=week_stories,
        issue_number=issue_number,
        is_friday=is_friday,
        wordcloud_filename=wordcloud_filename,
        author=author,
    )

    print(f"  [delivery] Sending to {len(subscribers)} subscriber(s)...")

    try:
        for sub in subscribers:
            if sub["tier"] == "paid" and sub.get("topics"):
                stories    = filter_stories(digest_es["stories"], sub["topics"])
                sub_digest = {**digest_es, "stories": stories}
                tag        = "[paid/filtered]"
            else:
                sub_digest = digest_es
                tag        = "[free]"

            html  = build_html(digest=sub_digest, **render_kwargs)
            plain = build_plain(sub_digest, author=author)
            _send_single(html, plain, sub["email"], sentiment_label)
            print(f"  [delivery] Sent {tag} to {sub['email']}")

        print(f"  [delivery] Done — {len(subscribers)} email(s) sent.")
    except Exception as e:
        print(f"  [delivery] Email send failed: {e}")
        raise
```

- [ ] **Step 4: Update `bot/main.py` to call `deliver()` instead of `send_email()`**

In `bot/main.py`, find the import line:
```python
from delivery    import send_email
```

Replace with:
```python
from delivery    import deliver
```

Find the email sending block:
```python
    html  = build_html(
        digest             = digest_es,
        tickers            = tickers,
        secondary_tickers  = secondary_tickers,
        currency           = currency,
        week_stories       = week_stories,
        issue_number       = issue_num,
        is_friday          = friday,
        wordcloud_filename = wordcloud_filename,
        author             = author,
    )
    plain = build_plain(digest_es, author=author)

    if SKIP_EMAIL:
        print("  [delivery] SKIP_EMAIL set — skipping send.")
    else:
        sentiment_label = digest_es.get("sentiment", {}).get("label_en", "Cautious")
        send_email(html, plain, sentiment_label=sentiment_label)
```

Replace with:
```python
    if SKIP_EMAIL:
        print("  [delivery] SKIP_EMAIL set — skipping send.")
    else:
        deliver(
            digest_es          = digest_es,
            tickers            = tickers,
            secondary_tickers  = secondary_tickers,
            currency           = currency,
            week_stories       = week_stories,
            issue_number       = issue_num,
            is_friday          = friday,
            wordcloud_filename = wordcloud_filename,
            author             = author,
        )
```

Also remove the `build_html` and `build_plain` imports from `main.py` since they're no longer used there:

Find:
```python
from renderer    import build_html, build_plain
```

Replace with:
```python
from renderer    import build_html, build_plain  # used by save_pretty_issue indirectly
```

Wait — check if `build_html`/`build_plain` are used anywhere else in `main.py` besides the send block. They are not — `save_pretty_issue` takes the raw `digest` dict and renders internally. So remove the import entirely:

Find:
```python
from renderer    import build_html, build_plain
```

Delete that line.

- [ ] **Step 5: Run tests to verify they pass**

```
cd bot && pytest tests/test_delivery_personalized.py -v
```

Expected: 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add bot/delivery.py bot/main.py bot/tests/test_delivery_personalized.py
git commit -m "feat: per-subscriber filtered delivery for paid tier"
```

---

## Task 6: Admin CLI (`bot/admin.py`)

**Files:**
- Create: `bot/admin.py`
- Create: `bot/tests/test_admin.py`

- [ ] **Step 1: Write failing tests**

Create `bot/tests/test_admin.py`:

```python
import io
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("SUBSCRIBERS_DB", str(tmp_path / "test.db"))
    import db
    db.init_db()
    db.upsert_subscriber("alice@example.com", tier="free")
    return db


def test_promote(tmp_db, capsys):
    import admin
    admin.run(["promote", "alice@example.com"])
    sub = tmp_db.get_subscriber("alice@example.com")
    assert sub["tier"] == "paid"


def test_demote(tmp_db, capsys):
    tmp_db.upsert_subscriber("alice@example.com", tier="paid")
    import admin
    admin.run(["demote", "alice@example.com"])
    sub = tmp_db.get_subscriber("alice@example.com")
    assert sub["tier"] == "free"


def test_add(tmp_db, capsys):
    import admin
    admin.run(["add", "new@example.com"])
    sub = tmp_db.get_subscriber("new@example.com")
    assert sub is not None
    assert sub["tier"] == "free"
    assert sub["active"] == 1


def test_deactivate(tmp_db, capsys):
    import admin
    admin.run(["deactivate", "alice@example.com"])
    sub = tmp_db.get_subscriber("alice@example.com")
    assert sub["active"] == 0


def test_list_prints_subscribers(tmp_db, capsys):
    import admin
    admin.run(["list"])
    out = capsys.readouterr().out
    assert "alice@example.com" in out


def test_promote_unknown_email_prints_error(tmp_db, capsys):
    import admin
    admin.run(["promote", "nobody@example.com"])
    out = capsys.readouterr().out
    assert "not found" in out.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd bot && pytest tests/test_admin.py -v
```

Expected: `ModuleNotFoundError: No module named 'admin'`

- [ ] **Step 3: Create `bot/admin.py`**

```python
# bot/admin.py  --  CLI for subscriber tier management
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
import db


def run(args: list[str]) -> None:
    db.init_db()

    if not args:
        print("Usage: python admin.py <command> [email]")
        print("Commands: add, promote, demote, deactivate, list")
        return

    command = args[0]

    if command == "list":
        subs = db.get_subscribers(active_only=False)
        if not subs:
            print("No subscribers.")
            return
        print(f"{'EMAIL':<35} {'TIER':<8} {'ACTIVE':<8} TOPICS")
        print("-" * 70)
        for s in subs:
            topics = ", ".join(s["topics"]) or "(none)"
            active = "yes" if s["active"] else "no"
            print(f"{s['email']:<35} {s['tier']:<8} {active:<8} {topics}")
        return

    if len(args) < 2:
        print(f"Error: '{command}' requires an email address.")
        return

    email = args[1].strip()

    if command == "add":
        db.upsert_subscriber(email, tier="free", topics=[], active=1)
        print(f"Added: {email} (free tier)")
        return

    sub = db.get_subscriber(email)
    if sub is None:
        print(f"Error: {email} not found in database.")
        return

    if command == "promote":
        db.upsert_subscriber(email, tier="paid", topics=sub["topics"], active=sub["active"])
        print(f"Promoted: {email} -> paid")

    elif command == "demote":
        db.upsert_subscriber(email, tier="free", topics=sub["topics"], active=sub["active"])
        print(f"Demoted: {email} -> free")

    elif command == "deactivate":
        db.upsert_subscriber(email, tier=sub["tier"], topics=sub["topics"], active=0)
        print(f"Deactivated: {email}")

    else:
        print(f"Unknown command: {command}")
        print("Commands: add, promote, demote, deactivate, list")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    run(sys.argv[1:])
```

- [ ] **Step 4: Run tests to verify they pass**

```
cd bot && pytest tests/test_admin.py -v
```

Expected: 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add bot/admin.py bot/tests/test_admin.py
git commit -m "feat: add admin CLI for subscriber tier management"
```

---

## Task 7: Flask portal — setup + auth routes (`web/app.py`)

**Files:**
- Create: `web/app.py`
- Create: `web/requirements.txt`
- Create: `web/templates/index.html`
- Create: `web/templates/auth_sent.html`
- Create: `web/templates/auth_error.html`
- Create: `web/tests/test_auth.py`

- [ ] **Step 1: Create `web/requirements.txt`**

```
flask>=3.0
python-dotenv
```

- [ ] **Step 2: Write failing auth tests**

Create `web/tests/test_auth.py`:

```python
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "bot"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("SUBSCRIBERS_DB", db_path)
    monkeypatch.setenv("PORTAL_SECRET_KEY", "test-secret")
    monkeypatch.setenv("PORTAL_BASE_URL", "http://localhost:5000")

    import db
    db.init_db()
    db.upsert_subscriber("user@example.com", tier="paid", topics=["latam"])

    import importlib
    import app as portal_app
    importlib.reload(portal_app)
    portal_app.app.config["TESTING"] = True
    with portal_app.app.test_client() as c:
        yield c, db


def test_index_returns_200(client):
    c, _ = client
    resp = c.get("/")
    assert resp.status_code == 200


def test_auth_request_unknown_email_returns_200(client):
    """Returns 200 silently to prevent email enumeration."""
    c, _ = client
    resp = c.post("/auth/request", data={"email": "unknown@example.com"})
    assert resp.status_code == 200


def test_auth_request_known_email_sends_link(client, monkeypatch):
    c, db_module = client
    sent = []
    monkeypatch.setattr("app.send_magic_link_email", lambda email, token, base: sent.append(token))
    resp = c.post("/auth/request", data={"email": "user@example.com"})
    assert resp.status_code == 200
    assert len(sent) == 1


def test_auth_verify_valid_token_sets_session(client, monkeypatch):
    c, db_module = client
    monkeypatch.setattr("app.send_magic_link_email", lambda *a: None)
    # Create a real token
    token = db_module.create_auth_token("user@example.com")
    resp = c.get(f"/auth/verify?token={token}", follow_redirects=False)
    assert resp.status_code == 302
    assert "/preferences" in resp.headers["Location"]


def test_auth_verify_invalid_token_returns_error(client):
    c, _ = client
    resp = c.get("/auth/verify?token=bad-token-uuid")
    assert resp.status_code == 200
    assert b"expired" in resp.data.lower() or b"invalid" in resp.data.lower()


def test_auth_verify_missing_token_returns_error(client):
    c, _ = client
    resp = c.get("/auth/verify")
    assert resp.status_code == 200
```

- [ ] **Step 3: Run tests to verify they fail**

```
cd web && python -m pytest tests/test_auth.py -v
```

Expected: `ModuleNotFoundError: No module named 'app'`

- [ ] **Step 4: Create `web/app.py`**

```python
# web/app.py  --  Preference portal for paid subscribers
import os
import smtplib
import sys
from datetime import timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import (
    Flask, redirect, render_template, request, session, url_for
)

# Make bot/ importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bot"))
import db
from config import EMAIL_SENDER, EMAIL_PASSWORD, NEWSLETTER_NAME

app = Flask(__name__)
app.secret_key = os.environ.get("PORTAL_SECRET_KEY", "dev-secret-change-in-prod")
app.permanent_session_lifetime = timedelta(days=7)

PORTAL_BASE_URL = os.environ.get("PORTAL_BASE_URL", "http://localhost:5000")

TOPIC_BUCKETS = [
    ("latam",       "LatAm",          "Mexico, LatAm economics & politics"),
    ("markets",     "Global Markets", "Rates, commodities, FX, equities"),
    ("geopolitics", "Geopolitics",    "International politics, trade policy"),
    ("crypto",      "Crypto",         "Bitcoin, Ethereum, digital assets"),
]


# ── Helpers ──────────────────────────────────────

def send_magic_link_email(email: str, token: str, base_url: str) -> None:
    link    = f"{base_url}/auth/verify?token={token}"
    subject = f"{NEWSLETTER_NAME} — Your login link"
    body    = f"Click to access your preferences (expires in 1 hour):\n\n{link}\n\nIf you didn't request this, ignore it."
    html    = f"<p>Click to access your preferences (expires in 1 hour):</p><p><a href='{link}'>{link}</a></p>"

    msg            = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = EMAIL_SENDER
    msg["To"]      = email
    msg.attach(MIMEText(body, "plain"))
    msg.attach(MIMEText(html, "html"))

    smtp_port = int(os.environ.get("SMTP_PORT", 587))
    use_ssl   = os.environ.get("SMTP_USE_SSL", "false").lower() == "true"
    if use_ssl:
        import ssl as _ssl
        ctx = _ssl.create_default_context()
        server_cm = smtplib.SMTP_SSL("smtp.gmail.com", smtp_port, timeout=10, context=ctx)
    else:
        server_cm = smtplib.SMTP("smtp.gmail.com", smtp_port, timeout=10)

    with server_cm as server:
        if not use_ssl:
            server.ehlo(); server.starttls(); server.ehlo()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, email, msg.as_string())


# ── Routes ───────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html", newsletter=NEWSLETTER_NAME)


@app.route("/auth/request", methods=["POST"])
def auth_request():
    email = request.form.get("email", "").strip().lower()
    sub   = db.get_subscriber(email) if email else None
    if sub and sub["active"]:
        token = db.create_auth_token(email)
        try:
            send_magic_link_email(email, token, PORTAL_BASE_URL)
        except Exception as exc:
            app.logger.error(f"[auth] Failed to send magic link to {email}: {exc}")
    # Always return the same page (prevents email enumeration)
    return render_template("auth_sent.html", newsletter=NEWSLETTER_NAME)


@app.route("/auth/verify")
def auth_verify():
    token = request.args.get("token", "")
    email = db.consume_auth_token(token) if token else None
    if not email:
        return render_template("auth_error.html", newsletter=NEWSLETTER_NAME)
    session.permanent = True
    session["email"]  = email
    return redirect(url_for("preferences"))


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", "bot", ".env"))
    db.init_db()
    app.run(host="0.0.0.0", port=5000, debug=False)
```

- [ ] **Step 5: Create templates**

Create `web/templates/index.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{ newsletter }} — Preferences</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { background: #dde3e8; font-family: 'DM Sans', Arial, sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; padding: 24px; }
    .card { background: #f0f3f5; border: 1px solid #cdd4d9; padding: 40px; max-width: 440px; width: 100%; }
    h1 { font-size: 22px; font-weight: 700; color: #1a1a1a; margin-bottom: 6px; }
    p  { font-size: 13px; color: #5a6670; margin-bottom: 24px; line-height: 1.5; }
    label { display: block; font-size: 11px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; color: #5a6670; margin-bottom: 6px; }
    input[type="email"] { width: 100%; padding: 11px 14px; background: #fff; border: 1px solid #cdd4d9; font-size: 14px; color: #1a1a1a; outline: none; }
    input[type="email"]:focus { border-color: #3a4a54; }
    button { width: 100%; margin-top: 14px; padding: 12px; background: #1a1a1a; color: #f5f2ed; font-size: 13px; font-weight: 700; letter-spacing: 1px; border: none; cursor: pointer; }
    button:hover { background: #2a2a2a; }
  </style>
</head>
<body>
  <div class="card">
    <h1>{{ newsletter }}</h1>
    <p>Enter your subscriber email to access your topic preferences. We'll send you a login link.</p>
    <form method="POST" action="/auth/request">
      <label for="email">Subscriber email</label>
      <input type="email" id="email" name="email" placeholder="you@example.com" required autofocus>
      <button type="submit">Send login link</button>
    </form>
  </div>
</body>
</html>
```

Create `web/templates/auth_sent.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{{ newsletter }} — Check your email</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { background: #dde3e8; font-family: Arial, sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; padding: 24px; }
    .card { background: #f0f3f5; border: 1px solid #cdd4d9; padding: 40px; max-width: 440px; width: 100%; }
    h1 { font-size: 20px; font-weight: 700; color: #1a1a1a; margin-bottom: 12px; }
    p  { font-size: 13px; color: #5a6670; line-height: 1.6; }
    a  { color: #1a1a1a; }
  </style>
</head>
<body>
  <div class="card">
    <h1>Check your inbox</h1>
    <p>If that email address is on our subscriber list, you'll receive a login link shortly. The link expires in 1 hour.</p>
    <p style="margin-top:16px"><a href="/">&larr; Back</a></p>
  </div>
</body>
</html>
```

Create `web/templates/auth_error.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{{ newsletter }} — Link expired</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { background: #dde3e8; font-family: Arial, sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; padding: 24px; }
    .card { background: #f0f3f5; border: 1px solid #cdd4d9; padding: 40px; max-width: 440px; width: 100%; }
    h1 { font-size: 20px; font-weight: 700; color: #1a1a1a; margin-bottom: 12px; }
    p  { font-size: 13px; color: #5a6670; line-height: 1.6; }
    a  { color: #1a1a1a; }
  </style>
</head>
<body>
  <div class="card">
    <h1>Link invalid or expired</h1>
    <p>This login link has expired or was already used. Login links are valid for 1 hour and can only be used once.</p>
    <p style="margin-top:16px"><a href="/">Request a new link &rarr;</a></p>
  </div>
</body>
</html>
```

- [ ] **Step 6: Run tests to verify they pass**

```
cd web && python -m pytest tests/test_auth.py -v
```

Expected: 6 tests PASS

- [ ] **Step 7: Commit**

```bash
git add web/app.py web/requirements.txt web/templates/
git commit -m "feat: add Flask preference portal with magic link auth"
```

---

## Task 8: Preferences routes (`web/app.py` + template)

**Files:**
- Modify: `web/app.py`
- Create: `web/templates/preferences.html`
- Create: `web/tests/test_preferences.py`

- [ ] **Step 1: Write failing tests**

Create `web/tests/test_preferences.py`:

```python
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "bot"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("SUBSCRIBERS_DB", db_path)
    monkeypatch.setenv("PORTAL_SECRET_KEY", "test-secret")
    monkeypatch.setenv("PORTAL_BASE_URL", "http://localhost:5000")

    import db
    db.init_db()
    db.upsert_subscriber("paid@example.com", tier="paid", topics=["latam"])
    db.upsert_subscriber("free@example.com", tier="free", topics=[])

    import importlib
    import app as portal_app
    importlib.reload(portal_app)
    portal_app.app.config["TESTING"] = True
    with portal_app.app.test_client() as c:
        yield c, db


def _login(c, email):
    """Set session as if user completed magic link auth."""
    with c.session_transaction() as sess:
        sess["email"] = email


def test_preferences_requires_auth(client):
    c, _ = client
    resp = c.get("/preferences", follow_redirects=False)
    assert resp.status_code == 302
    assert "/" in resp.headers["Location"]


def test_preferences_loads_for_paid_user(client):
    c, _ = client
    _login(c, "paid@example.com")
    resp = c.get("/preferences")
    assert resp.status_code == 200
    assert b"latam" in resp.data.lower() or b"LatAm".encode() in resp.data


def test_preferences_shows_upgrade_prompt_for_free_user(client):
    c, _ = client
    _login(c, "free@example.com")
    resp = c.get("/preferences")
    assert resp.status_code == 200
    assert b"upgrade" in resp.data.lower() or b"paid" in resp.data.lower()


def test_save_preferences_updates_db(client):
    c, db_module = client
    _login(c, "paid@example.com")
    resp = c.post("/preferences", data={"topics": ["markets", "crypto"]})
    assert resp.status_code == 200
    sub = db_module.get_subscriber("paid@example.com")
    assert set(sub["topics"]) == {"markets", "crypto"}


def test_save_preferences_free_user_rejected(client):
    c, db_module = client
    _login(c, "free@example.com")
    c.post("/preferences", data={"topics": ["markets"]})
    sub = db_module.get_subscriber("free@example.com")
    assert sub["topics"] == []  # not updated
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd web && python -m pytest tests/test_preferences.py -v
```

Expected: `test_preferences_requires_auth` FAILS (no `/preferences` route yet)

- [ ] **Step 3: Add preferences routes to `web/app.py`**

Add these two routes after the `auth_verify` route in `web/app.py`:

```python
@app.route("/preferences", methods=["GET"])
def preferences():
    email = session.get("email")
    if not email:
        return redirect(url_for("index"))
    sub = db.get_subscriber(email)
    if not sub or not sub["active"]:
        return redirect(url_for("index"))
    return render_template(
        "preferences.html",
        newsletter=NEWSLETTER_NAME,
        subscriber=sub,
        topic_buckets=TOPIC_BUCKETS,
    )


@app.route("/preferences", methods=["POST"])
def save_preferences():
    email = session.get("email")
    if not email:
        return redirect(url_for("index"))
    sub = db.get_subscriber(email)
    if not sub or not sub["active"] or sub["tier"] != "paid":
        return redirect(url_for("preferences"))

    valid = {t[0] for t in TOPIC_BUCKETS}
    selected = [t for t in request.form.getlist("topics") if t in valid]
    db.upsert_subscriber(email, tier=sub["tier"], topics=selected, active=sub["active"])

    return render_template(
        "preferences.html",
        newsletter=NEWSLETTER_NAME,
        subscriber=db.get_subscriber(email),
        topic_buckets=TOPIC_BUCKETS,
        saved=True,
    )
```

- [ ] **Step 4: Create `web/templates/preferences.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{{ newsletter }} — Your Preferences</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { background: #dde3e8; font-family: Arial, sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; padding: 24px; }
    .card { background: #f0f3f5; border: 1px solid #cdd4d9; padding: 40px; max-width: 480px; width: 100%; }
    h1   { font-size: 20px; font-weight: 700; color: #1a1a1a; margin-bottom: 4px; }
    .sub { font-size: 11px; letter-spacing: 1.5px; text-transform: uppercase; color: #aab4bc; margin-bottom: 24px; }
    .section-label { font-size: 9px; font-weight: 700; letter-spacing: 2.5px; text-transform: uppercase; color: #aab4bc; margin-bottom: 14px; }
    .bucket { display: flex; align-items: flex-start; gap: 12px; padding: 14px 0; border-bottom: 1px solid #e0e5e8; }
    .bucket:last-of-type { border-bottom: none; }
    .bucket input[type="checkbox"] { margin-top: 3px; accent-color: #1a1a1a; width: 15px; height: 15px; flex-shrink: 0; }
    .bucket input:disabled { opacity: 0.35; }
    .bucket-name { font-size: 14px; font-weight: 700; color: #1a1a1a; }
    .bucket-desc { font-size: 12px; color: #5a6670; margin-top: 2px; }
    .upgrade { background: #fff8e6; border: 1px solid #f0d070; padding: 14px; font-size: 12px; color: #7a6020; margin-bottom: 20px; }
    .success { background: #e8f5e9; border: 1px solid #a5d6a7; padding: 12px; font-size: 12px; color: #2e7d32; margin-bottom: 16px; }
    button { width: 100%; margin-top: 20px; padding: 12px; background: #1a1a1a; color: #f5f2ed; font-size: 13px; font-weight: 700; letter-spacing: 1px; border: none; cursor: pointer; }
    button:hover { background: #2a2a2a; }
    button:disabled { opacity: 0.4; cursor: default; }
    .email-line { font-size: 11px; color: #aab4bc; margin-bottom: 20px; }
  </style>
</head>
<body>
  <div class="card">
    <h1>{{ newsletter }}</h1>
    <div class="sub">Topic preferences</div>
    <div class="email-line">{{ subscriber.email }}</div>

    {% if saved %}
    <div class="success">Preferences saved.</div>
    {% endif %}

    {% if subscriber.tier != 'paid' %}
    <div class="upgrade">
      Topic filtering is available on the paid tier. Upgrade to customize your digest.
    </div>
    {% endif %}

    <div class="section-label">Choose your topics</div>

    <form method="POST" action="/preferences">
      {% for key, name, desc in topic_buckets %}
      <div class="bucket">
        <input
          type="checkbox"
          name="topics"
          value="{{ key }}"
          id="t-{{ key }}"
          {% if key in subscriber.topics %}checked{% endif %}
          {% if subscriber.tier != 'paid' %}disabled{% endif %}
        >
        <label for="t-{{ key }}">
          <div class="bucket-name">{{ name }}</div>
          <div class="bucket-desc">{{ desc }}</div>
        </label>
      </div>
      {% endfor %}

      <button type="submit" {% if subscriber.tier != 'paid' %}disabled{% endif %}>
        Save preferences
      </button>
    </form>
  </div>
</body>
</html>
```

- [ ] **Step 5: Run all web tests**

```
cd web && python -m pytest tests/ -v
```

Expected: 11 tests PASS

- [ ] **Step 6: Run all bot tests to verify no regressions**

```
cd bot && pytest tests/ -v
```

Expected: all existing tests PASS

- [ ] **Step 7: Commit**

```bash
git add web/app.py web/templates/preferences.html web/tests/test_preferences.py
git commit -m "feat: add topic preferences form for paid subscribers"
```

---

## Final: Run migration on VPS

After deploying, run the migration once to populate `subscribers.db` from the existing `subscribers.csv`:

```bash
cd /path/to/repo/bot
python migrate_subscribers.py
```

Verify:

```bash
python admin.py list
```

Expected: existing subscribers listed, all with `tier=free`, `active=yes`.

---

## Environment variables to add

Add to the VPS `.env` (in `bot/`):

```
# Already present — no change needed:
# EMAIL_SENDER, EMAIL_PASSWORD

# New — required for the portal:
PORTAL_SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
PORTAL_BASE_URL=http://<your-domain-or-vps-ip>:5000
SUBSCRIBERS_DB=/path/to/repo/subscribers.db
```
