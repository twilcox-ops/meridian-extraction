"""Stage 3 — runs an extracted document through `InspectionCertificate` and
turns a Pydantic `ValidationError`, if any, into a reported outcome instead
of a crashed program.
"""

from __future__ import annotations

from dataclasses import dataclass, fields as dataclass_fields

from pydantic import ValidationError

from extraction.models import ExtractionResult
from extraction.schema import InspectionCertificate


@dataclass(frozen=True)
class ValidationOutcome:
    valid: bool
    certificate: InspectionCertificate | None
    errors: tuple[str, ...]


def validate_extraction(result: ExtractionResult) -> ValidationOutcome:
    """Validate one parser result against the schema.

    Field-level problems (wrong type, out of range, missing required
    value) and the cross-field rules both surface the same way: `valid`
    is False and `errors` explains exactly what failed. Nothing here
    invents a value to make validation pass.
    """
    data = {f.name: getattr(result, f.name) for f in dataclass_fields(result)}
    try:
        certificate = InspectionCertificate.model_validate(data)
    except ValidationError as exc:
        errors = tuple(
            f"{'.'.join(str(p) for p in e['loc']) or '<model>'}: {e['msg']}"
            for e in exc.errors()
        )
        return ValidationOutcome(valid=False, certificate=None, errors=errors)
    return ValidationOutcome(valid=True, certificate=certificate, errors=())
