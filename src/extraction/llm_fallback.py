"""Stage 5 — LLM fallback, measured.

Scope, exactly as the project brief states it: Layout C only, and only for
fields the deterministic parser (`layout_c.py`) left as `None`. In practice
that means one field, `capacity_lbs`, on the handful of documents where the
source PDF genuinely omits it — every other Layout C field already reaches
100% accuracy without a model call (see `accuracy.py`), so there is nothing
else for the LLM to do. The fallback is not the primary Layout C extractor;
it is a narrow patch applied after the deterministic parser has already done
everything it can.

The instruction to the model is as important as the schema: return `null`
for a field that is not actually present in the document text. A model that
invents a plausible capacity number is worse than the deterministic parser
returning `None`, because nobody would find out. This module treats an
LLM-returned `null` as a legitimate answer, not a failed call.

Determinism, per the acceptance criterion ("reprocessing the same PDF twice
produces identical output"): `temperature` is not an available lever here —
Claude Opus 5 rejects non-default sampling parameters outright (see the
model's migration notes; the parameter 400s if sent). Instead, every real
API response is cached by a hash of (model, prompt version, requested
fields, document text). A rerun against the same document hits the cache
and never calls the API again — which is a stronger determinism guarantee
than `temperature=0` ever was anyway, and has the side effect of making
reprocessing free after the first run.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable, Literal

from extraction.models import FIELD_NAMES, ExtractionResult

MODEL = "claude-opus-5"

# Claude Opus 5 list pricing, $ per million tokens (see the claude-api skill's
# cached model table). Cost is reported per document, per the acceptance
# criterion -- not estimated from a flat per-call assumption.
INPUT_PRICE_PER_MTOK = 5.00
OUTPUT_PRICE_PER_MTOK = 25.00

# Bumping this invalidates every cached response -- change it whenever the
# prompt or schema changes, so stale answers from a different prompt version
# are never silently reused.
PROMPT_VERSION = "v1"

_JSON_TYPE_FOR_FIELD: dict[str, dict[str, object]] = {
    "cert_no": {"type": ["string", "null"]},
    "unit_id": {"type": ["string", "null"]},
    "building": {"type": ["string", "null"]},
    "city": {"type": ["string", "null"]},
    "state": {"type": ["string", "null"]},
    "unit_type": {"type": ["string", "null"]},
    "capacity_lbs": {"type": ["integer", "null"]},
    "inspection_date": {"type": ["string", "null"], "format": "date"},
    "next_due": {"type": ["string", "null"], "format": "date"},
    "inspector": {"type": ["string", "null"]},
    "result": {"type": ["string", "null"]},
    "invoice_total": {"type": ["number", "null"]},
    "defect_count": {"type": ["integer", "null"]},
}

_SYSTEM_PROMPT = (
    "You extract specific fields from an elevator inspection certificate. "
    "You will be told exactly which fields to extract. For each one, search "
    "the document text carefully. If a field's value is genuinely not "
    "present anywhere in the document -- not stated, not implied, not "
    "computable from other stated values -- return null for it. Never "
    "guess, estimate, or infer a plausible value. Returning null for an "
    "absent field is the correct answer, not a failure."
)


def _build_schema(missing_fields: list[str]) -> dict[str, object]:
    return {
        "type": "object",
        "properties": {name: _JSON_TYPE_FOR_FIELD[name] for name in missing_fields},
        "required": missing_fields,
        "additionalProperties": False,
    }


@dataclass(frozen=True)
class LLMRawResponse:
    """What one real API call returns, before field-type coercion."""

    fields: dict[str, object]  # raw JSON values: str | int | float | None
    input_tokens: int
    output_tokens: int


def _call_claude(text: str, missing_fields: list[str]) -> LLMRawResponse:
    """The real API call. Isolated behind this function so tests can inject
    a fake caller instead of hitting the network on every run."""
    import anthropic
    from dotenv import load_dotenv

    load_dotenv()  # reads ANTHROPIC_API_KEY from .env into the environment
    client = anthropic.Anthropic()  # picks up ANTHROPIC_API_KEY automatically

    schema = _build_schema(missing_fields)
    field_list = ", ".join(missing_fields)
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Extract exactly these fields: {field_list}\n\n"
                    f"Document text:\n{text}"
                ),
            }
        ],
        output_config={"format": {"type": "json_schema", "schema": schema}},
    )
    text_block = next(b for b in response.content if b.type == "text")
    fields = json.loads(text_block.text)
    return LLMRawResponse(
        fields=fields,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )


CallerFn = Callable[[str, list[str]], LLMRawResponse]


def _compute_cost(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens / 1_000_000) * INPUT_PRICE_PER_MTOK + (
        output_tokens / 1_000_000
    ) * OUTPUT_PRICE_PER_MTOK


def _coerce_field(name: str, value: object) -> object:
    """Convert one raw JSON value into the type `ExtractionResult` expects.
    A value the model couldn't parse into that type is treated as missing
    (None) rather than raising -- consistent with the rest of the pipeline's
    "never fabricate, always flag" rule."""
    if value is None:
        return None
    try:
        if name in ("capacity_lbs", "defect_count"):
            return int(value)
        if name == "invoice_total":
            return float(value)
        if name in ("inspection_date", "next_due"):
            return date.fromisoformat(str(value))
        return str(value)
    except (ValueError, TypeError):
        return None


def _merge(result: ExtractionResult, coerced_fields: dict[str, object]) -> ExtractionResult:
    updates = {name: value for name, value in coerced_fields.items() if value is not None}
    return dataclasses.replace(result, **updates) if updates else result


# --- Cache -------------------------------------------------------------

_LLM_CACHE_PATH_ENV = "EXTRACTION_LLM_CACHE_PATH"
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def default_llm_cache_path() -> Path:
    """Resolved fresh on every call (not cached at import time) so the env
    override works reliably and tests can redirect it -- same reasoning as
    `audit_log.default_audit_log_path`."""
    override = os.environ.get(_LLM_CACHE_PATH_ENV)
    return Path(override) if override else _PROJECT_ROOT / "var" / "llm_cache.jsonl"


def _cache_key(text: str, missing_fields: list[str]) -> str:
    payload = json.dumps(
        {
            "model": MODEL,
            "prompt_version": PROMPT_VERSION,
            "missing_fields": sorted(missing_fields),
            "text": text,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class LLMCacheEntry:
    key: str
    fields: dict[str, object]
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_seconds: float


class LLMCache:
    """Append-only JSONL cache, one entry per unique (model, prompt version,
    fields requested, document text). A cache hit means zero new API calls
    and zero new cost -- and is what makes reprocessing the same document
    produce identical output without ever touching the network again."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path is not None else default_llm_cache_path()

    def get(self, key: str) -> LLMCacheEntry | None:
        if not self.path.exists():
            return None
        with self.path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                if entry["key"] == key:
                    return LLMCacheEntry(**entry)
        return None

    def put(self, entry: LLMCacheEntry) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(dataclasses.asdict(entry)) + "\n")


