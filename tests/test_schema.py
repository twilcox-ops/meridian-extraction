from datetime import date

import pytest
from pydantic import ValidationError

from extraction.schema import InspectionCertificate, InspectionResult

VALID = dict(
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


def test_valid_document_constructs_cleanly():
    cert = InspectionCertificate.model_validate(VALID)
    assert cert.result == InspectionResult.FAIL
    assert cert.capacity_lbs == 4000


def test_capacity_lbs_may_be_legitimately_missing():
    """A few Layout C documents omit capacity entirely; that must validate
    as an explicit None, not fail the whole document."""
    data = {**VALID, "capacity_lbs": None}
    cert = InspectionCertificate.model_validate(data)
    assert cert.capacity_lbs is None


def test_capacity_lbs_must_be_positive_when_present():
    data = {**VALID, "capacity_lbs": 0}
    with pytest.raises(ValidationError):
        InspectionCertificate.model_validate(data)


def test_next_due_must_be_later_than_inspection_date():
    data = {**VALID, "next_due": date(2026, 1, 13)}  # same day, not later
    with pytest.raises(ValidationError, match="next_due"):
        InspectionCertificate.model_validate(data)


def test_next_due_before_inspection_date_is_rejected():
    data = {**VALID, "next_due": date(2025, 1, 13)}
    with pytest.raises(ValidationError, match="next_due"):
        InspectionCertificate.model_validate(data)


def test_invoice_total_must_be_positive():
    data = {**VALID, "invoice_total": 0}
    with pytest.raises(ValidationError):
        InspectionCertificate.model_validate(data)


def test_invoice_total_negative_is_rejected():
    data = {**VALID, "invoice_total": -100.0}
    with pytest.raises(ValidationError):
        InspectionCertificate.model_validate(data)


def test_defect_count_cannot_be_negative():
    data = {**VALID, "defect_count": -1}
    with pytest.raises(ValidationError):
        InspectionCertificate.model_validate(data)


def test_result_must_be_a_known_enum_value():
    data = {**VALID, "result": "SORT OF PASSED"}
    with pytest.raises(ValidationError):
        InspectionCertificate.model_validate(data)


def test_fail_with_zero_defects_is_contradictory():
    data = {**VALID, "result": "FAIL", "defect_count": 0}
    with pytest.raises(ValidationError, match="contradictory"):
        InspectionCertificate.model_validate(data)


def test_pass_with_zero_defects_is_fine():
    data = {**VALID, "result": "PASS", "defect_count": 0}
    cert = InspectionCertificate.model_validate(data)
    assert cert.defect_count == 0


def test_pass_with_defects_enum_value_accepts_spaces():
    data = {**VALID, "result": "PASS WITH DEFECTS", "defect_count": 1}
    cert = InspectionCertificate.model_validate(data)
    assert cert.result == InspectionResult.PASS_WITH_DEFECTS


def test_missing_required_field_is_rejected_not_defaulted():
    data = {**VALID}
    del data["cert_no"]
    with pytest.raises(ValidationError):
        InspectionCertificate.model_validate(data)


def test_multiple_cross_field_violations_are_all_reported():
    """Both cross-field rules broken at once should both show up, not just
    whichever one happened to raise first."""
    data = {**VALID, "next_due": date(2025, 1, 13), "result": "FAIL", "defect_count": 0}
    with pytest.raises(ValidationError) as exc_info:
        InspectionCertificate.model_validate(data)
    message = str(exc_info.value)
    assert "next_due" in message
    assert "contradictory" in message
