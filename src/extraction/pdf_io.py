"""Thin wrapper around pdfplumber so the rest of the pipeline works with
plain text, not pdfplumber objects. Keeping this isolated means swapping in
a different PDF library later (Stage 5's vision-model experiment, the
Textract/Azure comparison in the stretch goals) only touches this one file.
"""

from __future__ import annotations

from pathlib import Path

import pdfplumber


def extract_text(pdf_path: str | Path) -> str:
    """Extract all text from a PDF, page by page, joined with blank lines.

    Deterministic: pdfplumber's layout-aware extraction returns the same
    string for the same file on every run, which is what lets Stage 1
    satisfy "reprocessing the same PDF twice produces identical output."
    """
    pdf_path = Path(pdf_path)
    pages: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
    return "\n\n".join(pages)
