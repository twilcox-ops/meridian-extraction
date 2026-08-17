"""Score Layout A extraction against GROUND_TRUTH.csv.

Stage 1 only scores Layout A documents — Stage 2 hasn't been built yet to
route Layout B/C documents anywhere, and running this parser on them would
just produce a wall of `None`s that are misleading, not informative. Those
rows are counted and reported as skipped, not silently dropped.
"""

from __future__ import annotations

import csv
from dataclasses import fields
from datetime import date
from pathlib import Path

from extraction.layout_a import LayoutAResult, parse_layout_a
from extraction.pdf_io import extract_text

_FIELD_NAMES = [f.name for f in fields(LayoutAResult)]


def _normalize_ground_truth_row(row: dict[str, str]) -> dict[str, object]:
    """Convert a GROUND_TRUTH.csv row into the same types LayoutAResult
    uses, so comparison is a plain `==` per field."""

    def parse_date(value: str) -> date | None:
        if not value:
            return None
        month, day, year = value.split("/")
        return date(int(year), int(month), int(day))

    return {
        "cert_no": row["cert_no"] or None,
        "unit_id": row["unit_id"] or None,
        "building": row["building"] or None,
        "city": row["city"] or None,
        "state": row["state"] or None,
        "unit_type": row["unit_type"] or None,
        "capacity_lbs": int(row["capacity_lbs"]) if row["capacity_lbs"] else None,
        "inspection_date": parse_date(row["inspection_date"]),
        "next_due": parse_date(row["next_due"]),
        "inspector": row["inspector"] or None,
        "result": row["result"] or None,
        "invoice_total": float(row["invoice_total"]) if row["invoice_total"] else None,
        "defect_count": int(row["defect_count"]) if row["defect_count"] else None,
    }


def score_layout_a(sample_data_dir: Path) -> "AccuracyReport":
    """Run the Layout A parser over every Layout-A row in GROUND_TRUTH.csv
    and score each field against the ground-truth value."""
    ground_truth_path = sample_data_dir / "GROUND_TRUTH.csv"
    with ground_truth_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    layout_a_rows = [r for r in rows if r["layout"] == "A"]
    other_layout_count = len(rows) - len(layout_a_rows)

    field_correct = {name: 0 for name in _FIELD_NAMES}
    field_total = {name: 0 for name in _FIELD_NAMES}
    mismatches: list[FieldMismatch] = []

    for row in layout_a_rows:
        pdf_path = sample_data_dir / row["file"]
        text = extract_text(pdf_path)
        extracted = parse_layout_a(text).as_dict()
        expected = _normalize_ground_truth_row(row)

        for name in _FIELD_NAMES:
            field_total[name] += 1
            if extracted[name] == expected[name]:
                field_correct[name] += 1
            else:
                mismatches.append(
                    FieldMismatch(
                        file=row["file"],
                        field=name,
                        expected=expected[name],
                        actual=extracted[name],
                    )
                )

    return AccuracyReport(
        documents_scored=len(layout_a_rows),
        documents_skipped=other_layout_count,
        field_correct=field_correct,
        field_total=field_total,
        mismatches=mismatches,
    )


class FieldMismatch:
    __slots__ = ("file", "field", "expected", "actual")

    def __init__(self, file: str, field: str, expected: object, actual: object) -> None:
        self.file = file
        self.field = field
        self.expected = expected
        self.actual = actual


class AccuracyReport:
    def __init__(
        self,
        documents_scored: int,
        documents_skipped: int,
        field_correct: dict[str, int],
        field_total: dict[str, int],
        mismatches: list[FieldMismatch],
    ) -> None:
        self.documents_scored = documents_scored
        self.documents_skipped = documents_skipped
        self.field_correct = field_correct
        self.field_total = field_total
        self.mismatches = mismatches

    def overall_accuracy(self) -> float:
        total = sum(self.field_total.values())
        correct = sum(self.field_correct.values())
        return correct / total if total else 0.0

    def field_accuracy(self, field: str) -> float:
        total = self.field_total[field]
        return self.field_correct[field] / total if total else 0.0
