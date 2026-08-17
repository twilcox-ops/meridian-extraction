"""Stage 4 — decides which documents go to the review queue.

A document is flagged for review if any of:
  - routing didn't land it on exactly one known layout with a working
    parser (Stage 2's `misrouted`) — unknown layout, ambiguous marker
    match, or a layout with no parser yet
  - any field's confidence is below threshold, which includes any field
    that's missing entirely (capacity_lbs on some Layout C documents is
    the case the whole project is built around: never fabricate it, always
    flag it)
  - the extraction fails schema validation (Stage 3) — a type/range
    problem or a cross-field contradiction

A document flagged for none of those reasons is "clean": fully extracted,
fully validated, every field at full confidence. Nothing in between exists
— there is no clean output that a human hasn't implicitly signed off on by
its extraction succeeding outright.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from extraction.confidence import DEFAULT_CONFIDENCE_THRESHOLD, field_confidences, low_confidence_fields
from extraction.models import FIELD_NAMES
from extraction.pdf_io import extract_text
from extraction.router import route
from extraction.validate import ValidationOutcome, validate_extraction

DEFAULT_SAMPLE_DATA = Path(__file__).resolve().parents[2] / "sample-data" / "inspection-certs"


@dataclass(frozen=True)
class QueueItem:
    file: str
    layout: str | None  # detected layout, or None if unknown/ambiguous
    values: dict[str, object]  # field -> extracted value, or None for every field if unrouted
    confidences: dict[str, float]
    validation: ValidationOutcome | None  # None only when there was nothing to validate
    routing_note: str
    needs_review: bool
    reasons: tuple[str, ...]


def evaluate_document(pdf_path: Path, threshold: float = DEFAULT_CONFIDENCE_THRESHOLD) -> QueueItem:
    text = extract_text(pdf_path)
    routed = route(text)

    confidences = field_confidences(routed.result)
    low_conf = low_confidence_fields(confidences, threshold)
    validation = validate_extraction(routed.result) if routed.result is not None else None

    if routed.result is not None:
        values = routed.result.as_dict()
    else:
        values = {name: None for name in FIELD_NAMES}

    reasons: list[str] = []
    if routed.misrouted:
        reasons.append(f"routing: {routed.note}")
    if low_conf:
        reasons.append(f"low-confidence/missing fields: {', '.join(low_conf)}")
    if validation is not None and not validation.valid:
        reasons.extend(f"validation: {e}" for e in validation.errors)

    return QueueItem(
        file=pdf_path.name,
        layout=routed.layout,
        values=values,
        confidences=confidences,
        validation=validation,
        routing_note=routed.note,
        needs_review=bool(reasons),
        reasons=tuple(reasons),
    )


def build_queue(
    sample_data_dir: Path, threshold: float = DEFAULT_CONFIDENCE_THRESHOLD
) -> list[QueueItem]:
    return [evaluate_document(p, threshold) for p in sorted(sample_data_dir.glob("*.pdf"))]


def main() -> None:
    sample_data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SAMPLE_DATA
    items = build_queue(sample_data_dir)

    review = [i for i in items if i.needs_review]
    clean = [i for i in items if not i.needs_review]

    print(f"{len(items)} documents evaluated: {len(clean)} clean, {len(review)} need review")
    print()
    print(f"REVIEW QUEUE ({len(review)}):")
    for item in review:
        print(f"  {item.file}  (layout={item.layout or 'unknown'})")
        for reason in item.reasons:
            print(f"    - {reason}")

    if clean:
        print()
        print(f"CLEAN ({len(clean)}): " + ", ".join(i.file for i in clean))


if __name__ == "__main__":
    main()
