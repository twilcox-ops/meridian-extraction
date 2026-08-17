"""One real end-to-end check against the actual Claude API -- not a mock.
Skipped automatically when no API key is configured (e.g. CI without
secrets). Uses the project's real cache (`var/llm_cache.jsonl`), so after
the first real run this test costs nothing on every subsequent run: it's
exercising the same cache key the real `report-llm-fallback` run already
populated, not minting a new one.
"""

from __future__ import annotations

import os

import pytest

pytest.importorskip("anthropic")

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not configured (see .env)",
)


def test_llm_fallback_confirms_genuinely_missing_capacity(sample_data_dir):
    """The one document this whole stage is built around: capacity_lbs is
    truly absent from the source PDF. The real model must return null for
    it -- not invent a plausible number -- and the merged result must still
    show capacity_lbs as None afterward."""
    from extraction.llm_fallback import LLMCache, resolve_missing_fields
    from extraction.pdf_io import extract_text
    from extraction.router import route

    pdf_path = sample_data_dir / "MES-2026-4102.pdf"
    text = extract_text(pdf_path)
    routed = route(text)
    assert routed.layout == "C"
    assert routed.result.capacity_lbs is None  # deterministic parser already confirms this

    cache = LLMCache()  # the project's real cache -- this key is already populated
    outcome = resolve_missing_fields(text, routed.result, cache)

    assert outcome.called is True
    assert outcome.result.capacity_lbs is None  # LLM confirmed absence, never fabricated
    assert outcome.fields_filled == ()
    # Real usage was billed on the first-ever run of this key; every run
    # since (including this one, most likely) is a free cache hit.
    if outcome.from_cache:
        assert outcome.cost_usd == 0.0
        assert outcome.latency_seconds == 0.0
    else:
        assert outcome.cost_usd > 0


def test_reprocessing_the_same_document_is_identical(sample_data_dir):
    """The acceptance criterion, exercised against the real cache: run the
    LLM fallback on the same document twice and expect byte-identical
    output, same as the rest of the pipeline."""
    from extraction.llm_fallback import LLMCache, resolve_missing_fields
    from extraction.pdf_io import extract_text
    from extraction.router import route

    pdf_path = sample_data_dir / "MES-2026-4102.pdf"
    text = extract_text(pdf_path)
    routed = route(text)
    cache = LLMCache()

    first = resolve_missing_fields(text, routed.result, cache)
    second = resolve_missing_fields(text, routed.result, cache)

    assert first.result == second.result
    assert second.from_cache is True
