# ─────────────────────────────────────────────
#  telegram_handler.py  --  Polls Telegram for
#  editorial callbacks and handles:
#    select|YYYY-MM-DD|optN   -- copy, verify, publish, rerender
#    regenerate|YYYY-MM-DD    -- new candidate batch (max 2)
#    skip|YYYY-MM-DD          -- no-op acknowledgement
#
#  Usage (run from bot/):
#    python telegram_handler.py
#
#  Requires: TELEGRAM_TOKEN env var.
#  Offset between runs is persisted in:
#    bot/.telegram_offset
# ─────────────────────────────────────────────

import json
import os
import pathlib
import shutil

import requests

from config import DIGEST_DIR, ARCHIVE_DIR
from image_candidates import generate_image_candidates
from generate_candidates import _send_candidate_photos, _send_control_message
from rerender import rerender
from publish_site import publish_site

_OFFSET_FILE = os.path.join(os.path.dirname(__file__), ".telegram_offset")

_MAX_REGENERATIONS = 2


# ── Offset persistence ────────────────────────

def _load_offset() -> int:
    if os.path.exists(_OFFSET_FILE):
        try:
            return int(open(_OFFSET_FILE).read().strip())
        except (ValueError, OSError):
            pass
    return 0


def _save_offset(offset: int) -> None:
    with open(_OFFSET_FILE, "w") as f:
        f.write(str(offset))


# ── Telegram helpers ──────────────────────────

def _answer_callback(token: str, callback_id: str, text: str = "") -> None:
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/answerCallbackQuery",
            json={"callback_query_id": callback_id, "text": text},
            timeout=5,
        )
    except Exception:
        pass


# ── Tmp candidate cleanup ─────────────────────

def _cleanup_tmp_candidates(issue_date: str, selected_key: str, candidates: dict) -> None:
    """Delete non-selected tmp candidate files. Non-fatal on any error."""
    for key, path in candidates.items():
        if key == selected_key:
            continue
        try:
            if os.path.exists(path):
                os.remove(path)
                print(f"  [telegram_handler] Deleted tmp: {os.path.basename(path)}")
        except OSError as exc:
            print(f"  [telegram_handler] Could not delete {path}: {exc} (non-fatal)")


# ── Selection handler ─────────────────────────

def _handle_select(token: str, cb_id: str, issue_date: str, key: str) -> None:
    """
    Copy selected candidate to docs/images/, verify, update digest, rerender.
    Safe order: copy -> verify -> update state -> save -> rerender -> cleanup.
    """
    path = os.path.join(DIGEST_DIR, f"{issue_date}.json")
    if not os.path.exists(path):
        _answer_callback(token, cb_id, "Issue not found.")
        return

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    visual = data.get("visual", {})

    # Guard: already locked
    if visual.get("hero_image"):
        _answer_callback(token, cb_id, "Already locked.")
        return

    # Validate key
    candidates = visual.get("hero_image_candidates", {})
    if key not in candidates:
        _answer_callback(token, cb_id, "Candidate key not found.")
        return

    src_path = candidates[key]
    if not os.path.exists(src_path):
        _answer_callback(token, cb_id, "Candidate file missing on disk.")
        return

    # 1. Copy to published location
    images_dir = os.path.join(ARCHIVE_DIR, "images")
    try:
        os.makedirs(images_dir, exist_ok=True)
    except OSError as exc:
        print(f"  [telegram_handler] Could not create images dir: {exc}")
        _answer_callback(token, cb_id, "Server error creating images dir.")
        return

    dst_path = os.path.join(images_dir, f"{issue_date}.png")
    try:
        shutil.copy2(src_path, dst_path)
    except OSError as exc:
        print(f"  [telegram_handler] Copy failed: {exc}")
        _answer_callback(token, cb_id, "Copy failed.")
        return

    # 2. Verify destination
    if not os.path.exists(dst_path):
        print(f"  [telegram_handler] Verification failed: {dst_path} not found after copy.")
        _answer_callback(token, cb_id, "Verification failed.")
        return

    # 3. Update state
    visual["hero_selected"] = key
    visual["hero_image"] = f"/images/{issue_date}.png"
    data["visual"] = visual

    # 4. Save digest
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # 5. Rerender archive
    try:
        rerender(issue_date)
    except Exception as exc:
        print(f"  [telegram_handler] Rerender error (non-fatal): {exc}")

    # 6. Publish updated site
    publish_site()

    # 8. Cleanup non-selected tmp candidates
    _cleanup_tmp_candidates(issue_date, key, candidates)

    # 9. Answer
    _answer_callback(token, cb_id, f"Saved: {key}")
    print(f"  [telegram_handler] Selection complete: {key} for {issue_date}.")


