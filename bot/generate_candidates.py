# bot/generate_candidates.py
# ─────────────────────────────────────────────
#  Generate hero image candidates for a given issue.
#
#  Usage (run from bot/):
#    python generate_candidates.py [--date YYYY-MM-DD]
#
#  Defaults to today's date.
#  Reads digest from digests/YYYY-MM-DD.json.
#  Writes candidates to tmp_images/YYYY-MM-DD/.
#  Sends photos + control message to Telegram.
#
#  Idempotent: exits cleanly if candidates already exist
#  on disk for the current round, or if hero_image is set.
# ─────────────────────────────────────────────

import argparse
import json
import os
import pathlib
from datetime import date

import requests

from config import DIGEST_DIR
from image_candidates import generate_image_candidates

PROJECT_ROOT = str(pathlib.Path(DIGEST_DIR).parent)


# ── Telegram delivery ──────────────────────────

def _send_candidate_photos(token: str, chat_id: str, issue_date: str, candidates: dict) -> None:
    """Send 3 candidate photos to Telegram, each with an individual Select button."""
    labels = {"opt1": "Option 1", "opt2": "Option 2", "opt3": "Option 3"}

    for key in ("opt1", "opt2", "opt3"):
        path = candidates.get(key)
        if not path or not os.path.exists(path):
            print(f"  [generate_candidates] Skipping {key}: file not found at {path}")
            continue

        keyboard = {
            "inline_keyboard": [[
                {
                    "text": f"Select {labels[key].split()[-1]}",
                    "callback_data": f"select|{issue_date}|{key}",
                }
            ]]
        }

        try:
            with open(path, "rb") as photo_file:
                resp = requests.post(
                    f"https://api.telegram.org/bot{token}/sendPhoto",
                    data={
                        "chat_id": chat_id,
                        "caption": labels[key],
                        "reply_markup": json.dumps(keyboard),
                    },
                    files={"photo": photo_file},
                    timeout=30,
                )
            if resp.ok:
                print(f"  [generate_candidates] Sent {key} photo.")
            else:
                print(f"  [generate_candidates] Failed {key}: {resp.status_code} {resp.text[:80]}")
        except Exception as exc:
            print(f"  [generate_candidates] Error sending {key} (non-fatal): {exc}")


def _send_control_message(token: str, chat_id: str, issue_date: str) -> None:
    """Send control message with Regenerate and Skip buttons."""
    keyboard = {
        "inline_keyboard": [[
            {"text": "Regenerate", "callback_data": f"regenerate|{issue_date}"},
            {"text": "Skip",       "callback_data": f"skip|{issue_date}"},
        ]]
    }

    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id":      chat_id,
                "text":         f"Which image do you want to use for {issue_date}?",
                "reply_markup": keyboard,
            },
            timeout=10,
        )
        if resp.ok:
            print("  [generate_candidates] Control message sent.")
        else:
            print(f"  [generate_candidates] Control message failed: {resp.status_code} {resp.text[:80]}")
    except Exception as exc:
        print(f"  [generate_candidates] Error sending control message (non-fatal): {exc}")


# ── Core logic (extracted for testability) ────

def _load_and_run(
    issue_date: str,
    digest_dir: str,
    project_root: str,
    token: str,
    chat_id: str,
) -> None:
    """Load digest, generate candidates, update digest, send to Telegram."""
    digest_path = os.path.join(digest_dir, f"{issue_date}.json")
    if not os.path.exists(digest_path):
        print(f"  [generate_candidates] No digest found for {issue_date} at {digest_path} -- skipping.")
        return

    with open(digest_path, encoding="utf-8") as f:
        data = json.load(f)

    visual = data.get("visual", {})

    # Guard 1: already locked
    if visual.get("hero_image"):
        print(f"  [generate_candidates] Issue {issue_date} already locked (hero_image set). Nothing to do.")
        return

    # Guard 2: candidates already exist on disk for the current round
    current_round = visual.get("hero_generation_round", 1)
    existing_candidates = visual.get("hero_image_candidates", {})
    if existing_candidates:
        round_files = {
            k: p for k, p in existing_candidates.items()
            if f"r{current_round}_" in os.path.basename(p)
        }
        if round_files and all(os.path.exists(p) for p in round_files.values()):
            print(
                f"  [generate_candidates] Candidates already generated for round {current_round} "
                "and files exist on disk. Nothing to do. (Use regenerate flow to create new candidates.)"
            )
            return

    # Generate
    round_num = current_round
    new_candidates = generate_image_candidates(issue_date, visual, project_root, round_num)

    # Update visual block (init counters only if absent — never reset)
    visual["hero_image_candidates"] = new_candidates
    visual["hero_generation_round"] = visual.get("hero_generation_round", round_num)
    if "hero_regenerations_used" not in visual:
        visual["hero_regenerations_used"] = 0
    if "hero_image" not in visual:
        visual["hero_image"] = None
    data["visual"] = visual

    # Save digest
    with open(digest_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  [generate_candidates] Digest updated for {issue_date}.")

    # Send to Telegram (skip silently if credentials missing)
    if not token or not chat_id:
        print("  [generate_candidates] TELEGRAM_TOKEN or TELEGRAM_CHAT_ID not set -- skipping Telegram send.")
        return

    _send_candidate_photos(token, chat_id, issue_date, new_candidates)
    _send_control_message(token, chat_id, issue_date)


# ── Entrypoint ────────────────────────────────

def run(issue_date: str) -> None:
    print(f"\n[generate_candidates] Starting for {issue_date}...")
    token   = os.environ.get("TELEGRAM_TOKEN",  "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    _load_and_run(issue_date, DIGEST_DIR, PROJECT_ROOT, token, chat_id)


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Generate hero image candidates for a newsletter issue."
    )
    parser.add_argument(
        "--date",
        default=str(date.today()),
        help="Issue date (YYYY-MM-DD). Defaults to today.",
    )
    args = parser.parse_args()
    run(args.date)
