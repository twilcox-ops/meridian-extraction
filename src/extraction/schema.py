"""Stage 3 — schema validation.

`InspectionCertificate` is the Pydantic model every extracted document must
satisfy before it's trusted. It checks three things:

1. Types — every field is the type it claims to be (a date is a real date,
   not a string that looks like one; `result` is one of the known enum
   values, not any string that happened to get OCR'd out).
2. Ranges — `invoice_total` and `capacity_lbs` must be positive,
   `defect_count` can't be negative.
3. Cross-field rules — `next_due` must be later than `inspection_date`, and
   a `FAIL` result with zero defects listed is contradictory.

This module does not decide what happens to a document that fails
validation (that's Stage 4's review queue) — it only decides, precisely,
what "valid" means.
"""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class InspectionResult(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    PASS_WITH_DEFECTS = "PASS WITH DEFECTS"


class InspectionCertificate(BaseModel):
    """Validated shape of one inspection certificate, layout-agnostic.

    `capacity_lbs` is the one field allowed to be legitimately absent — a
    few Layout C documents omit it entirely, and the correct handling is an
    explicit `None` that later gets flagged for review (Stage 4), not a
    fabricated number. Every other field is required: a missing
    `cert_no`/`result`/`inspection_date`/etc. means the extraction failed
    and should be caught here, not passed downstream as good data.
    """

    model_config = ConfigDict(extra="forbid")

    cert_no: str = Field(min_length=1)
    unit_id: str = Field(min_length=1)
    building: str = Field(min_length=1)
    city: str = Field(min_length=1)
    state: str = Field(min_length=2, max_length=2)
    unit_type: str = Field(min_length=1)
    capacity_lbs: int | None = Field(default=None, gt=0)
    inspection_date: date
    next_due: date
    inspector: str = Field(min_length=1)
    result: InspectionResult
    invoice_total: float = Field(gt=0)
    defect_count: int = Field(ge=0)

    @model_validator(mode="after")
    def _cross_field_rules(self) -> "InspectionCertificate":
        errors: list[str] = []

        if self.next_due <= self.inspection_date:
            errors.append(
                f"next_due ({self.next_due}) must be later than "
                f"inspection_date ({self.inspection_date})"
            )

        if self.result == InspectionResult.FAIL and self.defect_count == 0:
            errors.append(
                "result is FAIL but defect_count is 0 -- contradictory, "
                "a failed inspection must list at least one defect"
            )

        if errors:
            # Collected into one error so a caller sees every cross-field
            # problem on a document at once, not just the first one raised.
            raise ValueError("; ".join(errors))

        return self