# ── Regeneration handler ──────────────────────

def _handle_regenerate(token: str, cb_id: str, issue_date: str) -> None:
    """
    Generate a new round of candidates.
    Bounded by _MAX_REGENERATIONS. Counters are incremented, never reset.
    Old-round tmp candidates are cleaned up after new round is saved.
    """
    path = os.path.join(DIGEST_DIR, f"{issue_date}.json")
    if not os.path.exists(path):
        _answer_callback(token, cb_id, "Issue not found.")
        return

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    visual = data.get("visual", {})

    # Guard: already locked
    if visual.get("hero_image"):
        _answer_callback(token, cb_id, "Already locked.")
        return

    # Check limit
    regen_used = visual.get("hero_regenerations_used", 0)
    if regen_used >= _MAX_REGENERATIONS:
        _answer_callback(token, cb_id, "No more regenerations allowed.")
        return

    # Answer callback early -- generation takes a moment
    _answer_callback(token, cb_id, "Generating new candidates...")

    # Snapshot old candidates before incrementing
    old_candidates = dict(visual.get("hero_image_candidates", {}))

    # Increment counters
    current_round = visual.get("hero_generation_round", 1)
    new_round     = current_round + 1
    visual["hero_generation_round"]   = new_round
    visual["hero_regenerations_used"] = regen_used + 1

    # Generate new candidates
    project_root = str(pathlib.Path(DIGEST_DIR).parent)
    try:
        new_candidates = generate_image_candidates(issue_date, visual, project_root, new_round)
    except Exception as exc:
        print(f"  [telegram_handler] Candidate generation error: {exc}")
        return

    visual["hero_image_candidates"] = new_candidates
    data["visual"] = visual

    # Save digest (new round saved before cleanup)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # Clean up previous-round tmp candidates (after digest is saved)
    for key, old_path in old_candidates.items():
        try:
            if os.path.exists(old_path) and old_path not in new_candidates.values():
                os.remove(old_path)
                print(f"  [telegram_handler] Deleted old round tmp: {os.path.basename(old_path)}")
        except OSError as exc:
            print(f"  [telegram_handler] Could not delete old tmp {old_path}: {exc} (non-fatal)")

    # Send new photos + control message
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if chat_id:
        _send_candidate_photos(token, chat_id, issue_date, new_candidates)
        _send_control_message(token, chat_id, issue_date)

    print(f"  [telegram_handler] Regeneration round {new_round} complete for {issue_date}.")


# ── Main poll function ────────────────────────

def process_telegram_updates() -> None:
    """
    Poll Telegram getUpdates once, process any pending callback_query updates,
    and persist the new offset so updates are not reprocessed.
    Non-fatal on all network errors.
    """
    print("[telegram_handler] Polling for updates...")
    token = os.environ.get("TELEGRAM_TOKEN", "")
    if not token:
        print("  [telegram_handler] TELEGRAM_TOKEN not set -- skipping.")
        return

    offset = _load_offset()

    try:
        resp = requests.get(
            f"https://api.telegram.org/bot{token}/getUpdates",
            params={
                "offset":          offset,
                "timeout":         5,
                "allowed_updates": json.dumps(["callback_query"]),
            },
            timeout=15,
        )
        if not resp.ok:
            print(f"  [telegram_handler] getUpdates failed: {resp.status_code} {resp.text[:120]}")
            return
        updates = resp.json().get("result", [])
    except Exception as exc:
        print(f"  [telegram_handler] Request error (non-fatal): {exc}")
        return

    new_offset = offset
    for update in updates:
        update_id  = update["update_id"]
        new_offset = update_id + 1

        cb = update.get("callback_query")
        if not cb:
            continue

        cb_id   = cb["id"]
        cb_data = cb.get("data", "")
        parts   = cb_data.split("|")

        if len(parts) < 2:
            _answer_callback(token, cb_id)
            continue

        action     = parts[0]
        issue_date = parts[1]

        if action == "skip":
            _answer_callback(token, cb_id, "Skipped.")
            print(f"  [telegram_handler] Skip received for {issue_date}.")

        elif action == "select" and len(parts) == 3:
            _handle_select(token, cb_id, issue_date, parts[2])

        elif action == "regenerate":
            _handle_regenerate(token, cb_id, issue_date)

        else:
            _answer_callback(token, cb_id)

    _save_offset(new_offset)
    if not updates:
        print("  [telegram_handler] No updates.")
    else:
        print(f"  [telegram_handler] Processed {len(updates)} update(s). Offset: {new_offset}")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    process_telegram_updates()
