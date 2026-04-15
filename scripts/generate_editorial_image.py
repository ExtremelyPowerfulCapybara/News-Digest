# scripts/generate_editorial_image.py
# ─────────────────────────────────────────────
#  CLI for the editorial image generation + deduplication subsystem.
#
#  Usage (from repo root):
#    python scripts/generate_editorial_image.py \
#      --issue-date 2026-04-15 \
#      --story-slug mexico-energy-reform \
#      --category energy \
#      --main-subject "oil refinery towers at dusk" \
#      --environment "flat industrial horizon, overcast sky" \
#      --composition "wide establishing shot, subject dominant left" \
#      --color-system "warm amber-rust tones on metal"
#
#  Optional flags:
#    --context             Editorial context (headline, event)
#    --novelty-request     Manual novelty directive
#    --variation-code      e.g. B-2-ii-gamma
#    --concept-tag         Override inferred concept tag
#    --force-novelty-level {0,1,2,3}  Apply escalation from first attempt
#    --max-retries         Default 3
#    --text-threshold      Default 0.82
#    --phash-threshold     Default 8
#    --output-dir          Directory for generated PNGs
#    --db-path             SQLite DB path
#    --dry-run             Print full prompt breakdown; skip generation
#    --show-similarity-debug  Print per-phase similarity scores after generation
#    --list-presets        Print category presets and exit
# ─────────────────────────────────────────────

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def cmd_list_presets() -> None:
    from lib.image_prompt_builder import CATEGORY_PRESETS
    print("\n-- Category presets --------------------------------------------------\n")
    for cat, preset in CATEGORY_PRESETS.items():
        print(f"[{cat}]")
        for k, v in preset.items():
            print(f"  --{k.replace('_', '-')}: {v}")
        print()


def cmd_dry_run(args) -> None:
    from lib.image_prompt_builder import (
        build_image_prompt,
        infer_concept_tag,
        resolve_variation_code,
        suggest_novelty_request,
    )
    from lib.image_history_store import get_recent_by_category

    resolved_concept_tag = args.concept_tag or infer_concept_tag(args.category, args.main_subject)
    variation_text = resolve_variation_code(args.variation_code)

    # Load comparison candidate count (if DB exists)
    candidate_count = 0
    try:
        db_path = args.db_path or None
        records = get_recent_by_category(args.category, limit=15, db_path=db_path)
        candidate_count = len(records)
    except Exception:
        pass

    # Resolve novelty: use manual if provided, else suggest at force_novelty_level
    novelty = args.novelty_request
    if novelty is None and args.force_novelty_level is not None:
        novelty = suggest_novelty_request(
            args.category, [], escalation_level=args.force_novelty_level
        )

    prompt = build_image_prompt(
        category=args.category,
        main_subject=args.main_subject,
        environment=args.environment,
        composition=args.composition,
        color_system=args.color_system,
        context=args.context,
        novelty_request=novelty,
        variation_code=args.variation_code,
    )

    print("\n-- Dry-run breakdown --------------------------------------------------\n")
    print(f"Category:            {args.category}")
    print(f"Concept tag:         {resolved_concept_tag}")
    if variation_text:
        print(f"Variation resolved:  {variation_text}")
    if novelty:
        print(f"Novelty directive:   {novelty}")
    print(f"Comparison candidates (category): {candidate_count}")
    print(f"Text threshold:      {args.text_threshold}")
    print(f"Phash threshold:     {args.phash_threshold}")
    print(f"\nFull prompt ({len(prompt)} chars):\n")
    print(prompt)


