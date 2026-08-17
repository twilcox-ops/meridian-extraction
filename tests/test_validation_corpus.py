"""End-to-end: every real document with a working parser (Layout A and
Layout C), routed and then validated, should pass schema validation
cleanly -- the sample corpus has no contradictions or out-of-range values
planted in it, and a missing capacity_lbs (some Layout C documents) is
schema-valid on its own, not a validation failure. The cross-field rules
themselves are exercised against synthetic data in test_schema.py; this
test is here to catch the case where the real data doesn't agree with that
assumption.
"""

from extraction.pdf_io import extract_text
from extraction.router import route
from extraction.validate import validate_extraction


def test_all_parsed_documents_pass_validation(sample_data_dir):
    pdf_paths = sorted(sample_data_dir.glob("*.pdf"))
    checked_by_layout: dict[str, int] = {}
    for pdf_path in pdf_paths:
        routed = route(extract_text(pdf_path))
        if routed.result is None:
            continue  # Layout B: no parser (deliberate scope boundary)
        checked_by_layout[routed.layout] = checked_by_layout.get(routed.layout, 0) + 1
        outcome = validate_extraction(routed.result)
        assert outcome.valid, f"{pdf_path.name}: {outcome.errors}"

    assert checked_by_layout == {"A": 12, "C": 12}
