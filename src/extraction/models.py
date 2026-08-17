"""The result type every layout parser returns.

One shared dataclass, not one per layout, because the schema is the same
regardless of which layout produced it. Field names match `GROUND_TRUTH.csv`
columns 1:1 (minus `file`/`layout`, which the caller already knows), which
is what keeps scoring, validation, confidence, and the review queue
layout-agnostic — none of that code needs to know or care whether a given
`ExtractionResult` came from `layout_a.py` or `layout_c.py`.

Any field a parser's regex didn't match is `None` — a signal for later
stages, never an invented value.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import date


@dataclass(frozen=True)
class ExtractionResult:
    cert_no: str | None
    unit_id: str | None
    building: str | None
    city: str | None
    state: str | None
    unit_type: str | None
    capacity_lbs: int | None
    inspection_date: date | None
    next_due: date | None
    inspector: str | None
    result: str | None
    invoice_total: float | None
    defect_count: int | None

    def as_dict(self) -> dict[str, object]:
        return {f.name: getattr(self, f.name) for f in fields(self)}


FIELD_NAMES: tuple[str, ...] = tuple(f.name for f in fields(ExtractionResult))
