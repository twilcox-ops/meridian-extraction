"""Entry point: run every layout that has a working parser over the sample
corpus and report field-level accuracy against GROUND_TRUTH.csv, broken
out per layout and per field.
"""

from __future__ import annotations

import sys
from pathlib import Path

from extraction.accuracy import score_extraction

DEFAULT_SAMPLE_DATA = Path(__file__).resolve().parents[2] / "sample-data" / "inspection-certs"


def main() -> None:
    sample_data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SAMPLE_DATA
    report = score_extraction(sample_data_dir)

    print(f"Documents scored: {report.documents_scored()}")
    if report.skipped_by_layout:
        skipped_str = ", ".join(f"{layout}={count}" for layout, count in sorted(report.skipped_by_layout.items()))
        print(f"Documents skipped (no parser for that layout): {report.documents_skipped()} ({skipped_str})")
    print()
    print(f"Overall field accuracy (all scored layouts): {report.overall_accuracy():.1%}")

    for layout in sorted(report.layouts):
        layout_accuracy = report.layouts[layout]
        print()
        print(f"Layout {layout} - {layout_accuracy.documents_scored} documents, "
              f"{layout_accuracy.overall_accuracy():.1%} overall")
        for field in layout_accuracy.field_total:
            print(f"  {field:<16} {layout_accuracy.field_accuracy(field):.1%}")

    if report.mismatches:
        print()
        print(f"Mismatches ({len(report.mismatches)}):")
        for m in report.mismatches:
            print(f"  {m.file}  layout={m.layout}  {m.field}: expected={m.expected!r} actual={m.actual!r}")


if __name__ == "__main__":
    main()
