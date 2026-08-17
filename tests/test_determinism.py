"""Acceptance criterion: reprocessing the same PDF twice produces identical
output. Parsing is pure (regex over a string, no timestamps, no randomness,
no I/O side effects beyond reading the file), so this should hold trivially
— but it's exactly the kind of thing that's cheap to assert and easy to
silently break later.
"""

from extraction.layout_a import parse_layout_a
from extraction.pdf_io import extract_text


def test_reprocessing_same_pdf_is_identical(sample_data_dir):
    pdf_path = sample_data_dir / "MES-2026-4100.pdf"

    first = parse_layout_a(extract_text(pdf_path))
    second = parse_layout_a(extract_text(pdf_path))

    assert first == second


def test_reparsing_same_text_is_identical():
    text = "Certificate No:   MES-2026-9999\nUnit ID:          A00-0\n"
    assert parse_layout_a(text) == parse_layout_a(text)
