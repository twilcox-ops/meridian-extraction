"""Unit tests for the Stage 5 LLM fallback, using a fake caller so these
never touch the network or spend real money. The one test that calls the
real Claude API lives in test_llm_fallback_live.py, guarded and cached.
"""

from datetime import date

from extraction.llm_fallback import (
    LLMCache,
    LLMRawResponse,
    resolve_missing_fields,
)
from extraction.models import ExtractionResult

FULL_RESULT = ExtractionResult(
    cert_no="MES-2026-4102",
    unit_id="E11-2",
    building="Harborview Tower",
    city="Portland",
    state="OR",
    unit_type="Freight",
    capacity_lbs=None,  # the field under test: genuinely missing from the doc
    inspection_date=date(2026, 4, 2),
    next_due=date(2027, 4, 2),
    inspector="D. Whitfield",
    result="FAIL",
    invoice_total=1001.53,
    defect_count=3,
)


def make_cache(tmp_path):
    return LLMCache(tmp_path / "llm_cache.jsonl")


def test_nothing_missing_makes_no_call(tmp_path):
    complete = FULL_RESULT.__class__(**{**FULL_RESULT.as_dict(), "capacity_lbs": 3500})
    calls = []

    def fake_caller(text, missing_fields):
        calls.append(missing_fields)
        raise AssertionError("should never be called when nothing is missing")

    outcome = resolve_missing_fields("irrelevant text", complete, make_cache(tmp_path), caller=fake_caller)

    assert outcome.called is False
    assert outcome.cost_usd == 0.0
    assert outcome.result == complete
    assert calls == []


def test_missing_field_triggers_one_call_and_merges_result(tmp_path):
    calls = []

    def fake_caller(text, missing_fields):
        calls.append(missing_fields)
        return LLMRawResponse(fields={"capacity_lbs": 4000}, input_tokens=500, output_tokens=20)

    outcome = resolve_missing_fields("doc text", FULL_RESULT, make_cache(tmp_path), caller=fake_caller)

    assert calls == [["capacity_lbs"]]
    assert outcome.called is True
    assert outcome.from_cache is False
    assert outcome.result.capacity_lbs == 4000
    assert outcome.fields_requested == ("capacity_lbs",)
    assert outcome.fields_filled == ("capacity_lbs",)


def test_cost_computed_from_actual_token_counts(tmp_path):
    def fake_caller(text, missing_fields):
        return LLMRawResponse(fields={"capacity_lbs": 4000}, input_tokens=1_000_000, output_tokens=1_000_000)

    outcome = resolve_missing_fields("doc text", FULL_RESULT, make_cache(tmp_path), caller=fake_caller)

    # 1M input tokens @ $5/MTok + 1M output tokens @ $25/MTok = $30.00
    assert outcome.cost_usd == 30.0


def test_model_confirming_absence_is_not_treated_as_a_failure(tmp_path):
    """The model returning null for a genuinely absent field is the correct
    answer -- capacity_lbs must still be None afterward, never fabricated."""

    def fake_caller(text, missing_fields):
        return LLMRawResponse(fields={"capacity_lbs": None}, input_tokens=500, output_tokens=15)

    outcome = resolve_missing_fields("doc text", FULL_RESULT, make_cache(tmp_path), caller=fake_caller)

    assert outcome.called is True
    assert outcome.result.capacity_lbs is None
    assert outcome.fields_filled == ()  # nothing was actually filled in
    assert outcome.cost_usd > 0  # the call still cost money even though it changed nothing


def test_second_call_with_same_input_hits_cache_and_makes_no_new_call(tmp_path):
    cache = make_cache(tmp_path)
    calls = []

    def fake_caller(text, missing_fields):
        calls.append(1)
        return LLMRawResponse(fields={"capacity_lbs": 4000}, input_tokens=500, output_tokens=20)

    first = resolve_missing_fields("doc text", FULL_RESULT, cache, caller=fake_caller)
    second = resolve_missing_fields("doc text", FULL_RESULT, cache, caller=fake_caller)

    assert len(calls) == 1  # the fake API was only ever hit once
    assert first.from_cache is False
    assert second.from_cache is True
    assert second.cost_usd == 0.0
    assert second.latency_seconds == 0.0
    assert second.result == first.result  # identical output on reprocessing


def test_different_missing_field_set_is_a_different_cache_key(tmp_path):
    """Same document text, different set of fields missing (e.g. after a
    parser change) must not collide with a previously cached answer."""
    cache = make_cache(tmp_path)
    calls = []

    def fake_caller(text, missing_fields):
        calls.append(tuple(missing_fields))
        return LLMRawResponse(fields={f: None for f in missing_fields}, input_tokens=10, output_tokens=5)

    partial = FULL_RESULT
    doubly_missing = FULL_RESULT.__class__(**{**FULL_RESULT.as_dict(), "inspector": None})

    resolve_missing_fields("doc text", partial, cache, caller=fake_caller)
    resolve_missing_fields("doc text", doubly_missing, cache, caller=fake_caller)

    assert len(calls) == 2
    assert calls[0] != calls[1]


def test_uncoercible_value_is_treated_as_missing_not_a_crash(tmp_path):
    def fake_caller(text, missing_fields):
        return LLMRawResponse(fields={"capacity_lbs": "not a number"}, input_tokens=10, output_tokens=5)

    outcome = resolve_missing_fields("doc text", FULL_RESULT, make_cache(tmp_path), caller=fake_caller)

    assert outcome.result.capacity_lbs is None
    assert outcome.fields_filled == ()


def test_date_field_is_coerced_from_iso_string(tmp_path):
    missing_date_result = FULL_RESULT.__class__(**{**FULL_RESULT.as_dict(), "next_due": None})

    def fake_caller(text, missing_fields):
        return LLMRawResponse(fields={"next_due": "2027-04-02"}, input_tokens=10, output_tokens=5)

    outcome = resolve_missing_fields(
        "doc text", missing_date_result, make_cache(tmp_path), caller=fake_caller
    )

    assert outcome.result.next_due == date(2027, 4, 2)
