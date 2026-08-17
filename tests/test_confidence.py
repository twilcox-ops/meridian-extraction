import dataclasses
from datetime import date

from extraction.confidence import FIELD_NAMES, field_confidences, low_confidence_fields
from extraction.models import ExtractionResult

FULL_RESULT = ExtractionResult(
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


def test_fully_extracted_result_is_all_full_confidence():
    confidences = field_confidences(FULL_RESULT)
    assert set(confidences) == set(FIELD_NAMES)
    assert all(score == 1.0 for score in confidences.values())


def test_no_parser_result_is_all_zero_confidence():
    confidences = field_confidences(None)
    assert all(score == 0.0 for score in confidences.values())


def test_one_missing_field_scores_zero_others_stay_full():
    partial = dataclasses.replace(FULL_RESULT, capacity_lbs=None)
    confidences = field_confidences(partial)
    assert confidences["capacity_lbs"] == 0.0
    assert confidences["cert_no"] == 1.0


def test_low_confidence_fields_respects_threshold():
    partial = dataclasses.replace(FULL_RESULT, capacity_lbs=None)
    confidences = field_confidences(partial)
    assert low_confidence_fields(confidences) == ["capacity_lbs"]
    # a threshold of 0 means nothing is "below" it, even a missing field
    assert low_confidence_fields(confidences, threshold=0.0) == []
