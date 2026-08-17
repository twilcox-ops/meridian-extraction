"""Score deterministic extraction against GROUND_TRUTH.csv, broken out by
layout and by field.

Only layouts with a working parser (Stage 2's `router.py`) get scored — a
row is routed for real, not just looked up by its ground-truth layout
column, so a routing regression would show up here as documents dropping
out of scoring, not as silently wrong numbers. Layout B has no parser by
design (see README): its documents are counted and reported as skipped,
never run through the wrong parser and never silently treated as 0%
accurate. "Skipped" and "wrong" are different findings, and this report
keeps them distinct.
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from extraction.models import FIELD_NAMES
from extraction.pdf_io import extract_text
from extraction.router import route


def _normalize_ground_truth_row(row: dict[str, str]) -> dict[str, object]:
    """Convert a GROUND_TRUTH.csv row into the same types ExtractionResult
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


class FieldMismatch:
    __slots__ = ("file", "layout", "field", "expected", "actual")

    def __init__(self, file: str, layout: str, field: str, expected: object, actual: object) -> None:
        self.file = file
        self.layout = layout
        self.field = field
        self.expected = expected
        self.actual = actual


class LayoutAccuracy:
    """Per-field correct/total counts for one layout."""

    def __init__(self) -> None:
        self.field_correct: dict[str, int] = {name: 0 for name in FIELD_NAMES}
        self.field_total: dict[str, int] = {name: 0 for name in FIELD_NAMES}
        self.documents_scored = 0

    def record(self, extracted: dict[str, object], expected: dict[str, object]) -> list[str]:
        """Score one document's fields; returns the names of any that were wrong."""
        wrong_fields = []
        for name in FIELD_NAMES:
            self.field_total[name] += 1
            if extracted[name] == expected[name]:
                self.field_correct[name] += 1
            else:
                wrong_fields.append(name)
        self.documents_scored += 1
        return wrong_fields

    def overall_accuracy(self) -> float:
        total = sum(self.field_total.values())
        correct = sum(self.field_correct.values())
        return correct / total if total else 0.0

    def field_accuracy(self, field: str) -> float:
        total = self.field_total[field]
        return self.field_correct[field] / total if total else 0.0


class AccuracyReport:
    def __init__(self) -> None:
        self.layouts: dict[str, LayoutAccuracy] = {}
        self.skipped_by_layout: dict[str, int] = {}
        self.mismatches: list[FieldMismatch] = []

    def documents_scored(self) -> int:
        return sum(la.documents_scored for la in self.layouts.values())

    def documents_skipped(self) -> int:
        return sum(self.skipped_by_layout.values())

    def overall_accuracy(self) -> float:
        total = sum(sum(la.field_total.values()) for la in self.layouts.values())
        correct = sum(sum(la.field_correct.values()) for la in self.layouts.values())
        return correct / total if total else 0.0


def score_extraction(sample_data_dir: Path) -> AccuracyReport:
    """Route and score every document in GROUND_TRUTH.csv, layout by
    layout. A document only contributes to `layouts[...]` if `route()`
    actually produced an extraction for it; otherwise it's counted in
    `skipped_by_layout`, keyed by its ground-truth layout for reporting.
    """
    ground_truth_path = sample_data_dir / "GROUND_TRUTH.csv"
    with ground_truth_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    report = AccuracyReport()

    for row in rows:
        pdf_path = sample_data_dir / row["file"]
        text = extract_text(pdf_path)
        routed = route(text)
        layout = row["layout"]

        if routed.result is None:
            report.skipped_by_layout[layout] = report.skipped_by_layout.get(layout, 0) + 1
            continue

        extracted = routed.result.as_dict()
        expected = _normalize_ground_truth_row(row)
        layout_accuracy = report.layouts.setdefault(layout, LayoutAccuracy())
        wrong_fields = layout_accuracy.record(extracted, expected)
        for name in wrong_fields:
            report.mismatches.append(
                FieldMismatch(
                    file=row["file"],
                    layout=layout,
                    field=name,
                    expected=expected[name],
                    actual=extracted[name],
                )
            )

    return report
