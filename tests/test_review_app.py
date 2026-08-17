"""Exercises the Streamlit review UI itself, using Streamlit's AppTest
harness (runs the script for real, headlessly, no browser). Requires the
`ui` extra; skipped otherwise since it's not part of the core pipeline.
"""

from pathlib import Path

import pytest

st_testing = pytest.importorskip("streamlit.testing.v1")

APP_PATH = str(Path(__file__).resolve().parents[1] / "app" / "review_app.py")


@pytest.fixture
def audit_log_path(tmp_path, monkeypatch):
    path = tmp_path / "audit_log.jsonl"
    monkeypatch.setenv("EXTRACTION_AUDIT_LOG_PATH", str(path))
    return path


def test_app_loads_without_exceptions(audit_log_path):
    at = st_testing.AppTest.from_file(APP_PATH, default_timeout=60)
    at.run()
    assert not at.exception


def test_review_queue_documents_are_listed(audit_log_path):
    at = st_testing.AppTest.from_file(APP_PATH, default_timeout=60)
    at.run()
    # 16 of the 36 sample documents need review: 12 Layout B (no parser) +
    # 4 Layout C (capacity_lbs missing)
    assert len(at.sidebar.radio[0].options) == 16


def test_submitting_a_review_writes_the_audit_log(audit_log_path):
    from extraction.audit_log import AuditLog

    at = st_testing.AppTest.from_file(APP_PATH, default_timeout=60)
    at.run()

    at.sidebar.text_input[1].set_value("jane.doe").run()  # reviewer name
    at.text_input[0].set_value("MES-2026-4101").run()  # correct the first field
    at.button[0].click().run()
    assert not at.exception

    log = AuditLog(audit_log_path)
    entries = log.read_all()
    assert len(entries) == 13  # one entry per schema field

    corrected = [e for e in entries if e.action == "correct"]
    assert len(corrected) == 1
    assert corrected[0].new_value == "MES-2026-4101"
    assert corrected[0].reviewer == "jane.doe"

    untouched = [e for e in entries if e.field != corrected[0].field]
    assert all(e.action == "approve" and e.old_value is None and e.new_value is None for e in untouched)


def test_reviewing_without_a_reviewer_name_does_not_write_the_log(audit_log_path):
    at = st_testing.AppTest.from_file(APP_PATH, default_timeout=60)
    at.run()
    # No reviewer name set -> submit button must be disabled
    assert at.button[0].disabled
    assert not audit_log_path.exists()
