# bot/image_candidates.py
# ─────────────────────────────────────────────
#  Hero image candidate generation.
#
#  generate_image() is the provider stub.
#  Replace its body with a real API call when ready.
#  Signature (prompt, output_path) is stable — do not change.
#
#  generate_image_candidates() is the orchestrator.
#  It calls generate_image() 3 times and returns a
#  {opt1: path, opt2: path, opt3: path} mapping.
# ─────────────────────────────────────────────

import os


def generate_image(prompt: str, output_path: str) -> None:
    """
    Stub implementation: creates a solid-color placeholder PNG.

    TODO: Replace this body with a real provider call, e.g.:
        client = openai.OpenAI()
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1792x1024",
            quality="standard",
            n=1,
        )
        image_url = response.data[0].url
        img_data = requests.get(image_url).content
        with open(output_path, "wb") as f:
            f.write(img_data)

    The signature (prompt: str, output_path: str) must remain unchanged.
    """
    from PIL import Image, ImageDraw

    # Use a different hue per filename so options are visually distinct in Telegram
    basename = os.path.basename(output_path)
    if "opt1" in basename:
        bg = (28, 45, 65)
    elif "opt2" in basename:
        bg = (28, 62, 52)
    else:
        bg = (65, 42, 28)

    img = Image.new("RGB", (1200, 630), color=bg)
    draw = ImageDraw.Draw(img)
    draw.rectangle([40, 40, 1160, 590], outline=(160, 160, 160), width=2)
    # PIL default font — always available, no path needed
    draw.text((60, 60), f"[stub] {basename}", fill=(200, 200, 200))
    draw.text((60, 100), prompt[:100], fill=(140, 140, 140))
    img.save(output_path, "PNG")
    print(f"  [image_candidates] Stub image saved: {output_path}")


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
