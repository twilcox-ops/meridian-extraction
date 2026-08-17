from datetime import date

from extraction.layout_a import is_layout_a, parse_layout_a

SAMPLE_TEXT_WITH_DEFECTS = """
MERIDIAN ELEVATOR SERVICES

Annual Safety Inspection Certificate

Certificate No:   MES-2026-4100
Unit ID:          D97-6
Building:         Kestrel Plaza
Address:          88 Ninth Ave, Denver, CO 80202
Unit Type:        Freight
Capacity (lbs):   4000
Inspection Date:  01/13/2026
Next Due:         01/13/2027
Inspector:        A. Vasquez
Result:           FAIL
Invoice Total:    $1,766.82

Defects Noted:

    - Buffer oil level low
    - Governor tripping speed out of range
    - Door restrictor worn beyond tolerance

SYNTHETIC TRAINING DOCUMENT - fictional company, not a real record
"""

SAMPLE_TEXT_NO_DEFECTS = """
MERIDIAN ELEVATOR SERVICES

Annual Safety Inspection Certificate

Certificate No:   MES-2026-4112
Unit ID:          C83-3
Building:         Ironwood Residences
Address:          315 Ironwood Ct, Spokane, WA 99201
Unit Type:        Traction Passenger
Capacity (lbs):   3500
Inspection Date:  03/22/2026
Next Due:         03/22/2027
Inspector:        S. Ferrara
Result:           PASS
Invoice Total:    $1,439.22

SYNTHETIC TRAINING DOCUMENT - fictional company, not a real record
"""


def test_is_layout_a_detects_marker():
    assert is_layout_a(SAMPLE_TEXT_WITH_DEFECTS)
    assert not is_layout_a("some unrelated table-style document")


def test_parses_all_fields_with_defects():
    result = parse_layout_a(SAMPLE_TEXT_WITH_DEFECTS)

    assert result.cert_no == "MES-2026-4100"
    assert result.unit_id == "D97-6"
    assert result.building == "Kestrel Plaza"
    assert result.city == "Denver"
    assert result.state == "CO"
    assert result.unit_type == "Freight"
    assert result.capacity_lbs == 4000
    assert result.inspection_date == date(2026, 1, 13)
    assert result.next_due == date(2027, 1, 13)
    assert result.inspector == "A. Vasquez"
    assert result.result == "FAIL"
    assert result.invoice_total == 1766.82
    assert result.defect_count == 3


def test_zero_defects_when_section_absent():
    result = parse_layout_a(SAMPLE_TEXT_NO_DEFECTS)
    assert result.result == "PASS"
    assert result.defect_count == 0


def test_missing_field_is_none_not_fabricated():
    """A field the regex can't find must come back as None, never a guess."""
    text_missing_capacity = SAMPLE_TEXT_WITH_DEFECTS.replace(
        "Capacity (lbs):   4000\n", ""
    )
    result = parse_layout_a(text_missing_capacity)
    assert result.capacity_lbs is None
    # everything else still parses fine
    assert result.cert_no == "MES-2026-4100"


def test_parse_layout_a_on_garbage_text_returns_all_none_no_crash():
    result = parse_layout_a("this is not an inspection certificate at all")
    assert result.cert_no is None
    assert result.capacity_lbs is None
    assert result.defect_count == 0
