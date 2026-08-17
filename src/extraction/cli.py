"""Stage 1 entry point: run the Layout A parser over the sample corpus and
report field-level accuracy against GROUND_TRUTH.csv.
"""

from __future__ import annotations

import sys
from pathlib import Path

from extraction.accuracy import score_layout_a

DEFAULT_SAMPLE_DATA = Path(__file__).resolve().parents[2] / "sample-data" / "inspection-certs"


def main() -> None:
    sample_data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SAMPLE_DATA
    report = score_layout_a(sample_data_dir)

    print(f"Layout A documents scored: {report.documents_scored}")
    print(f"Documents skipped (not Layout A, no parser yet): {report.documents_skipped}")
    print()
    print(f"Overall field accuracy: {report.overall_accuracy():.1%}")
    print()
    print("Per-field accuracy:")
    for field in report.field_total:
        print(f"  {field:<16} {report.field_accuracy(field):.1%}")

    if report.mismatches:
        print()
        print(f"Mismatches ({len(report.mismatches)}):")
        for m in report.mismatches:
            print(f"  {m.file}  {m.field}: expected={m.expected!r} actual={m.actual!r}")


if __name__ == "__main__":
    main()
