# Isolated Preview Environment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route all preview pipeline output to isolated subfolders (`docs/preview/`, `digests/preview/`) and deploy them to GitHub Pages via GitHub Actions, keeping production VPS, `main` branch, and all production systems completely untouched.

**Architecture:** A single env var (`PREVIEW_MODE=true`) switches the two path constants in `config.py` (`DIGEST_DIR`, `ARCHIVE_DIR`) to preview subfolders. Every downstream module inherits the new paths with zero changes. A new workflow (`newsletter-preview.yml`) runs the pipeline with that flag set, commits preview artifacts to `Dev-Nigg`, and deploys the `docs/preview/` folder to GitHub Pages via `actions/deploy-pages`. GitHub Pages is reconfigured to use GitHub Actions as its source (one-time manual step).

**Tech Stack:** Python 3.11, GitHub Actions (`actions/checkout@v4`, `actions/setup-python@v5`, `actions/upload-pages-artifact@v3`, `actions/deploy-pages@v4`), GitHub Pages (Actions source mode)

---

## File Map

| Action | Path | What changes |
|--------|------|--------------|
| Modify | `bot/config.py` | Add `PREVIEW_MODE` flag; switch `DIGEST_DIR` / `ARCHIVE_DIR` conditionally |
| Create | `bot/test_preview_config.py` | Unit test: verify path switching under the env var |
| Create | `.github/workflows/newsletter-preview.yml` | New manual workflow — preview pipeline + Pages deployment |
| Manual | GitHub repo Settings → Pages | Switch source from "Deploy from branch" to "GitHub Actions" |

No other files need changes. All renderers, writers, `archive.py`, `storage.py`, and `publish_site.py` derive their paths from `DIGEST_DIR` / `ARCHIVE_DIR` and work correctly with new paths.

---

## Task 1: Switch GitHub Pages to Actions Source (Manual, One-Time)

This must be done before the preview workflow can deploy to Pages.

- [ ] **Step 1: Open repo Settings**

  Navigate to: `https://github.com/ExtremelyPowerfulCapybara/News-Digest/settings/pages`

- [ ] **Step 2: Change the source**

  Under **Build and deployment → Source**, change from:
  > `Deploy from a branch` → branch: `main`, folder: `/docs`

  To:
  > `GitHub Actions`

  Click **Save**. No further configuration needed — the workflow provides the artifact.

- [ ] **Step 3: Verify**

  The Pages settings panel should now show:
  > "Your GitHub Pages site is currently being built from a GitHub Actions workflow."

  The existing live Pages site (`https://extremelypowerfulcapybara.github.io/News-Digest/`) will go offline until the first preview workflow run deploys content. This is expected — production is served by the VPS, not Pages.

---

## Task 2: Add `PREVIEW_MODE` to `config.py`

**Files:**
- Modify: `bot/config.py` (lines 228–234)
- Create: `bot/test_preview_config.py`

- [ ] **Step 1: Write the failing test**

  Create `bot/test_preview_config.py`:

  ```python
  # bot/test_preview_config.py
  import importlib
  import os
  import sys


  def _reload_config(preview: bool):
      """Set PREVIEW_MODE and reload config, return the module."""
      if preview:
          os.environ["PREVIEW_MODE"] = "true"
      else:
          os.environ.pop("PREVIEW_MODE", None)
      if "config" in sys.modules:
          del sys.modules["config"]
      import config
      return config


  def test_default_paths_do_not_contain_preview():
      cfg = _reload_config(preview=False)
      assert "preview" not in cfg.DIGEST_DIR
      assert "preview" not in cfg.ARCHIVE_DIR
      assert cfg.DIGEST_DIR.endswith("digests")
      assert cfg.ARCHIVE_DIR.endswith("docs")


  def test_preview_mode_switches_to_preview_subfolders():
      cfg = _reload_config(preview=True)
      assert cfg.DIGEST_DIR.endswith("digests/preview") or cfg.DIGEST_DIR.endswith("digests\\preview")
      assert cfg.ARCHIVE_DIR.endswith("docs/preview") or cfg.ARCHIVE_DIR.endswith("docs\\preview")


  def test_preview_subfolders_are_children_of_repo_root():
      cfg = _reload_config(preview=True)
      import pathlib
      repo_root = pathlib.Path(cfg.REPO_ROOT)
      assert pathlib.Path(cfg.DIGEST_DIR).parent == repo_root / "digests"
      assert pathlib.Path(cfg.ARCHIVE_DIR).parent == repo_root / "docs"


  if __name__ == "__main__":
      test_default_paths_do_not_contain_preview()
      test_preview_mode_switches_to_preview_subfolders()
      test_preview_subfolders_are_children_of_repo_root()
      print("All tests passed.")
  ```

