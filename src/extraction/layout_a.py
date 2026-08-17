"""Deterministic parser for Layout A — the clean single-column label/value
inspection certificate.

Stage 1 scope, on purpose: this module only knows how to read Layout A. It
does not try to detect layout (Stage 2), validate the values it finds
(Stage 3), attach confidence or route anything to a review queue (Stage 4),
or fall back to an LLM (Stage 5). A regex that works is cheaper, faster, and
more debuggable than a model call, and Layout A is clean enough that it
should get us to 100% field accuracy without one.

Every field is either extracted correctly or reported as missing — never
guessed. `parse_layout_a` returns `None` for any field its regex doesn't
match, rather than inventing a plausible value.
"""

from __future__ import annotations

import re
from datetime import date

from extraction.models import ExtractionResult

# One marker that this text plausibly is Layout A. Real routing across all
# three layouts is Stage 2's job; this is just a guard so this parser
# refuses to silently misparse a document it wasn't built for.
LAYOUT_A_MARKER = re.compile(r"Annual Safety Inspection Certificate")

_FIELD_PATTERNS: dict[str, re.Pattern[str]] = {
    "cert_no": re.compile(r"^Certificate No:\s*(\S+)\s*$", re.MULTILINE),
    "unit_id": re.compile(r"^Unit ID:\s*(\S+)\s*$", re.MULTILINE),
    "building": re.compile(r"^Building:\s*(.+?)\s*$", re.MULTILINE),
    "address": re.compile(r"^Address:\s*(.+?)\s*$", re.MULTILINE),
    "unit_type": re.compile(r"^Unit Type:\s*(.+?)\s*$", re.MULTILINE),
    "capacity_lbs": re.compile(r"^Capacity \(lbs\):\s*(\d+)\s*$", re.MULTILINE),
    "inspection_date": re.compile(r"^Inspection Date:\s*(\d{2}/\d{2}/\d{4})\s*$", re.MULTILINE),
    "next_due": re.compile(r"^Next Due:\s*(\d{2}/\d{2}/\d{4})\s*$", re.MULTILINE),
    "inspector": re.compile(r"^Inspector:\s*(.+?)\s*$", re.MULTILINE),
    "result": re.compile(r"^Result:\s*(.+?)\s*$", re.MULTILINE),
    "invoice_total": re.compile(r"^Invoice Total:\s*\$([\d,]+\.\d{2})\s*$", re.MULTILINE),
}

# A defect line under "Defects Noted:" — indented, starts with "- ".
_DEFECT_LINE = re.compile(r"^\s*-\s+.+$", re.MULTILINE)


def _parse_date(value: str) -> date | None:
    try:
        month, day, year = value.split("/")
        return date(int(year), int(month), int(day))
    except (ValueError, AttributeError):
        return None


def _split_address(address: str | None) -> tuple[str | None, str | None]:
    """"88 Ninth Ave, Denver, CO 80202" -> ("Denver", "CO").

    Only city/state are in the ground-truth schema; street and zip are
    parsed implicitly (to find the boundary) and then discarded.
    """
    if address is None:
        return None, None
    parts = [p.strip() for p in address.split(",")]
    if len(parts) < 3:
        return None, None
    city = parts[-2] or None
    state_zip = parts[-1].split()
    state = state_zip[0] if state_zip else None
    return city, state


def _count_defects(text: str) -> int:
    """Defects Noted: section is omitted entirely when there are none, so
    "no section" and "zero defects" are the same, correct answer: 0.
    """
    marker = text.find("Defects Noted:")
    if marker == -1:
        return 0
    section = text[marker:]
    return len(_DEFECT_LINE.findall(section))


def is_layout_a(text: str) -> bool:
    """Cheap applicability check, not full layout detection (Stage 2)."""
    return LAYOUT_A_MARKER.search(text) is not None


def parse_layout_a(text: str) -> ExtractionResult:
    """Parse Layout A document text into structured fields.

    Deterministic and side-effect free: the same `text` in always produces
    the same `ExtractionResult` out, which is what makes reprocessing a PDF
    twice produce identical output.
    """
    raw: dict[str, str | None] = {}
    for field_name, pattern in _FIELD_PATTERNS.items():
        match = pattern.search(text)
        raw[field_name] = match.group(1) if match else None

    city, state = _split_address(raw["address"])

    capacity_lbs = int(raw["capacity_lbs"]) if raw["capacity_lbs"] is not None else None
    invoice_total = (
        float(raw["invoice_total"].replace(",", "")) if raw["invoice_total"] is not None else None
    )
    inspection_date = _parse_date(raw["inspection_date"]) if raw["inspection_date"] else None
    next_due = _parse_date(raw["next_due"]) if raw["next_due"] else None

    return ExtractionResult(
        cert_no=raw["cert_no"],
        unit_id=raw["unit_id"],
        building=raw["building"],
        city=city,
        state=state,
        unit_type=raw["unit_type"],
        capacity_lbs=capacity_lbs,
        inspection_date=inspection_date,
        next_due=next_due,
        inspector=raw["inspector"],
        result=raw["result"],
        invoice_total=invoice_total,
        defect_count=_count_defects(text),
    )
