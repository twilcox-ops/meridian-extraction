"""Deterministic parser for Layout C — the two-column prose certificate.

Layout C is harder than Layout A on purpose: a prose preamble instead of
label/value lines, different label wording (`Equipment No.` instead of
`Unit ID`), the invoice total buried mid-sentence, and the re-inspection
date phrased as a clause that can wrap across lines differently from one
document to the next. A few Layout C documents also omit the capacity
field entirely — the correct output for those is an explicit `None`, never
a fabricated number.

`pdfplumber`'s default `extract_text()` collapses the visual two-column
layout down to single-spaced text (unlike `pdftotext -layout`, which
preserves column alignment). That's actually simpler to parse: the two
columns become two `label: value` pairs separated by whitespace on the
same line, so each pair can be pulled out with one anchored regex per
line rather than by column position.
"""

from __future__ import annotations

import re
from datetime import date

from extraction.models import ExtractionResult

# Boilerplate opening sentence — same guard pattern as Layout A's marker.
LAYOUT_C_MARKER = re.compile(r"The conveyance identified below was examined on")

_CERT_NO = re.compile(r"reference\s+(\S+)\s+and\s+supersedes")
# The preamble sentence's word-wrap point shifts depending on how long the
# inspector's name is -- sometimes "an\nauthorized inspector", sometimes
# "an authorized\ninspector". \s+ at every join tolerates either.
_DATE_INSPECTOR = re.compile(
    r"examined\s+on\s+(?P<date>\d{2}/\d{2}/\d{4})\s+by\s+(?P<inspector>.+?),"
    r"\s+acting\s+as\s+an\s+authorized\s+inspector"
)
_PREMISES_EQUIPMENT = re.compile(r"Premises:\s*(?P<building>.+?)\s+Equipment No\.:\s*(?P<unit_id>\S+)")
_CLASSIFICATION = re.compile(r"Classification:\s*(?P<unit_type>.+?)\s*$", re.MULTILINE)
_MUNICIPALITY_LOAD = re.compile(
    r"Municipality:\s*(?P<city>.+?),\s*(?P<state>[A-Za-z]{2})\s+"
    r"Rated Load:\s*(?P<capacity>\d+)?\s*pounds"
)
_OUTCOME = re.compile(r"Outcome:\s*(?P<result>.+?)\s*$", re.MULTILINE)
_INVOICE_TOTAL = re.compile(r"total\s+\$(?P<amount>[\d,]+\.\d{2})")
_NEXT_DUE = re.compile(r"Re-examination shall occur no\s+later\s+than\s+(?P<date>\d{2}/\d{2}/\d{4})")

# Bullet glyph pdfplumber can't map to a Unicode character comes through
# as the literal string "(cid:127)" — one per defect line.
_DEFECT_LINE = re.compile(r"^\(cid:127\)\s+.+$", re.MULTILINE)


def _parse_date(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        month, day, year = value.split("/")
        return date(int(year), int(month), int(day))
    except (ValueError, AttributeError):
        return None


def _count_defects(text: str) -> int:
    """"Items requiring corrective action:" is omitted entirely when there
    are none, so "no section" and "zero defects" are the same, correct
    answer: 0 — same convention as Layout A's "Defects Noted:"."""
    marker = text.find("Items requiring corrective action:")
    if marker == -1:
        return 0
    return len(_DEFECT_LINE.findall(text[marker:]))


def is_layout_c(text: str) -> bool:
    """Cheap applicability check, not full layout detection (Stage 2)."""
    return LAYOUT_C_MARKER.search(text) is not None


def parse_layout_c(text: str) -> ExtractionResult:
    """Parse Layout C document text into structured fields.

    Deterministic and side-effect free, same as `parse_layout_a`. Any
    field whose regex doesn't match comes back `None` — most importantly
    `capacity_lbs`, which several real Layout C documents omit outright.
    """
    cert_no_match = _CERT_NO.search(text)
    date_inspector_match = _DATE_INSPECTOR.search(text)
    premises_match = _PREMISES_EQUIPMENT.search(text)
    classification_match = _CLASSIFICATION.search(text)
    municipality_match = _MUNICIPALITY_LOAD.search(text)
    outcome_match = _OUTCOME.search(text)
    invoice_match = _INVOICE_TOTAL.search(text)
    next_due_match = _NEXT_DUE.search(text)

    capacity_raw = municipality_match.group("capacity") if municipality_match else None

    return ExtractionResult(
        cert_no=cert_no_match.group(1) if cert_no_match else None,
        unit_id=premises_match.group("unit_id") if premises_match else None,
        building=premises_match.group("building") if premises_match else None,
        city=municipality_match.group("city") if municipality_match else None,
        state=municipality_match.group("state") if municipality_match else None,
        unit_type=classification_match.group("unit_type") if classification_match else None,
        capacity_lbs=int(capacity_raw) if capacity_raw else None,
        inspection_date=_parse_date(date_inspector_match.group("date") if date_inspector_match else None),
        next_due=_parse_date(next_due_match.group("date") if next_due_match else None),
        inspector=date_inspector_match.group("inspector") if date_inspector_match else None,
        result=outcome_match.group("result") if outcome_match else None,
        invoice_total=float(invoice_match.group("amount").replace(",", "")) if invoice_match else None,
        defect_count=_count_defects(text),
    )
