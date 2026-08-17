# Project 2 — Document Extraction (Stage 1–4, plus the Layout C parser Stage 5 needs)

A scaffold for the project described in
[`PROJECT-2-document-extraction.md`](../meridian-portfolio/PROJECT-2-document-extraction.md)
in the sibling `meridian-portfolio` repo. Personal project built for skill
development against synthetic sample data — no production deployment, no
real users, no real inspection records.

**A deliberate scope boundary: Layout B has no parser, on purpose.** None
of the project's 5 named stages ever assign Layout B one — Stage 1 scopes
Layout A only, Stage 5 scopes Layout C only. Rather than silently drift
past that gap, it's documented here: Layout B is classified correctly
(Stage 2) and always routed to the review queue, every field reported
missing, never guessed. If a Layout B parser gets built later it's a
one-line addition to `router.py`'s `_PARSERS` registry — nothing else
changes.

**Built so far, deliberately in small stages:**

**Stage 1 — deterministic extraction (Layout A).**
- `pdfplumber` reads each PDF's text (`src/extraction/pdf_io.py`).
- A set of regexes pulls out the labeled fields (`src/extraction/layout_a.py`).
- Anything a regex doesn't match comes back as `None` — never a guessed
  value.

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
  the sidebar, see its PDF page rendered next to its extracted (or blank)
  field values, edit what needs correcting, and submit. Leaving a field
  blank and submitting logs an explicit "approved as missing," not a
  fabricated empty value.

**Prerequisite work for Stage 5, done ahead of the LLM fallback.**
Stage 5's own wording only makes sense with a deterministic Layout C
parser already in place — it says the LLM fills in "fields the
deterministic parser couldn't get," which presupposes a deterministic
parser doing most of the work already. So:
- `layout_c.py` — a regex parser for Layout C's two-column prose format,
  reaching 100% field accuracy. The one real bug hit building it: the
  preamble sentence's word-wrap point shifts depending on how long the
  inspector's name is (`"...as an\nauthorized inspector"` in most
  documents, `"...as an authorized\ninspector"` in two of them) — a regex
  assuming a fixed wrap point silently returned `None` for three fields
  on exactly those two documents. Fixed by using `\s+` at every join in
  the sentence instead of a literal space, so the match doesn't care
  where the line actually breaks. Covered by
  `test_parses_correctly_regardless_of_which_word_the_preamble_wraps_after`
  in `tests/test_layout_c.py`.
- `models.py` — `ExtractionResult`, one shared dataclass every parser
  returns, replacing the Layout-A-specific `LayoutAResult`. Keeps
  `router.py`, `confidence.py`, `validate.py`, and `review_queue.py`
  layout-agnostic: none of them need to know or care which parser
  produced a given result.
