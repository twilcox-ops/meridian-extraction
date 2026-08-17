"""Stage 2 entry point: classify and route every document in the sample
corpus, report where each one landed, and call out any misrouting loudly
rather than letting it blend into a summary percentage.
"""

from __future__ import annotations

import csv
import sys
from dataclasses import dataclass
from pathlib import Path

from extraction.pdf_io import extract_text
from extraction.router import RoutedDocument, route

DEFAULT_SAMPLE_DATA = Path(__file__).resolve().parents[2] / "sample-data" / "inspection-certs"


@dataclass
class RoutingRow:
    file: str
    routed: RoutedDocument
    expected: str | None  # ground-truth layout, if a GROUND_TRUTH.csv is present

    @property
    def detected(self) -> str:
        """The detected layout letter, or the failure mode (UNKNOWN /
        AMBIGUOUS) when classification didn't land on exactly one layout."""
        return self.routed.layout or self.routed.classification.status.upper()

    @property
    def is_misrouted(self) -> bool:
        if self.routed.classification.status != "ok":
            return True
        if self.expected is not None and self.routed.layout != self.expected:
            return True
        return False


def _load_ground_truth_layouts(sample_data_dir: Path) -> dict[str, str]:
    """Ground truth is a dev/test convenience for cross-checking routing
    against a known answer key. Real documents won't have one — `route()`
    itself never depends on this."""
    path = sample_data_dir / "GROUND_TRUTH.csv"
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as f:
        return {row["file"]: row["layout"] for row in csv.DictReader(f)}


def build_routing_rows(sample_data_dir: Path) -> list[RoutingRow]:
    ground_truth = _load_ground_truth_layouts(sample_data_dir)
    rows = []
    for pdf_path in sorted(sample_data_dir.glob("*.pdf")):
        text = extract_text(pdf_path)
        routed = route(text)
        rows.append(
            RoutingRow(file=pdf_path.name, routed=routed, expected=ground_truth.get(pdf_path.name))
        )
    return rows


def main() -> None:
    sample_data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SAMPLE_DATA
    rows = build_routing_rows(sample_data_dir)

    print(f"{'file':<20} {'detected':<10} {'expected':<10} status")
    for row in rows:
        status = "MISROUTED" if row.is_misrouted else "ok"
        print(f"{row.file:<20} {row.detected:<10} {row.expected or '?':<10} {status}")

    layout_counts: dict[str, int] = {}
    for row in rows:
        layout_counts[row.detected] = layout_counts.get(row.detected, 0) + 1
    print()
    print("Detected layout counts: " + ", ".join(f"{k}={v}" for k, v in sorted(layout_counts.items())))

    scored = [row for row in rows if row.expected is not None]
    if scored:
        correct = sum(1 for row in scored if row.routed.layout == row.expected)
        print(f"Routing accuracy vs ground truth: {correct}/{len(scored)} ({correct / len(scored):.1%})")

    misrouted = [row for row in rows if row.is_misrouted]
    print()
    if misrouted:
        print(f"MISROUTED ({len(misrouted)}) -- needs a human, not a guess:")
        for row in misrouted:
            print(
                f"  {row.file}: detected={row.detected!r} expected={row.expected!r} "
                f"note={row.routed.note!r}"
            )
    else:
        print("No misrouted documents.")


if __name__ == "__main__":
    main()
