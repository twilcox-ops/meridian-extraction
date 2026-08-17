from datetime import date

from extraction.models import ExtractionResult
from extraction.validate import validate_extraction

VALID_RESULT = ExtractionResult(
    cert_no="MES-2026-4100",
    unit_id="D97-6",
    building="Kestrel Plaza",
    city="Denver",
    state="CO",
    unit_type="Freight",
    capacity_lbs=4000,
    inspection_date=date(2026, 1, 13),
    next_due=date(2027, 1, 13),
    inspector="A. Vasquez",
    result="FAIL",
    invoice_total=1766.82,
    defect_count=3,
)


def test_valid_extraction_passes():
    outcome = validate_extraction(VALID_RESULT)
    assert outcome.valid
    assert outcome.certificate is not None
    assert outcome.errors == ()


def test_invalid_extraction_is_flagged_not_silently_accepted():
    import dataclasses

    bad = dataclasses.replace(VALID_RESULT, result="FAIL", defect_count=0)
    outcome = validate_extraction(bad)
    assert not outcome.valid
    assert outcome.certificate is None
    assert any("contradictory" in e for e in outcome.errors)


def test_missing_field_from_a_failed_parse_is_flagged():
    """If Stage 1's regex missed a field and left it None, validation must
    catch that -- never silently pass a document with a None where a real
    value belongs (except capacity_lbs, which may be legitimately absent)."""
    import dataclasses

    bad = dataclasses.replace(VALID_RESULT, cert_no=None)
    outcome = validate_extraction(bad)
    assert not outcome.valid
    assert any("cert_no" in e for e in outcome.errors)


def test_missing_capacity_is_not_treated_as_a_failure():
    import dataclasses

    result = dataclasses.replace(VALID_RESULT, capacity_lbs=None)
    outcome = validate_extraction(result)
    assert outcome.valid
    assert outcome.certificate.capacity_lbs is None
