# Project 2 — Document Extraction (Stage 1: Layout A)

A scaffold for the project described in
[`PROJECT-2-document-extraction.md`](../meridian-portfolio/PROJECT-2-document-extraction.md)
in the sibling `meridian-portfolio` repo. Personal project built for skill
development against synthetic sample data — no production deployment, no
real users, no real inspection records.

**This is Stage 1 of 5, built deliberately alone.** It does deterministic
extraction for Layout A only:

- `pdfplumber` reads each PDF's text (`src/extraction/pdf_io.py`).
- A set of regexes pulls out the labeled fields (`src/extraction/layout_a.py`).
- Anything a regex doesn't match comes back as `None` — never a guessed
  value. There's no fallback and nothing to fall back to yet.
- An accuracy report (`src/extraction/accuracy.py`) scores every Layout A
  document against `GROUND_TRUTH.csv`, field by field.

Layout B (table-style) and Layout C (two-column prose, missing capacity
fields) are **not handled yet**. The accuracy report counts them and reports
them as skipped rather than running Layout A's parser on them and reporting
misleading zeroes — that routing decision is Stage 2. Schema validation,
confidence scoring, the review queue, and the LLM fallback are Stages 3–5.

## Result

```
Layout A documents scored: 12
Documents skipped (not Layout A, no parser yet): 24

Overall field accuracy: 100.0%
```

100% field-level accuracy across all 13 fields on all 12 Layout A documents,
measured by `tests/test_accuracy.py` against `GROUND_TRUTH.csv` — not
asserted.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\pip install -e ".[dev]"
```

## Run

```powershell
# accuracy report against the bundled sample corpus
.venv\Scripts\extract-layout-a

# or point it at a different corpus with the same GROUND_TRUTH.csv shape
.venv\Scripts\python -m extraction.cli path\to\other\sample-data

# tests
.venv\Scripts\pytest -q
```

## Layout

```
src/extraction/
  pdf_io.py     # pdfplumber wrapper: PDF -> text
  layout_a.py   # regex extraction for Layout A + LayoutAResult dataclass
  accuracy.py   # scores extraction against GROUND_TRUTH.csv
  cli.py        # entry point: extract-layout-a
tests/
  test_layout_a.py     # unit tests against synthetic label/value text
  test_determinism.py  # same PDF in twice -> identical result out
  test_accuracy.py     # end-to-end: 100% on the real sample corpus
sample-data/inspection-certs/   # 36 PDFs + GROUND_TRUTH.csv (copied in so
                                 # this repo is self-contained; source of
                                 # truth is meridian-portfolio/sample-data)
```

## Design notes for later stages

- `is_layout_a()` is a cheap marker check, not real layout detection —
  Stage 2 will replace how documents get routed here, not how this module
  parses once routed.
- `LayoutAResult` field names match `GROUND_TRUTH.csv` columns 1:1 so
  scoring stays a plain per-field `==`. Stage 3's Pydantic model should
  probably reuse these names for the same reason.
- `parse_layout_a` takes a `str`, not a file path — deterministic and
  trivially testable without touching a PDF. `pdf_io.extract_text` is the
  only thing that touches pdfplumber.
