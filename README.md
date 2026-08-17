# Project 2 — Document Extraction (Stage 1–4: extraction, routing, validation, review queue)

A scaffold for the project described in
[`PROJECT-2-document-extraction.md`](../meridian-portfolio/PROJECT-2-document-extraction.md)
in the sibling `meridian-portfolio` repo. Personal project built for skill
development against synthetic sample data — no production deployment, no
real users, no real inspection records.

**Built so far, deliberately in small stages:**

**Stage 1 — deterministic extraction (Layout A only).**
- `pdfplumber` reads each PDF's text (`src/extraction/pdf_io.py`).
- A set of regexes pulls out the labeled fields (`src/extraction/layout_a.py`).
- Anything a regex doesn't match comes back as `None` — never a guessed
  value. There's no fallback and nothing to fall back to yet.
- An accuracy report (`src/extraction/accuracy.py`) scores every Layout A
  document against `GROUND_TRUTH.csv`, field by field.

**Stage 2 — layout detection and routing.**
- Each of the three layouts has one boilerplate text marker
  (`src/extraction/layout_detect.py`) — verified unique across the full
  36-document corpus: every document matches exactly one marker, never
  zero, never more than one.
- A document is only routed to a parser when classification is
  unambiguous *and* a parser exists for that layout
  (`src/extraction/router.py`). Zero-match (`unknown`) and multi-match
  (`ambiguous`) are distinct, reported outcomes, not silently resolved by
  picking the "closest" layout.
- Only Layout A has a parser. Layout B/C route correctly but come back
  with an explicit "no parser implemented yet" note and `result=None` —
  never a silent empty extraction that looks like success.
- A routing report (`src/extraction/routing_report.py`) prints every
  document's detected layout next to ground truth and calls out any
  misrouted document by name in its own section.

