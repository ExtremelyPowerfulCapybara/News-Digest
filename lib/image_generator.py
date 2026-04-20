# lib/image_generator.py
# ─────────────────────────────────────────────
#  Editorial image generation with deduplication.
#
#  Flow per attempt:
#    1. Build prompt (with current novelty + variation)
#    2. Generate via OpenAI (Responses API -> Images API fallback)
#    3. Compute accepted_prompt = revised_prompt or prompt_sent
#    4. Two-phase similarity check (category, then global)
#    5. Save attempt record (accepted or rejected)
#    6. If image_flagged: escalate novelty, increment regeneration_count, retry
#    7. On acceptance: save/update image_history record; link attempt to it
# ─────────────────────────────────────────────

import base64
import os
from collections import Counter
from typing import Any, Dict, Optional

from lib.image_prompt_builder import (
    PROMPT_MASTER_VERSION,
    build_image_prompt,
    infer_concept_tag,
    suggest_novelty_request,
)
from lib.image_history_store import (
    get_recent_by_category,
    get_recent_global,
    init_db,
    save_attempt_record,
    save_record,
    update_attempt_parent,
    update_record,
)
from lib.image_similarity import check_against_history
from lib.image_registry import select_prompt_components

DEFAULT_MAX_RETRIES: int = 3
DEFAULT_TEXT_THRESHOLD: float = 0.82
DEFAULT_PHASH_THRESHOLD: int = 8
_DEFAULT_OUTPUT_DIR: str = "generated_images"


def _openai_responses_api(prompt: str, output_path: str) -> Dict[str, Any]:
    """Generate image via OpenAI Responses API. Captures revised_prompt."""
    import openai
    client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    response = client.responses.create(
        model=os.environ.get("OPENAI_RESPONSES_MODEL", "gpt-4o"),
        input=[{"role": "user", "content": [{"type": "text", "text": prompt}]}],
        tools=[{
            "type": "image_generation",
            "size": os.environ.get("OPENAI_IMAGE_SIZE", "1024x1024"),
            "quality": os.environ.get("OPENAI_IMAGE_QUALITY", "medium"),
        }],
    )
    image_data = revised_prompt = None
    for item in response.output:
        if getattr(item, "type", None) == "image_generation_call":
            image_data = item.result
            revised_prompt = getattr(item, "revised_prompt", None)
            break
    if not image_data:
        raise RuntimeError("Responses API returned no image data.")
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(base64.b64decode(image_data))
    return {"image_path": output_path, "revised_prompt": revised_prompt}


def _openai_images_api(prompt: str, output_path: str) -> Dict[str, Any]:
    """Generate image via OpenAI Images API. revised_prompt available for dall-e-3."""
    import openai
    client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    response = client.images.generate(
        model=os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1"),
        prompt=prompt,
        size=os.environ.get("OPENAI_IMAGE_SIZE", "1024x1024"),
        quality=os.environ.get("OPENAI_IMAGE_QUALITY", "medium"),
        n=1,
        response_format="b64_json",
    )
    b64 = response.data[0].b64_json
    if not b64:
        raise RuntimeError("Images API returned empty image data.")
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(base64.b64decode(b64))
    return {
        "image_path": output_path,
        "revised_prompt": getattr(response.data[0], "revised_prompt", None),
    }


def _generate_image(prompt: str, output_path: str) -> Dict[str, Any]:
    """Try Responses API; fall back to Images API. Controlled by OPENAI_USE_RESPONSES_API."""
    if os.environ.get("OPENAI_USE_RESPONSES_API", "true").lower() == "true":
        try:
            return _openai_responses_api(prompt, output_path)
        except Exception as exc:
            print(f"  [image_generator] Responses API failed ({exc}); falling back.")
    return _openai_images_api(prompt, output_path)


