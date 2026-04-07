# bot/image_gen.py
# ─────────────────────────────────────────────
#  Generates a hero image prompt for an issue.
#  Pure function — no API calls, no side effects.
#
#  Inputs:  digest dict (bilingual, from summarizer)
#  Outputs: visual metadata dict for digest JSON
# ─────────────────────────────────────────────

from prompt_map import PROMPT_TEMPLATES

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

    return {
        "hero_category":        tag,
        "hero_category_source": "lead_story",
        "hero_prompt_template": template,
        "hero_prompt_version":  TEMPLATE_VERSION,
        "hero_prompt":          prompt,
        "hero_selected":        None,
    }