- `accuracy.py` generalized from a Layout-A-only scorer into a per-layout
  one, routing each document for real (via `router.route()`) rather than
  trusting the ground-truth layout column to pick a parser — a routing
  regression would show up as documents dropping out of scoring, not as
  silently wrong numbers. The `report-accuracy` command (renamed from
  `extract-layout-a`, since it's no longer Layout-A-specific) now prints
  a true per-layout, per-field breakdown.
- End-to-end determinism tests added in `tests/test_determinism.py`,
  covering the full pipeline (`route` → `validate_extraction` →
  `evaluate_document`), not just the Stage 1 parser in isolation. This
  was a gap identified before starting Stage 5: nothing tested that the
  whole system, not just one function, reprocesses a PDF identically —
  and Stage 5's LLM call is exactly the kind of thing that can quietly
  break that property if it isn't already pinned down by a test.

The LLM fallback itself is Stage 5, not built yet.

## Results

Per-layout, per-field accuracy against `GROUND_TRUTH.csv`, all 36 documents
(measured by `tests/test_accuracy.py`):

```
Documents scored: 24
Documents skipped (no parser for that layout): 12 (B=12)

Overall field accuracy (all scored layouts): 100.0%

Layout A - 12 documents, 100.0% overall
Layout C - 12 documents, 100.0% overall
```

Layout routing, all 36 documents (measured by `tests/test_routing_accuracy.py`):

```
Detected layout counts: A=12, B=12, C=12
Routing accuracy vs ground truth: 36/36 (100.0%)

No misrouted documents.
```

Schema validation, all 36 documents (measured by `tests/test_validation_corpus.py`):

```
Valid: 24  Invalid: 0  Skipped: 12
No documents flagged by schema validation.
```

The four Stage 3 rules are proven against mutated copies of a real
extraction in `tests/test_schema.py`, e.g.:

```
FAIL + 0 defects            -> False, "result is FAIL but defect_count is 0 -- contradictory..."
next_due == inspection_date -> False, "next_due (2026-01-13) must be later than inspection_date (2026-01-13)"
negative invoice_total      -> False, "Input should be greater than 0"
```

Review queue, all 36 documents (measured by `tests/test_review_queue.py`):

```
36 documents evaluated: 20 clean, 16 need review
```

- **20 clean**: 12 Layout A + 8 Layout C (the ones with `capacity_lbs`
  present) — fully populated, fully validated, every field at full
  confidence.
- **16 in the review queue**: 12 Layout B (no parser — the deliberate
  scope boundary above) + **4 Layout C documents, flagged specifically
  and only for their missing `capacity_lbs`** — the exact acceptance
  criterion the project doc is built around: *"Every missing-capacity
  document lands in the review queue; none receives a fabricated value."*
  Before the Layout C parser existed, this held only by accident (nothing
  in Layout C was extracted at all); now it holds for the right reason.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\pip install -e ".[dev]"

# to also run the Streamlit review UI:
.venv\Scripts\pip install -e ".[ui]"
```

## Run

```powershell
# per-layout, per-field accuracy report
.venv\Scripts\report-accuracy

# layout classification + routing report, all 36 documents
.venv\Scripts\route-documents

# schema validation report, all 36 documents
.venv\Scripts\validate-documents

# review queue report (who needs review and why)
.venv\Scripts\build-review-queue

# the review UI itself (requires the "ui" extra)
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
  models.py         # ExtractionResult: the one result type every parser returns
  layout_a.py       # regex extraction for Layout A
  layout_c.py       # regex extraction for Layout C (two-column prose)
  accuracy.py       # per-layout, per-field scoring against GROUND_TRUTH.csv
  cli.py            # entry point: report-accuracy
  layout_detect.py  # marker-based classify_layout(text) -> A/B/C/unknown/ambiguous
  router.py         # route(text) -> classification + parser result (or explicit "no parser")
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
  test_layout_a.py          # unit tests against synthetic Layout A text
  test_layout_c.py          # unit tests against synthetic Layout C text, incl. both wrap-point variants
  test_determinism.py       # same PDF in twice -> identical result out, Stage 1 through full pipeline
  test_accuracy.py          # end-to-end: 100% on both scored layouts, B correctly reported as skipped
  test_layout_detect.py     # unit tests: ok/unknown/ambiguous classification
  test_router.py            # unit tests: routing for A and C, "no parser" for B
  test_routing_accuracy.py  # end-to-end: 100% routing accuracy on all 36 real documents
  test_schema.py            # unit tests: every type/range/cross-field rule, both ways
  test_validate.py          # unit tests: validate_extraction wrapping + error surfacing
  test_validation_corpus.py # end-to-end: all 24 real A+C extractions pass validation
  test_confidence.py        # unit tests: binary per-field confidence
  test_audit_log.py         # unit tests: append/read, approve vs correct, per-file filtering
  test_review_queue.py      # unit tests + end-to-end: 20 clean / 16 review on the real corpus
  test_review_app.py        # Streamlit AppTest: loads, lists queue, submits, writes audit log
sample-data/inspection-certs/   # 36 PDFs + GROUND_TRUTH.csv (copied in so
                                 # this repo is self-contained; source of
                                 # truth is meridian-portfolio/sample-data)
var/                             # gitignored: audit_log.jsonl lives here once the UI is used
```

## Design notes for Stage 5

- `ExtractionResult` (`models.py`) field names match `GROUND_TRUTH.csv`
  columns 1:1 so scoring stays a plain per-field `==`, regardless of which
  layout's parser produced the result.
- Both parsers take a `str`, not a file path — deterministic and trivially
  testable without touching a PDF. `pdf_io.extract_text` is the only thing
  that touches pdfplumber.
- `route()` deliberately returns `result=None` for anything not cleanly
  routed to a working parser (unknown layout, ambiguous marker match, or a
  layout with no parser — currently just B), all exposed as
  `routed.misrouted`.
- `_PARSERS` in `router.py` is the only place that needs to change when a
  new layout gets a parser — routing, classification, scoring, and
  reporting all pick it up automatically.
- `ValidationOutcome.valid`, `routed.misrouted`, and per-field confidence
  are the three inputs `review_queue.evaluate_document` combines into one
  `needs_review` decision. **Stage 5 should only need to change what
  `field_confidences` returns** (fractional instead of binary, for
  whichever fields the LLM fills in) — not how the review queue, schema
  validation, or reporting consume it.
- `record_review` logs every field the reviewer saw, not just the ones
  they changed — a blank field left blank still gets an `approve` entry
  (`old_value=None, new_value=None`), which is what makes "this document
  was reviewed and nothing was fabricated" independently verifiable from
  the log later.
- The wrap-point bug in `layout_c.py` is the concrete argument for why
  Stage 5's LLM fallback should only run on fields the deterministic
  parser actually left `None` — not on every Layout C field — since the
  deterministic parser, once fixed, is both cheaper and now proven at
  100% on the real corpus.
