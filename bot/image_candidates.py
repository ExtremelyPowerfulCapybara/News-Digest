# bot/image_candidates.py
# ─────────────────────────────────────────────
#  Hero image candidate generation.
#
#  generate_image() calls the OpenAI Images API.
#  Signature (prompt, output_path) is stable — do not change.
#
#  generate_image_candidates() is the orchestrator.
#  It calls generate_image() 3 times and returns a
#  {opt1: path, opt2: path, opt3: path} mapping.
# ─────────────────────────────────────────────

import base64
import os


def generate_image(prompt: str, output_path: str) -> None:
    """
    Generate one image from prompt and save it as a PNG at output_path.

    Reads from environment:
        OPENAI_API_KEY         -- required
        OPENAI_IMAGE_MODEL     -- default: gpt-image-1
        OPENAI_IMAGE_SIZE      -- default: 1024x1024
        OPENAI_IMAGE_QUALITY   -- default: medium
    """
    import openai

    model   = os.environ.get("OPENAI_IMAGE_MODEL",   "gpt-image-1")
    size    = os.environ.get("OPENAI_IMAGE_SIZE",    "1024x1024")
    quality = os.environ.get("OPENAI_IMAGE_QUALITY", "medium")

    print(f"  [image_candidates] Generating: model={model} size={size} quality={quality} -> {os.path.basename(output_path)}")

    client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    try:
        response = client.images.generate(
            model=model,
            prompt=prompt,
            size=size,
            quality=quality,
            n=1,
        )
    except openai.AuthenticationError as exc:
        raise RuntimeError(f"[image_candidates] OpenAI auth failed: {exc}") from exc
    except openai.RateLimitError as exc:
        raise RuntimeError(f"[image_candidates] OpenAI rate limit: {exc}") from exc
    except openai.APIConnectionError as exc:
        raise RuntimeError(f"[image_candidates] OpenAI connection error: {exc}") from exc
    except openai.OpenAIError as exc:
        raise RuntimeError(f"[image_candidates] OpenAI API error: {exc}") from exc

    b64_data = response.data[0].b64_json
    if not b64_data:
        raise RuntimeError("[image_candidates] OpenAI returned empty image data.")

    with open(output_path, "wb") as f:
        f.write(base64.b64decode(b64_data))

    print(f"  [image_candidates] Saved: {output_path}")


def generate_image_candidates(
    issue_date: str,
    visual: dict,
    project_root: str,
    round_num: int = 1,
) -> dict:
    """
    Generate 3 candidate images for the given issue and round.

    Creates tmp_images/YYYY-MM-DD/ under project_root if it does not exist.

    Returns:
        {"opt1": "/abs/path/rN_opt1.png", "opt2": ..., "opt3": ...}

    Raises:
        ValueError: if hero_options is missing or empty in visual.
    """
    hero_options = visual.get("hero_options", {})
    if not hero_options:
        raise ValueError(
            f"No hero_options found in visual block for {issue_date}. "
            "Run main.py first to generate the digest."
        )

    out_dir = os.path.join(project_root, "tmp_images", issue_date)
    os.makedirs(out_dir, exist_ok=True)

    candidates = {}
    for key in ("opt1", "opt2", "opt3"):
        prompt = hero_options.get(key, "")
        if not prompt:
            continue
        filename = f"r{round_num}_{key}.png"
        output_path = os.path.join(out_dir, filename)
        generate_image(prompt, output_path)
        candidates[key] = output_path

    return candidates