def cmd_generate(args) -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    from lib.image_generator import generate_editorial_image

    result = generate_editorial_image(
        issue_date=args.issue_date,
        story_slug=args.story_slug,
        category=args.category,
        main_subject=args.main_subject,
        environment=args.environment,
        composition=args.composition,
        color_system=args.color_system,
        context=args.context,
        novelty_request=args.novelty_request,
        variation_code=args.variation_code,
        concept_tag=args.concept_tag,
        force_novelty_level=args.force_novelty_level,
        max_retries=args.max_retries,
        text_threshold=args.text_threshold,
        phash_threshold=args.phash_threshold,
        output_dir=args.output_dir,
        db_path=args.db_path,
    )

    printable = {k: v for k, v in result.items() if k != "similarity"}
    print("\n-- Result ----------------------------------------------------------")
    print(json.dumps(printable, indent=2, ensure_ascii=False))

    if args.show_similarity_debug:
        sim = result["similarity"]
        print("\n-- Similarity debug ---------------------------------------------------")
        print(f"  text_similarity:              {sim['text_similarity']:.4f}")
        print(f"  text_risky:                   {sim['text_risky']}")
        print(f"  category_min_phash_distance:  {sim['category_min_phash_distance']}")
        print(f"  global_min_phash_distance:    {sim['global_min_phash_distance']}")
        print(f"  min_phash_distance:           {sim['min_phash_distance']}")
        print(f"  image_flagged:                {sim['image_flagged']}")
        print(f"  rejection_reason:             {sim.get('rejection_reason')}")
    else:
        sim = result["similarity"]
        print(
            f"\nSimilarity: text={sim['text_similarity']:.3f} "
            f"(risky={sim['text_risky']}), "
            f"phash_dist={sim['min_phash_distance']}, "
            f"image_flagged={sim['image_flagged']}"
        )

    print(f"Concept tag:          {result['concept_tag']}")
    print(f"Regenerations used:   {result['regeneration_count']}")
    print(f"Saved to:             {result['image_path']}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a deduplicated editorial image for a newsletter issue.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--list-presets", action="store_true",
                        help="Print category preset suggestions and exit.")

    # Required for generation
    parser.add_argument("--issue-date",   help="Issue date YYYY-MM-DD")
    parser.add_argument("--story-slug",   help="Short slug identifying the story")
    parser.add_argument("--category",     help="Category (energy, macro_inflation, etc.)")
    parser.add_argument("--main-subject", help="Main subject description")
    parser.add_argument("--environment",  help="Environment/setting description")
    parser.add_argument("--composition",  help="Composition instruction")
    parser.add_argument("--color-system", help="Color accent system description")

    # Optional generation parameters
    parser.add_argument("--context",               default=None)
    parser.add_argument("--novelty-request",       default=None)
    parser.add_argument("--variation-code",        default=None)
    parser.add_argument("--concept-tag",           default=None,
                        help="Override inferred concept tag")
    parser.add_argument("--force-novelty-level",   type=int, default=None,
                        choices=[0, 1, 2, 3],
                        help="Apply this escalation level from attempt 0")
    parser.add_argument("--max-retries",           type=int, default=3)
    parser.add_argument("--text-threshold",        type=float, default=0.82,
                        help="Text similarity threshold (default 0.82)")
    parser.add_argument("--phash-threshold",       type=int, default=8,
                        help="Phash distance threshold (default 8)")
    parser.add_argument("--output-dir",            default=None)
    parser.add_argument("--db-path",               default=None)
    parser.add_argument("--dry-run",               action="store_true",
                        help="Print full prompt breakdown; skip API call")
    parser.add_argument("--show-similarity-debug", action="store_true",
                        help="Print per-phase similarity scores after generation")

    args = parser.parse_args()

    if args.list_presets:
        cmd_list_presets()
        return

    # Fill defaults for dry-run if some required fields are missing
    if args.dry_run:
        args.category     = args.category     or "[CATEGORY]"
        args.main_subject = args.main_subject or "[MAIN SUBJECT]"
        args.environment  = args.environment  or "[ENVIRONMENT]"
        args.composition  = args.composition  or "[COMPOSITION]"
        args.color_system = args.color_system or "[COLOR SYSTEM]"
        cmd_dry_run(args)
        return

    required = ["issue_date", "story_slug", "category", "main_subject",
                "environment", "composition", "color_system"]
    missing = [f"--{r.replace('_', '-')}" for r in required if not getattr(args, r, None)]
    if missing:
        parser.error(f"Required: {', '.join(missing)}")

    cmd_generate(args)


if __name__ == "__main__":
    main()
