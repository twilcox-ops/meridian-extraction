"""Stage 5 entry point: run the LLM fallback over every Layout C document
and report the thing the project doc asks for explicitly -- accuracy with
and without the fallback, cost per document, latency per document -- not
just whether it ran.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

from extraction.accuracy import normalize_ground_truth_row
from extraction.llm_fallback import LLMCache, resolve_missing_fields
from extraction.models import FIELD_NAMES
from extraction.pdf_io import extract_text
from extraction.router import route

DEFAULT_SAMPLE_DATA = Path(__file__).resolve().parents[2] / "sample-data" / "inspection-certs"


def _field_accuracy(result_dict: dict[str, object], expected: dict[str, object]) -> tuple[int, int]:
    correct = sum(1 for name in FIELD_NAMES if result_dict[name] == expected[name])
    return correct, len(FIELD_NAMES)


def main() -> None:
    sample_data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SAMPLE_DATA
    ground_truth_path = sample_data_dir / "GROUND_TRUTH.csv"
    with ground_truth_path.open(newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["layout"] == "C"]

    cache = LLMCache()

    correct_before = correct_after = total_fields = 0
    calls_made = cache_hits = 0
    total_cost = 0.0
    fresh_latencies: list[float] = []

    print(f"{'file':<20} {'called':<8} {'source':<10} {'cost':<10} {'latency':<10} status")
    for row in rows:
        pdf_path = sample_data_dir / row["file"]
        text = extract_text(pdf_path)
        routed = route(text)
        assert routed.layout == "C" and routed.result is not None, row["file"]

        expected = normalize_ground_truth_row(row)
        before_dict = routed.result.as_dict()
        c, t = _field_accuracy(before_dict, expected)
        correct_before += c
        total_fields += t

        outcome = resolve_missing_fields(text, routed.result, cache)
        after_dict = outcome.result.as_dict()
        c2, _ = _field_accuracy(after_dict, expected)
        correct_after += c2

        if outcome.called:
            calls_made += 1
            total_cost += outcome.cost_usd
            source = "cache" if outcome.from_cache else "api"
            if outcome.from_cache:
                cache_hits += 1
            else:
                fresh_latencies.append(outcome.latency_seconds)
            status = f"requested={list(outcome.fields_requested)} filled={list(outcome.fields_filled)}"
        else:
            source = "-"
            status = "nothing missing, no call made"

        print(
            f"{row['file']:<20} {str(outcome.called):<8} {source:<10} "
            f"${outcome.cost_usd:<9.5f} {outcome.latency_seconds:<10.2f} {status}"
        )

    print()
    print(f"Layout C documents: {len(rows)}")
    print(f"Documents needing the LLM fallback (a field was missing): {calls_made}")
    print(f"  of which served from cache (no new API call this run): {cache_hits}")
    print(f"  of which made a fresh API call: {len(fresh_latencies)}")
    print()
    print(f"Field accuracy WITHOUT fallback (deterministic parser only): {correct_before / total_fields:.1%}")
    print(f"Field accuracy WITH fallback:                                {correct_after / total_fields:.1%}")
    print()
    print(f"Total cost this run: ${total_cost:.5f}")
    print(f"Cost per document needing the fallback: "
          f"${(total_cost / calls_made) if calls_made else 0.0:.5f}")
    print(f"Cost per document across all of Layout C: ${total_cost / len(rows):.5f}")
    if fresh_latencies:
        avg_latency = sum(fresh_latencies) / len(fresh_latencies)
        print(f"Average latency per fresh API call: {avg_latency:.2f}s")
    else:
        print("Average latency per fresh API call: n/a (all calls served from cache this run)")


if __name__ == "__main__":
    main()