- [ ] **Step 2: Run the test to confirm it fails**

  ```bash
  cd bot
  python test_preview_config.py
  ```

  Expected: `AttributeError` or `AssertionError` on `test_preview_mode_switches_to_preview_subfolders` — `PREVIEW_MODE` has no effect yet.

- [ ] **Step 3: Edit `config.py` — add the flag and update path constants**

  Find this block in `bot/config.py` (around line 228):

  ```python
  # ── Storage paths ─────────────────────────────
  # Paths are relative to the repo root, not bot/
  # so digests and archive are committed together.
  import pathlib
  REPO_ROOT   = pathlib.Path(__file__).parent.parent
  DIGEST_DIR  = str(REPO_ROOT / "digests")
  ARCHIVE_DIR = str(REPO_ROOT / "docs")  # ARCHIVE_DIR is the source of truth for published site content (docs/)
  ```

  Replace with:

  ```python
  # ── Storage paths ─────────────────────────────
  # Paths are relative to the repo root, not bot/
  # so digests and archive are committed together.
  import pathlib
  REPO_ROOT    = pathlib.Path(__file__).parent.parent
  _preview     = os.environ.get("PREVIEW_MODE", "false").lower() == "true"
  DIGEST_DIR   = str(REPO_ROOT / ("digests/preview" if _preview else "digests"))
  ARCHIVE_DIR  = str(REPO_ROOT / ("docs/preview" if _preview else "docs"))
  ```

- [ ] **Step 4: Run the test to confirm it passes**

  ```bash
  cd bot
  python test_preview_config.py
  ```

  Expected output:
  ```
  All tests passed.
  ```

- [ ] **Step 5: Smoke-check that normal mode is unaffected**

  ```bash
  cd bot
  python -c "import config; print(config.DIGEST_DIR); print(config.ARCHIVE_DIR)"
  ```

  Expected (no `PREVIEW_MODE` set):
  ```
  /path/to/repo/digests
  /path/to/repo/docs
  ```

- [ ] **Step 6: Commit**

  ```bash
  git add bot/config.py bot/test_preview_config.py
  git commit -m "feat: add PREVIEW_MODE flag to route output to docs/preview and digests/preview"
  ```

---

## Task 3: Create `newsletter-preview.yml` Workflow

**Files:**
- Create: `.github/workflows/newsletter-preview.yml`

