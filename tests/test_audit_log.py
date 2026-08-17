from extraction.audit_log import AuditLog, record_review


def test_append_and_read_round_trips(tmp_path):
    log = AuditLog(tmp_path / "audit_log.jsonl")
    record_review(
        log,
        reviewer="jane.doe",
        file="MES-2026-4102.pdf",
        old_values={"capacity_lbs": None, "cert_no": "MES-2026-4102"},
        new_values={"capacity_lbs": 3500, "cert_no": "MES-2026-4102"},
    )

    entries = log.read_all()
    assert len(entries) == 2

    by_field = {e.field: e for e in entries}
    assert by_field["capacity_lbs"].action == "correct"
    assert by_field["capacity_lbs"].old_value is None
    assert by_field["capacity_lbs"].new_value == "3500"
    assert by_field["cert_no"].action == "approve"
    assert by_field["cert_no"].old_value == by_field["cert_no"].new_value == "MES-2026-4102"

    for entry in entries:
        assert entry.reviewer == "jane.doe"
        assert entry.file == "MES-2026-4102.pdf"
        assert entry.timestamp  # non-empty


def test_log_is_append_only_across_multiple_reviews(tmp_path):
    log = AuditLog(tmp_path / "audit_log.jsonl")
    record_review(log, reviewer="a", file="doc.pdf", old_values={"x": "1"}, new_values={"x": "1"})
    record_review(log, reviewer="b", file="doc.pdf", old_values={"x": "1"}, new_values={"x": "2"})

    entries = log.entries_for_file("doc.pdf")
    assert len(entries) == 2
    assert entries[0].reviewer == "a" and entries[0].action == "approve"
    assert entries[1].reviewer == "b" and entries[1].action == "correct"
    assert entries[1].old_value == "1"
    assert entries[1].new_value == "2"


def test_entries_for_file_filters_correctly(tmp_path):
    log = AuditLog(tmp_path / "audit_log.jsonl")
    record_review(log, reviewer="a", file="doc1.pdf", old_values={"x": "1"}, new_values={"x": "1"})
    record_review(log, reviewer="a", file="doc2.pdf", old_values={"x": "1"}, new_values={"x": "1"})

    assert len(log.entries_for_file("doc1.pdf")) == 1
    assert len(log.entries_for_file("doc2.pdf")) == 1
    assert len(log.read_all()) == 2


def test_read_all_on_missing_file_returns_empty(tmp_path):
    log = AuditLog(tmp_path / "does-not-exist.jsonl")
    assert log.read_all() == []