**Stage 3 — Pydantic schema validation.**
- `InspectionCertificate` (`src/extraction/schema.py`) is the Pydantic
  model every extracted document must satisfy: types (a real `date`, not a
  date-shaped string; `result` restricted to the three known enum values),
  ranges (`invoice_total` and `capacity_lbs` must be positive,
  `defect_count` can't be negative), and two cross-field rules —
  `next_due` must be later than `inspection_date`, and a `FAIL` result
  with zero defects listed is rejected as contradictory.
- `capacity_lbs` is the one field allowed to be `None` — a few Layout C
  documents omit it entirely, and that's a legitimate "missing," not an
  invalid document. Every other field being `None` (a parser miss) fails
  validation rather than passing a hole in the data downstream.
- `validate.py` wraps model construction so a validation failure is a
  reported outcome (`ValidationOutcome.valid`, `.errors`), not an
  exception that stops the run.
- A validation report (`src/extraction/validation_report.py`) routes and
  validates every document, prints per-document status, and lists any
  flagged document's exact errors in its own section.

**Stage 4 — confidence scoring and a review queue.**
- `confidence.py`: for deterministic regex extraction, confidence is
  honestly binary — 1.0 for a field the parser found, 0.0 for one it
  didn't. There's no gradient to hedge with; a real fractional confidence
  arrives with Stage 5's LLM fallback.
- `review_queue.py`: a document is flagged for review if it was misrouted
  (Stage 2), any field is below the confidence threshold — including any
  field that's simply missing — or the extraction fails schema validation
  (Stage 3). Everything not flagged is "clean." `build-review-queue`
  prints the queue and the reasons behind every flagged document.
- `audit_log.py`: an append-only JSONL log (`var/audit_log.jsonl` by
  default, overridable via `EXTRACTION_AUDIT_LOG_PATH`). Every review
  decision — approve or correct — is one line: reviewer, timestamp,
  document, field, old value, new value. Corrections add lines; nothing is
  ever overwritten.
- `app/review_app.py`: a small Streamlit UI. Pick a queued document from
  the sidebar, see its PDF page rendered next to its extracted (or blank,
  if there's no parser yet) field values, edit what needs correcting, and
  submit. Leaving a field blank and submitting logs an explicit "approved
  as missing," not a fabricated empty value.

The LLM fallback is Stage 5, not built yet.

## Results

Stage 1 — Layout A field extraction:

```
Layout A documents scored: 12
Documents skipped (not Layout A, no parser yet): 24

Overall field accuracy: 100.0%
```

100% field-level accuracy across all 13 fields on all 12 Layout A documents,
measured by `tests/test_accuracy.py` against `GROUND_TRUTH.csv` — not
asserted.

Stage 2 — layout routing, all 36 documents:

```
Detected layout counts: A=12, B=12, C=12
Routing accuracy vs ground truth: 36/36 (100.0%)

No misrouted documents.
```

100% routing accuracy, measured by `tests/test_routing_accuracy.py`. Layout
B and C documents route correctly but carry `result=None` since no parser
exists for them yet — routing accuracy is not the same claim as extraction
accuracy.

Stage 3 — schema validation, all 36 documents:

```
Valid: 12  Invalid: 0  Skipped: 24
No documents flagged by schema validation.
```

All 12 real Layout A extractions pass validation cleanly (measured by
`tests/test_validation_corpus.py`) — the sample corpus has no planted
contradictions. The four required rules are proven against mutated copies
of a real extraction in `tests/test_schema.py`, e.g.:

```
FAIL + 0 defects        -> False, "result is FAIL but defect_count is 0 -- contradictory..."
next_due == inspection_date -> False, "next_due (2026-01-13) must be later than inspection_date (2026-01-13)"
negative invoice_total  -> False, "Input should be greater than 0"
```

Stage 4 — review queue, all 36 documents:

```
36 documents evaluated: 12 clean, 24 need review
```

The 12 clean documents are the 12 Layout A extractions: fully populated,
fully validated, every field at full confidence. All 24 Layout B/C
documents land in the queue — no parser exists for them yet, so every
field is reported missing rather than guessed. Measured by
`tests/test_review_queue.py`.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\pip install -e ".[dev]"

# to also run the Streamlit review UI:
.venv\Scripts\pip install -e ".[ui]"
```

## Run

```powershell
# Stage 1: Layout A field-accuracy report
.venv\Scripts\extract-layout-a

# Stage 2: layout classification + routing report, all 36 documents
.venv\Scripts\route-documents

# Stage 3: schema validation report, all 36 documents
.venv\Scripts\validate-documents

# Stage 4: review queue report (who needs review and why)
.venv\Scripts\build-review-queue

# Stage 4: the review UI itself (requires the "ui" extra)
.venv\Scripts\streamlit run app\review_app.py

# any report command can point at a different corpus with the same GROUND_TRUTH.csv shape
.venv\Scripts\python -m extraction.cli path\to\other\sample-data
.venv\Scripts\python -m extraction.routing_report path\to\other\sample-data
.venv\Scripts\python -m extraction.validation_report path\to\other\sample-data
.venv\Scripts\python -m extraction.review_queue path\to\other\sample-data

# tests (Streamlit UI tests are skipped automatically if the "ui" extra isn't installed)
.venv\Scripts\pytest -q
```

## Layout

```
src/extraction/
  pdf_io.py         # pdfplumber wrapper: PDF -> text
  layout_a.py       # regex extraction for Layout A + LayoutAResult dataclass
  accuracy.py       # scores Layout A extraction against GROUND_TRUTH.csv
  cli.py            # entry point: extract-layout-a
  layout_detect.py  # marker-based classify_layout(text) -> A/B/C/unknown/ambiguous
  router.py         # route(text) -> classification + parser result (or explicit "no parser yet")
  routing_report.py # entry point: route-documents
  schema.py          # InspectionCertificate Pydantic model: types, ranges, cross-field rules
  validate.py         # validate_extraction(result) -> ValidationOutcome, never raises
  validation_report.py # entry point: validate-documents
  confidence.py        # field_confidences(result) -> per-field 0.0/1.0
  audit_log.py          # append-only JSONL log of review decisions
  review_queue.py        # combines routing + confidence + validation -> QueueItem list; entry point: build-review-queue
app/
  review_app.py          # Streamlit review UI: streamlit run app/review_app.py
tests/
  test_layout_a.py         # unit tests against synthetic label/value text
  test_determinism.py      # same PDF in twice -> identical result out
  test_accuracy.py         # end-to-end: 100% Layout A field accuracy on the real corpus
  test_layout_detect.py    # unit tests: ok/unknown/ambiguous classification
  test_router.py           # unit tests: routing + "no parser yet" for B/C
  test_routing_accuracy.py # end-to-end: 100% routing accuracy on all 36 real documents
  test_schema.py            # unit tests: every type/range/cross-field rule, both ways
  test_validate.py          # unit tests: validate_extraction wrapping + error surfacing
  test_validation_corpus.py # end-to-end: all 12 real Layout A extractions pass validation
  test_confidence.py         # unit tests: binary per-field confidence
  test_audit_log.py           # unit tests: append/read, approve vs correct, per-file filtering
  test_review_queue.py         # unit tests + end-to-end: 12 clean / 24 review on the real corpus
  test_review_app.py            # Streamlit AppTest: loads, lists queue, submits, writes audit log
sample-data/inspection-certs/   # 36 PDFs + GROUND_TRUTH.csv (copied in so
                                 # this repo is self-contained; source of
                                 # truth is meridian-portfolio/sample-data)
var/                             # gitignored: audit_log.jsonl lives here once the UI is used
```

## Design notes for later stages

- `LayoutAResult` field names match `GROUND_TRUTH.csv` columns 1:1 so
  scoring stays a plain per-field `==`. Stage 3's Pydantic model should
  probably reuse these names for the same reason.
- `parse_layout_a` takes a `str`, not a file path — deterministic and
  trivially testable without touching a PDF. `pdf_io.extract_text` is the
  only thing that touches pdfplumber.
- `route()` deliberately returns `result=None` for anything not cleanly
  routed to a working parser (unknown layout, ambiguous marker match, or a
  layout with no parser yet), all exposed as `routed.misrouted`. Stage 3's
  confidence/review-queue logic can treat "misrouted" as an automatic
  review-queue trigger without re-deriving what counts as suspicious.
- `_PARSERS` in `router.py` is the only place that needs to change when
  Layout B/C get parsers — routing, classification, and reporting don't.
- `ValidationOutcome.valid`, `routed.misrouted`, and per-field confidence
  are the three inputs `review_queue.evaluate_document` combines into one
  `needs_review` decision — Stage 5's LLM fallback only needs to change
  what `field_confidences` returns (fractional instead of binary), not
  how the review queue consumes it.
- `record_review` logs every field the reviewer saw, not just the ones
  they changed — a blank field left blank still gets an `approve` entry
  (`old_value=None, new_value=None`), which is what makes "this document
  was reviewed and nothing was fabricated" independently verifiable from
  the log later.