- [ ] **Step 1: Create the workflow file**

  Create `.github/workflows/newsletter-preview.yml` with this exact content:

  ```yaml
  # ─────────────────────────────────────────────
  #  .github/workflows/newsletter-preview.yml
  #
  #  Isolated preview environment.
  #  - Manual trigger only
  #  - Runs pipeline with PREVIEW_MODE=true
  #    (output goes to docs/preview/ and digests/preview/)
  #  - Never sends email, never syncs to VPS
  #  - Commits preview artifacts back to Dev-Nigg
  #  - Deploys docs/preview/ to GitHub Pages
  #    (visible at https://extremelypowerfulcapybara.github.io/News-Digest/)
  # ─────────────────────────────────────────────

  name: Newsletter Preview

  on:
    workflow_dispatch:
      inputs:
        mock_mode:
          description: "Mock mode? Skip NewsAPI + Anthropic, use latest saved digest"
          required: false
          default: "false"
          type: choice
          options:
            - "false"
            - "true"
        friday_mode:
          description: "Simulate Friday? Includes word cloud + week review"
          required: false
          default: "false"
          type: choice
          options:
            - "false"
            - "true"

  permissions:
    contents: write
    pages: write
    id-token: write

  concurrency:
    group: pages
    cancel-in-progress: false

  jobs:
    preview:
      runs-on: ubuntu-latest

      environment:
        name: github-pages
        url: ${{ steps.deployment.outputs.page_url }}

      steps:
        - name: Checkout Dev-Nigg
          uses: actions/checkout@v4
          with:
            ref: Dev-Nigg
            fetch-depth: 0

        - name: Set up Python 3.11
          uses: actions/setup-python@v5
          with:
            python-version: "3.11"

        - name: Install dependencies
          run: pip install --no-cache-dir -r requirements.txt

        - name: Write subscribers file
          run: |
            python3 -c "
            import os
            emails = os.environ['DEV_SUBSCRIBERS_CSV'].split(',')
            with open('subscribers.csv', 'w') as f:
                f.write('email,name,active\n')
                for e in emails:
                    e = e.strip()
                    if e:
                        f.write(f'{e},,true\n')
            "
          env:
            DEV_SUBSCRIBERS_CSV: ${{ secrets.DEV_SUBSCRIBERS_CSV }}

        - name: Run newsletter bot (preview mode)
          working-directory: bot
          env:
            PREVIEW_MODE:          "true"
            SKIP_EMAIL:            "true"
            MOCK:                  ${{ github.event.inputs.mock_mode }}
            FORCE_FRIDAY:          ${{ github.event.inputs.friday_mode }}
            NEWS_API_KEY:          ${{ secrets.NEWS_API_KEY }}
            ANTHROPIC_API_KEY:     ${{ secrets.ANTHROPIC_API_KEY }}
            EMAIL_SENDER:          ${{ secrets.EMAIL_SENDER }}
            EMAIL_PASSWORD:        ${{ secrets.EMAIL_PASSWORD }}
            SUBSCRIBERS:           ${{ secrets.DEV_SUBSCRIBERS_CSV }}
            PUBLIC_ARCHIVE_BASE_URL: "https://extremelypowerfulcapybara.github.io/News-Digest"
          run: python main.py

        - name: Commit preview artifacts to Dev-Nigg
          run: |
            git config user.name  "Newsletter Bot"
            git config user.email "bot@newsletter"

            git add docs/preview/ digests/preview/

            if git diff --staged --quiet; then
              echo "Nothing new to commit."
            else
              git commit -m "[PREVIEW] Issue: $(date +'%Y-%m-%d')"
              git push origin Dev-Nigg
            fi

        - name: Upload Pages artifact
          uses: actions/upload-pages-artifact@v3
          with:
            path: docs/preview/

        - name: Deploy to GitHub Pages
          id: deployment
          uses: actions/deploy-pages@v4
  ```

- [ ] **Step 2: Commit the workflow**

  ```bash
  git add .github/workflows/newsletter-preview.yml
  git commit -m "feat: add newsletter-preview workflow with Pages deployment"
  ```

- [ ] **Step 3: Push to Dev-Nigg**

  ```bash
  git push origin Dev-Nigg
  ```

  > **Note:** Workflow files must exist on `main` to appear in the GitHub Actions tab. Push to `Dev-Nigg` first, then promote to `main` (see Task 4).

---

## Task 4: Promote Workflow File to `main`

