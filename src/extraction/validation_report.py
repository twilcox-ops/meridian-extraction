"""Stage 3 entry point: route every document (Stage 2), validate whatever
came out of extraction against the schema (Stage 3), and report per
document. A document with no extraction yet (Layout B/C, no parser) is
reported as skipped, not silently counted as valid or invalid.
"""

from __future__ import annotations

import sys
from pathlib import Path

from extraction.pdf_io import extract_text
from extraction.router import route
from extraction.validate import validate_extraction

DEFAULT_SAMPLE_DATA = Path(__file__).resolve().parents[2] / "sample-data" / "inspection-certs"


def main() -> None:
    sample_data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SAMPLE_DATA
    pdf_paths = sorted(sample_data_dir.glob("*.pdf"))

    valid_count = 0
    invalid: list[tuple[str, tuple[str, ...]]] = []
    skipped_count = 0

    print(f"{'file':<20} {'layout':<8} status")
    for pdf_path in pdf_paths:
        text = extract_text(pdf_path)
        routed = route(text)

        detected = routed.layout or routed.classification.status.upper()

        if routed.result is None:
            skipped_count += 1
            print(f"{pdf_path.name:<20} {detected:<8} skipped (no extraction to validate)")
            continue

        outcome = validate_extraction(routed.result)
        if outcome.valid:
            valid_count += 1
            print(f"{pdf_path.name:<20} {detected:<8} valid")
        else:
            invalid.append((pdf_path.name, outcome.errors))
            print(f"{pdf_path.name:<20} {detected:<8} INVALID")

    print()
    print(f"Valid: {valid_count}  Invalid: {len(invalid)}  Skipped: {skipped_count}")

    if invalid:
        print()
        print(f"FLAGGED ({len(invalid)}) -- failed schema validation, needs review:")
        for file, errors in invalid:
            print(f"  {file}:")
            for error in errors:
                print(f"    - {error}")
    else:
        print("No documents flagged by schema validation.")


if __name__ == "__main__":
    main()
