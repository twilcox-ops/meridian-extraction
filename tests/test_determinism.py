"""Acceptance criterion: reprocessing the same PDF twice produces identical
output. Parsing is pure (regex over a string, no timestamps, no randomness,
no I/O side effects beyond reading the file), so this should hold trivially
— but it's exactly the kind of thing that's cheap to assert and easy to
silently break later.

The Stage-1-level tests below check the parser in isolation. The
end-to-end tests check the same property through the whole pipeline —
routing, validation, confidence, and the review-queue decision — because
that's the property the acceptance criterion actually describes, and
nothing guarantees each new stage stays pure just because parsing is.
This matters more once Stage 5 adds an LLM call: those aren't
deterministic by default, and this test is what would catch it if a
caching/pinning strategy stopped doing its job.
"""

from extraction.layout_a import parse_layout_a
from extraction.pdf_io import extract_text
from extraction.review_queue import evaluate_document
from extraction.router import route
from extraction.validate import validate_extraction


def test_reprocessing_same_pdf_is_identical(sample_data_dir):
    pdf_path = sample_data_dir / "MES-2026-4100.pdf"

    first = parse_layout_a(extract_text(pdf_path))
    second = parse_layout_a(extract_text(pdf_path))

    assert first == second


def test_reparsing_same_text_is_identical():
    text = "Certificate No:   MES-2026-9999\nUnit ID:          A00-0\n"
    assert parse_layout_a(text) == parse_layout_a(text)


def test_routing_is_identical_across_reprocessing(sample_data_dir):
    for filename in ("MES-2026-4100.pdf", "MES-2026-4101.pdf", "MES-2026-4102.pdf"):
        pdf_path = sample_data_dir / filename
        first = route(extract_text(pdf_path))
        second = route(extract_text(pdf_path))
        assert first == second


def test_validation_outcome_is_identical_across_reprocessing(sample_data_dir):
    pdf_path = sample_data_dir / "MES-2026-4100.pdf"
    result_a = route(extract_text(pdf_path)).result
    result_b = route(extract_text(pdf_path)).result
    assert validate_extraction(result_a) == validate_extraction(result_b)


def test_full_pipeline_is_identical_across_reprocessing(sample_data_dir):
    """The exact acceptance criterion: reprocess the same PDF end to end
    (route -> validate -> confidence -> review-queue decision) and expect
    byte-for-byte identical output, for a clean document, a missing-field
    document, and an unparsed-layout document alike."""
    for filename in (
        "MES-2026-4100.pdf",  # Layout A, clean
        "MES-2026-4102.pdf",  # Layout C, missing capacity_lbs
        "MES-2026-4101.pdf",  # Layout B, no parser at all
    ):
        pdf_path = sample_data_dir / filename
        first = evaluate_document(pdf_path)
        second = evaluate_document(pdf_path)
        assert first == second
