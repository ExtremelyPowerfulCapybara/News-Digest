# bot/prompt_map.py
# ─────────────────────────────────────────────
#  Prompt templates for hero image generation.
#  Each template corresponds to one of the 8
#  Claude story tags. Fill {headline} and
#  {sentiment} at generation time via .format().
# ─────────────────────────────────────────────

_BASE = (
    "Premium editorial illustration for a high-end financial and geopolitical newsletter, "
    "hand-drawn ink and graphite style with refined linework and subtle cross-hatching, "
    "monochrome base with controlled muted color accents (20–25%), "
    "slightly textured paper background, "
    "{subject}, "
    "inspired by: {headline}, overall tone: {sentiment}, "
    "minimal composition, strong negative space, realistic proportions, "
    "calm but tense atmosphere, modern whitepaper-inspired editorial aesthetic, "
    "not photorealistic, not cinematic, no text, no logos."
)

PROMPT_TEMPLATES = {
    "Macro": _BASE.format(
        subject="a sparse government chamber or empty boardroom, muted light through tall windows",
        headline="{headline}",
        sentiment="{sentiment}",
    ),
    "FX": _BASE.format(
        subject="rows of currency exchange ticker boards, numbers blurred, deep architectural perspective",
        headline="{headline}",
        sentiment="{sentiment}",
    ),
    "México": _BASE.format(
        subject="Mexico City skyline at dusk, Torre Mayor silhouette, low clouds, empty boulevard below",
        headline="{headline}",
        sentiment="{sentiment}",
    ),
    "Comercio": _BASE.format(
        subject="stacked shipping containers at a port, cranes overhead, calm water, no figures",
        headline="{headline}",
        sentiment="{sentiment}",
    ),
    "Tasas": _BASE.format(
        subject="central bank building exterior, stone columns, overcast sky, empty stone steps",
        headline="{headline}",
        sentiment="{sentiment}",
    ),
    "Mercados": _BASE.format(
        subject="stock exchange trading floor, screens with data, long perspective shot, no people",
        headline="{headline}",
        sentiment="{sentiment}",
    ),
    "Energía": _BASE.format(
        subject="oil refinery towers and storage tanks at dusk, slow smoke rising, flat horizon",
        headline="{headline}",
        sentiment="{sentiment}",
    ),
    "Política": _BASE.format(
        subject="government building facade, national flags, dramatic clouds, empty plaza below",
        headline="{headline}",
        sentiment="{sentiment}",
    ),
}