def generate_editorial_image(
    issue_date: str,
    story_slug: str,
    category: str,
    main_subject: str,
    environment: str,
    composition: str,
    color_system: str,
    context: Optional[str] = None,
    novelty_request: Optional[str] = None,
    variation_code: Optional[str] = None,
    concept_tag: Optional[str] = None,
    subject_family: Optional[str] = None,
    composition_preset: Optional[str] = None,
    force_novelty_level: Optional[int] = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
    text_threshold: float = DEFAULT_TEXT_THRESHOLD,
    phash_threshold: int = DEFAULT_PHASH_THRESHOLD,
    db_path: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Full editorial image generation pipeline with automatic deduplication.

    accepted_prompt = revised_prompt if available, else prompt_sent.
    concept_tag: passed explicitly or inferred from category + main_subject.
    subject_family: override registry-selected subject family.
    composition_preset: override registry-selected composition preset.
    force_novelty_level: if set, applies that escalation level from attempt 0.

    Retries up to max_retries when image phash is too close to recent images.
    Text similarity above threshold marks text_risky but does NOT trigger retry.

    Returns: image_path, prompt_sent, revised_prompt, accepted_prompt, concept_tag,
             subject_family, composition_preset, variation_code, novelty_request,
             similarity (dict), regeneration_count, record_id
    """
    init_db(db_path)
    out_dir = output_dir or _DEFAULT_OUTPUT_DIR
    os.makedirs(out_dir, exist_ok=True)

    # Load recent history for deduplication and scoring
    recent_category = get_recent_by_category(category, limit=15, db_path=db_path)
    recent_global = get_recent_global(limit=50, db_path=db_path)

    # Compute frequency dicts for novelty directives
    concept_tag_freq = dict(
        Counter(r.get("concept_tag") for r in recent_category if r.get("concept_tag"))
    )
    subject_family_freq = dict(
        Counter(r.get("subject_family") for r in recent_category if r.get("subject_family"))
    )
    composition_freq = dict(
        Counter(r.get("composition_preset") for r in recent_category if r.get("composition_preset"))
    )

    current_novelty = novelty_request
    regeneration_count = 0
    record_id: Optional[int] = None
    excluded_combos = []

    for attempt in range(max_retries + 1):
        # Registry-aware component selection (rotates combo, avoids excluded triples)
        components = select_prompt_components(
            category=category,
            recent_history=recent_category,
            concept_tag=concept_tag,
            subject_family=subject_family,
            composition_preset=composition_preset,
            excluded_combos=excluded_combos,
            force_novelty_level=force_novelty_level if attempt == 0 else None,
        )

        resolved_main_subject = components.get("main_subject") or main_subject
        resolved_composition = components.get("composition") or composition
        resolved_color_system = components.get("color_system") or color_system
        resolved_concept_tag = (
            components.get("concept_tag")
            or concept_tag
            or infer_concept_tag(category, main_subject)
        )
        resolved_subject_family = components.get("subject_family")
        resolved_composition_preset = components.get("composition_preset")
        auto_novelty = components.get("novelty_request")

        used_combo = (
            resolved_concept_tag,
            resolved_subject_family or "",
            resolved_composition_preset or "",
        )

        # Determine effective novelty for this attempt
        if attempt == 0:
            if current_novelty is None:
                if force_novelty_level is not None:
                    current_novelty = suggest_novelty_request(
                        category, recent_category,
                        escalation_level=force_novelty_level,
                        concept_tag_freq=concept_tag_freq,
                        subject_family_freq=subject_family_freq,
                        composition_freq=composition_freq,
                    )
                else:
                    current_novelty = auto_novelty
        # else: current_novelty already set by escalation at end of previous iteration

        prompt = build_image_prompt(
            category=category,
            main_subject=resolved_main_subject,
            environment=environment,
            composition=resolved_composition,
            color_system=resolved_color_system,
            context=context,
            novelty_request=current_novelty,
            variation_code=variation_code,
        )

        slug_safe = story_slug.replace("/", "_").replace(" ", "_")[:60]
        attempt_suffix = f"_r{attempt}" if attempt > 0 else ""
        output_path = os.path.join(out_dir, f"{issue_date}_{slug_safe}{attempt_suffix}.png")

        print(
            f"  [image_generator] Attempt {attempt + 1}/{max_retries + 1}: "
            f"{os.path.basename(output_path)} "
            f"[{resolved_subject_family}/{resolved_composition_preset}]"
        )

        try:
            gen = _generate_image(prompt, output_path)
        except Exception as exc:
            print(f"  [image_generator] Generation error: {exc}")
            save_attempt_record({
                "prompt_sent": prompt,
                "accepted": False,
                "rejection_reason": "generation_error",
            }, db_path=db_path)
            if attempt == max_retries:
                raise
            excluded_combos.append(used_combo)
            escalation = min(attempt + 1, 3)
            current_novelty = suggest_novelty_request(
                category, recent_category, escalation,
                concept_tag_freq=concept_tag_freq,
                subject_family_freq=subject_family_freq,
                composition_freq=composition_freq,
            )
            regeneration_count += 1
            continue

        image_path = gen["image_path"]
        revised_prompt = gen.get("revised_prompt")
        accepted_prompt = revised_prompt or prompt

        sim = check_against_history(
            prompt=accepted_prompt,
            image_path=image_path,
            category_records=recent_category,
            global_records=recent_global,
            text_threshold=text_threshold,
            phash_threshold=phash_threshold,
        )

        is_accepted = not sim["flagged"] or attempt == max_retries

        # Save attempt record
        attempt_id = save_attempt_record({
            "prompt_sent": prompt,
            "revised_prompt": revised_prompt,
            "accepted": is_accepted,
            "rejection_reason": sim.get("rejection_reason") if not is_accepted else None,
            "image_phash": sim.get("new_phash"),
            "similarity_score_text": sim["text_similarity"],
            "similarity_score_image": sim["image_similarity"],
        }, db_path=db_path)

        if is_accepted:
            if sim["flagged"]:
                print("  [image_generator] Warning: max retries reached. Accepting despite similarity.")
            else:
                print(
                    f"  [image_generator] Accepted on attempt {attempt + 1}. "
                    f"phash_dist={sim['min_phash_distance']}, "
                    f"text_risky={sim['text_risky']}"
                )

            shared_record = {
                "issue_date": issue_date,
                "story_slug": story_slug,
                "category": category,
                "prompt_master_version": PROMPT_MASTER_VERSION,
                "prompt_sent": prompt,
                "revised_prompt": revised_prompt,
                "accepted_prompt": accepted_prompt,
                "concept_tag": resolved_concept_tag,
                "subject_family": resolved_subject_family,
                "composition_preset": resolved_composition_preset,
                "variation_code": variation_code,
                "novelty_request": current_novelty,
                "image_path": image_path,
                "image_phash": sim.get("new_phash"),
                "similarity_score_text": sim["text_similarity"],
                "similarity_score_image": sim["image_similarity"],
                "regeneration_count": regeneration_count,
            }

            if record_id is None:
                record_id = save_record(shared_record, db_path=db_path)
            else:
                update_record(record_id, {
                    "image_path": image_path,
                    "image_phash": sim.get("new_phash"),
                    "accepted_prompt": accepted_prompt,
                    "revised_prompt": revised_prompt,
                    "subject_family": resolved_subject_family,
                    "composition_preset": resolved_composition_preset,
                    "similarity_score_text": sim["text_similarity"],
                    "similarity_score_image": sim["image_similarity"],
                    "regeneration_count": regeneration_count,
                }, db_path=db_path)

            update_attempt_parent(attempt_id, record_id, db_path=db_path)

            return {
                "image_path": image_path,
                "prompt_sent": prompt,
                "revised_prompt": revised_prompt,
                "accepted_prompt": accepted_prompt,
                "concept_tag": resolved_concept_tag,
                "subject_family": resolved_subject_family,
                "composition_preset": resolved_composition_preset,
                "variation_code": variation_code,
                "novelty_request": current_novelty,
                "similarity": sim,
                "regeneration_count": regeneration_count,
                "record_id": record_id,
            }

        # Image too similar — save initial record for tracking, then escalate
        if record_id is None:
            record_id = save_record({
                "issue_date": issue_date,
                "story_slug": story_slug,
                "category": category,
                "prompt_master_version": PROMPT_MASTER_VERSION,
                "prompt_sent": prompt,
                "revised_prompt": revised_prompt,
                "accepted_prompt": accepted_prompt,
                "concept_tag": resolved_concept_tag,
                "subject_family": resolved_subject_family,
                "composition_preset": resolved_composition_preset,
                "variation_code": variation_code,
                "novelty_request": current_novelty,
                "image_path": image_path,
                "image_phash": sim.get("new_phash"),
                "similarity_score_text": sim["text_similarity"],
                "similarity_score_image": sim["image_similarity"],
                "regeneration_count": regeneration_count,
            }, db_path=db_path)
            update_attempt_parent(attempt_id, record_id, db_path=db_path)

        excluded_combos.append(used_combo)
        escalation = min(attempt + 2, 3)
        current_novelty = suggest_novelty_request(
            category, recent_category, escalation,
            concept_tag_freq=concept_tag_freq,
            subject_family_freq=subject_family_freq,
            composition_freq=composition_freq,
        )
        regeneration_count += 1
        print(
            f"  [image_generator] Rejected ({sim['rejection_reason']}). "
            f"Escalating to level {escalation}. excluded_combos={len(excluded_combos)}"
        )

    raise RuntimeError("[image_generator] Generation loop exited unexpectedly.")
