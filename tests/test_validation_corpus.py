"""End-to-end: every real Layout A document, routed and then validated,
should pass schema validation cleanly -- the sample corpus has no
contradictions or out-of-range values planted in it. The cross-field rules
themselves are exercised against synthetic data in test_schema.py; this
test is here to catch the case where the real data doesn't agree with that
assumption.
"""

from extraction.pdf_io import extract_text
from extraction.router import route
from extraction.validate import validate_extraction


def test_all_layout_a_documents_pass_validation(sample_data_dir):
    layout_a_pdfs = sorted(sample_data_dir.glob("*.pdf"))
    checked = 0
    for pdf_path in layout_a_pdfs:
        routed = route(extract_text(pdf_path))
        if routed.result is None:
            continue  # Layout B/C: no parser yet, nothing to validate
        checked += 1
        outcome = validate_extraction(routed.result)
        assert outcome.valid, f"{pdf_path.name}: {outcome.errors}"

    assert checked == 12  # the 12 Layout A documents in the corpus
