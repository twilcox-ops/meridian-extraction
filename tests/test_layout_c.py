from datetime import date

from extraction.layout_c import is_layout_c, parse_layout_c

# Wrap point A: "...acting as an\nauthorized inspector..." (breaks after "an")
SAMPLE_TEXT_WITH_DEFECTS = """
MERIDIAN ELEVATOR SERVICES
The conveyance identified below was examined on 04/02/2026 by D. Whitfield, acting as an
authorized inspector for Meridian Elevator Services. This document is issued under certificate
reference MES-2026-4102 and supersedes any prior record for this unit.
Premises: Harborview Tower Equipment No.: E11-2
Street: 1100 Beacon St Classification: Freight
Municipality: Portland, OR Rated Load: pounds
Postal: 97205 Outcome: FAIL
Charges for this examination total $1,001.53, payable net 30. Re-examination shall occur no
later than 04/02/2027.
Items requiring corrective action:
(cid:127) Firefighter recall Phase II delayed
(cid:127) Governor tripping speed out of range
(cid:127) Buffer oil level low
SYNTHETIC TRAINING DOCUMENT - fictional company, not a real record
"""

# Wrap point B: "...acting as an authorized\ninspector..." (breaks after
# "authorized" instead) -- the real bug this project hit: two documents in
# the sample corpus wrap here, not after "an", and a regex assuming a fixed
# wrap point silently returned None for cert_no/inspection_date/inspector.
SAMPLE_TEXT_ALTERNATE_WRAP = """
MERIDIAN ELEVATOR SERVICES
The conveyance identified below was examined on 05/10/2026 by J. Bhatt, acting as an authorized
inspector for Meridian Elevator Services. This document is issued under certificate reference
MES-2026-4114 and supersedes any prior record for this unit.
Premises: Harborview Tower Equipment No.: B91-2
Street: 1100 Beacon St Classification: Freight
Municipality: Portland, OR Rated Load: 3500 pounds
Postal: 97205 Outcome: PASS
Charges for this examination total $398.08, payable net 30. Re-examination shall occur no later
than 05/10/2027.
SYNTHETIC TRAINING DOCUMENT - fictional company, not a real record
"""

SAMPLE_TEXT_MISSING_CAPACITY = """
MERIDIAN ELEVATOR SERVICES
The conveyance identified below was examined on 07/22/2026 by S. Ferrara, acting as an
authorized inspector for Meridian Elevator Services. This document is issued under certificate
reference MES-2026-4105 and supersedes any prior record for this unit.
Premises: Larkspur Union Equipment No.: E37-4
Street: 1220 Larkspur Ave Classification: Traction Passenger
Municipality: Missoula, MT Rated Load: pounds
Postal: 59801 Outcome: PASS
Charges for this examination total $395.86, payable net 30. Re-examination shall occur no later
than 07/22/2027.
SYNTHETIC TRAINING DOCUMENT - fictional company, not a real record
"""


def test_is_layout_c_detects_marker():
    assert is_layout_c(SAMPLE_TEXT_WITH_DEFECTS)
    assert not is_layout_c("some unrelated single-column document")


def test_parses_all_fields_with_defects():
    result = parse_layout_c(SAMPLE_TEXT_WITH_DEFECTS)

    assert result.cert_no == "MES-2026-4102"
    assert result.unit_id == "E11-2"
    assert result.building == "Harborview Tower"
    assert result.city == "Portland"
    assert result.state == "OR"
    assert result.unit_type == "Freight"
    assert result.capacity_lbs is None  # this document omits capacity
    assert result.inspection_date == date(2026, 4, 2)
    assert result.next_due == date(2027, 4, 2)
    assert result.inspector == "D. Whitfield"
    assert result.result == "FAIL"
    assert result.invoice_total == 1001.53
    assert result.defect_count == 3


def test_parses_correctly_regardless_of_which_word_the_preamble_wraps_after():
    """The two wrap-point variants must produce identical field values --
    the wrap point is a PDF rendering accident, not a data difference."""
    result = parse_layout_c(SAMPLE_TEXT_ALTERNATE_WRAP)

    assert result.cert_no == "MES-2026-4114"
    assert result.inspection_date == date(2026, 5, 10)
    assert result.inspector == "J. Bhatt"
    assert result.capacity_lbs == 3500
    assert result.next_due == date(2027, 5, 10)


def test_missing_capacity_is_none_not_fabricated():
    result = parse_layout_c(SAMPLE_TEXT_MISSING_CAPACITY)
    assert result.capacity_lbs is None
    # every other field still parses fine
    assert result.cert_no == "MES-2026-4105"
    assert result.city == "Missoula"
    assert result.state == "MT"


def test_zero_defects_when_section_absent():
    result = parse_layout_c(SAMPLE_TEXT_MISSING_CAPACITY)
    assert result.result == "PASS"
    assert result.defect_count == 0


def test_parse_layout_c_on_garbage_text_returns_all_none_no_crash():
    result = parse_layout_c("this is not an inspection certificate at all")
    assert result.cert_no is None
    assert result.capacity_lbs is None
    assert result.defect_count == 0


def test_parsing_is_deterministic():
    assert parse_layout_c(SAMPLE_TEXT_WITH_DEFECTS) == parse_layout_c(SAMPLE_TEXT_WITH_DEFECTS)