GitHub Actions only shows workflows from the default branch (`main`). The workflow YAML must land on `main` to be triggerable — but it will still run against `Dev-Nigg` (that's what `ref: Dev-Nigg` in the checkout step controls).

- [ ] **Step 1: Cherry-pick the workflow commit to `main`**

  ```bash
  git checkout main
  git pull origin main
  git cherry-pick Dev-Nigg -- .github/workflows/newsletter-preview.yml
  ```

  If cherry-pick isn't clean, copy the file manually:

  ```bash
  git checkout main
  git checkout Dev-Nigg -- .github/workflows/newsletter-preview.yml
  git add .github/workflows/newsletter-preview.yml
  git commit -m "feat: add newsletter-preview workflow"
  ```

- [ ] **Step 2: Push to `main`**

  ```bash
  git push origin main
  ```

- [ ] **Step 3: Verify the workflow appears in Actions tab**

  Navigate to: `https://github.com/ExtremelyPowerfulCapybara/News-Digest/actions`

  You should see **Newsletter Preview** in the left sidebar under "Workflows". If it does not appear within 1–2 minutes, hard-refresh the page.

---

## Task 5: End-to-End Verification Run

- [ ] **Step 1: Trigger the preview workflow**

  Go to: `https://github.com/ExtremelyPowerfulCapybara/News-Digest/actions/workflows/newsletter-preview.yml`

  Click **Run workflow** → select branch `main` (the workflow itself lives on `main`; it checks out `Dev-Nigg` internally) → set `mock_mode: true` for the first run (avoids spending API quota) → click **Run workflow**.

- [ ] **Step 2: Watch the run**

  Click into the running job. Confirm each step succeeds:
  - `Run newsletter bot (preview mode)` — should print `[generate_candidates]` or `[main]` logs; must NOT print `[delivery] Sending email`
  - `Commit preview artifacts to Dev-Nigg` — should show commit or "Nothing new to commit"
  - `Upload Pages artifact` — should succeed
  - `Deploy to GitHub Pages` — should print the live URL

- [ ] **Step 3: Open the preview URL**

  The deployment step prints a URL. It will be:
  ```
  https://extremelypowerfulcapybara.github.io/News-Digest/
  ```

  Open it. You should see the preview archive index. Click the latest issue to inspect the HTML output.

- [ ] **Step 4: Verify production systems are untouched**

  - SSH to VPS. Run:
    ```bash
    ls /var/www/newsletter/preview/
    ```
    Expected: `No such file or directory` (VPS was never touched)

  - Check `main` branch `docs/` folder locally or on GitHub:
    ```bash
    git checkout main && ls docs/
    ```
    Expected: no `preview/` subdirectory (preview files only live on Dev-Nigg and GitHub Pages)

  - Confirm no email was sent (check email inbox for dev subscribers — should be empty).

- [ ] **Step 5: Run once more without mock mode**

  Trigger again with `mock_mode: false`. This validates the full live pipeline runs cleanly in preview mode. Confirm the Pages URL updates with a real issue.

---

## Self-Review Notes

**Spec requirements covered:**
- Isolated output paths (`docs/preview/`, `digests/preview/`) — Task 2 ✓
- Separate deploy target (GitHub Pages via Actions) — Tasks 1 + 3 ✓
- No email — `SKIP_EMAIL=true` hardcoded in workflow, no input option ✓
- No VPS contact — `PUBLISH_WEB_ROOT` never set ✓
- No Telegram — `TELEGRAM_TOKEN` never set in preview workflow ✓
- Runs from Dev-Nigg — `ref: Dev-Nigg` in checkout ✓
- `main` not written by preview — only `docs/preview/` and `digests/preview/` committed to Dev-Nigg ✓
- Workflow visible in Actions tab — Task 4 promotes YAML to `main` ✓
- Asset URLs work in deployed Pages — `PUBLIC_ARCHIVE_BASE_URL` set to Pages URL ✓

**Known limitation:** The first time the workflow runs, Pages may take 1–3 minutes to propagate. Subsequent runs are faster. This is a GitHub Pages constraint, not a code issue.
