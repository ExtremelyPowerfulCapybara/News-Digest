# bot/image_gen.py
# ─────────────────────────────────────────────
#  Hero image metadata and generation for an issue.
#
#  generate_hero_prompt() -- pure, no side effects.
#  generate_hero_image()  -- calls OpenAI, writes PNG
#                            to docs/images/, updates DB.
#
#  Inputs:  digest dict (bilingual, from summarizer)
#  Outputs: visual metadata dict for digest JSON
# ─────────────────────────────────────────────

import os

from prompt_map import PROMPT_TEMPLATES, PROMPT_VARIANT_SUBJECTS, _BASE

TEMPLATE_VERSION = "v1"


def generate_hero_prompt(digest: dict) -> dict:
    """
    Derive hero image metadata from the lead story.

    Tag and headline come from digest["es"]["stories"][0].
    Sentiment label comes from digest["en"]["sentiment"]["label_en"]
    to keep English content in the English block.
    Falls back at each step.
    """
    digest_es = digest.get("es", {})
    digest_en = digest.get("en", digest_es)

    stories  = digest_es.get("stories", [])
    lead     = stories[0] if stories else {}

    tag      = lead.get("tag", "Macro")
    headline = lead.get("headline", "")

    # Sentiment: read label_en from EN block; fall back to ES block; then default
    sent_en  = digest_en.get("sentiment", {})
    sent_es  = digest_es.get("sentiment", {})
    mood     = sent_en.get("label_en") or sent_es.get("label_en") or "Cautious"

    template = PROMPT_TEMPLATES.get(tag, PROMPT_TEMPLATES["Macro"])
    prompt   = template.format(headline=headline, sentiment=mood)

    # Generate 3 compositional variants; opt1 matches the default prompt above.
    variant_subjects = PROMPT_VARIANT_SUBJECTS.get(tag, PROMPT_VARIANT_SUBJECTS["Macro"])
    hero_options = {}
    for i, subject in enumerate(variant_subjects[:3], start=1):
        hero_options[f"opt{i}"] = _BASE.format(
            subject=subject,
            headline=headline,
            sentiment=mood,
        )

    # Concise captions derived from variant subjects — no new LLM call.
    # Strip leading indefinite article and capitalize for mobile-friendly display.
    def _caption(subject: str) -> str:
        for prefix in ("a ", "an "):
            if subject.lower().startswith(prefix):
                subject = subject[len(prefix):]
                break
        return subject[:1].upper() + subject[1:]

    hero_option_summaries = {
        f"opt{i+1}": _caption(subject)
        for i, subject in enumerate(variant_subjects[:3])
    }

    return {
        "hero_category":         tag,
        "hero_category_source":  "lead_story",
        "hero_prompt_template":  template,
        "hero_prompt_version":   TEMPLATE_VERSION,
        "hero_prompt":           prompt,
        "hero_options":          hero_options,
        "hero_option_summaries": hero_option_summaries,
        "hero_selected":         None,
    }


# Maps Claude story tags to CATEGORY_PRESETS keys in lib/image_prompt_builder.py.
# Unknown tags fall back to "macro_inflation".
TAG_TO_PRESET: dict = {
    "Macro":    "macro_inflation",
    "FX":       "macro_inflation",
    "México":   "macro_inflation",
    "Tasas":    "macro_inflation",
    "Comercio": "trade_supply_chain",
    "Mercados": "markets_finance",
    "Energía":  "energy",
    "Política": "policy_institutional",
}


def generate_hero_image(digest: dict, issue_date: str, output_dir: str) -> dict:
    """
    Extends generate_hero_prompt() to actually produce a PNG via OpenAI.

    Saves image to output_dir/{issue_date}_hero.png.
    Sets visual["hero_image"] to the public URL on success.
    On SKIP_IMAGE=true or any generation error, returns visual without hero_image.
    """
    from lib.image_generator import generate_editorial_image
    from lib.image_prompt_builder import CATEGORY_PRESETS
    import config

    visual = generate_hero_prompt(digest)

    if config.SKIP_IMAGE:
        return visual

    tag = visual.get("hero_category", "Macro")
    preset_key = TAG_TO_PRESET.get(tag, "macro_inflation")
    preset = CATEGORY_PRESETS[preset_key]

    digest_es = digest.get("es", digest)
    stories = digest_es.get("stories", [])
    context = stories[0].get("headline", "") if stories else ""

    try:
        result = generate_editorial_image(
            issue_date=issue_date,
            story_slug="hero",
            category=preset_key,
            main_subject=preset["main_subject"],
            environment=preset["environment"],
            composition=preset["composition"],
            color_system=preset["color_system"],
            context=context,
            output_dir=output_dir,
        )
        filename = os.path.basename(result["image_path"])
        visual["hero_image"] = f"{config.ASSET_BASE_URL.rstrip('/')}/images/{filename}"
    except Exception as exc:
        print(f"  [image_gen] Hero image generation failed: {exc}")

    return visual