# --- Orchestration -------------------------------------------------------


@dataclass(frozen=True)
class LLMFallbackOutcome:
    result: ExtractionResult
    called: bool  # False when there was nothing missing to ask about
    from_cache: bool
    cost_usd: float  # 0.0 when called=False or from_cache=True
    latency_seconds: float  # 0.0 when called=False or from_cache=True
    fields_requested: tuple[str, ...]
    fields_filled: tuple[str, ...]  # subset of fields_requested the model actually filled in


def resolve_missing_fields(
    text: str,
    result: ExtractionResult,
    cache: LLMCache,
    caller: CallerFn = _call_claude,
) -> LLMFallbackOutcome:
    """Fill in whatever fields `result` is missing, using the LLM fallback.

    Only ever asks about fields that are actually `None` -- this is the
    "only for fields the deterministic parser couldn't get" constraint,
    enforced here rather than left to caller discipline.
    """
    missing = [name for name in FIELD_NAMES if getattr(result, name) is None]
    if not missing:
        return LLMFallbackOutcome(
            result=result,
            called=False,
            from_cache=False,
            cost_usd=0.0,
            latency_seconds=0.0,
            fields_requested=(),
            fields_filled=(),
        )

    key = _cache_key(text, missing)
    cached = cache.get(key)
    if cached is not None:
        coerced = {name: _coerce_field(name, v) for name, v in cached.fields.items()}
        merged = _merge(result, coerced)
        filled = tuple(name for name, v in coerced.items() if v is not None)
        return LLMFallbackOutcome(
            result=merged,
            called=True,
            from_cache=True,
            cost_usd=0.0,
            latency_seconds=0.0,
            fields_requested=tuple(missing),
            fields_filled=filled,
        )

    start = time.monotonic()
    raw = caller(text, missing)
    latency = time.monotonic() - start
    cost = _compute_cost(raw.input_tokens, raw.output_tokens)

    cache.put(
        LLMCacheEntry(
            key=key,
            fields=raw.fields,
            input_tokens=raw.input_tokens,
            output_tokens=raw.output_tokens,
            cost_usd=cost,
            latency_seconds=latency,
        )
    )

    coerced = {name: _coerce_field(name, v) for name, v in raw.fields.items()}
    merged = _merge(result, coerced)
    filled = tuple(name for name, v in coerced.items() if v is not None)
    return LLMFallbackOutcome(
        result=merged,
        called=True,
        from_cache=False,
        cost_usd=cost,
        latency_seconds=latency,
        fields_requested=tuple(missing),
        fields_filled=filled,
    )
