"""Stage 4 — confidence scoring.

Deterministic regex extraction only ever has two states for a field: the
pattern matched a value, or it didn't. There's no gradient of "pretty
sure" to hedge with, so confidence here is honestly binary — 1.0 for a
field that was extracted, 0.0 for one that's missing. Pretending otherwise
would just be dressing up a boolean as a float. Stage 5's LLM fallback is
where a real probabilistic confidence shows up; until then this is the
truthful version.

The threshold exists so "below threshold" is a real, adjustable concept
rather than a synonym for "is None" — Stage 5 can lower it once fields
carry fractional confidence, without changing how the review queue
consumes it.
"""

from __future__ import annotations

from extraction.layout_a import LayoutAResult
from extraction.schema import InspectionCertificate

DEFAULT_CONFIDENCE_THRESHOLD = 1.0

FIELD_NAMES: tuple[str, ...] = tuple(InspectionCertificate.model_fields)


def field_confidences(result: LayoutAResult | None) -> dict[str, float]:
    """One confidence score per schema field.

    `result=None` means there's no parser for this document's layout yet
    (Stage 2) — every field is missing, so every field scores 0.0, the
    same as any other field a working parser failed to find.
    """
    if result is None:
        return {name: 0.0 for name in FIELD_NAMES}

    values = result.as_dict()
    return {name: (1.0 if values.get(name) is not None else 0.0) for name in FIELD_NAMES}


def low_confidence_fields(
    confidences: dict[str, float], threshold: float = DEFAULT_CONFIDENCE_THRESHOLD
) -> list[str]:
    return [field for field, score in confidences.items() if score < threshold]
