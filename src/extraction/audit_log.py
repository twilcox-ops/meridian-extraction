"""Stage 4 — append-only audit log for review decisions.

Every review action is one JSON line: who made the decision, when, which
document and field, and the old/new value. The log is append-only by
design — a correction adds a new line, it never rewrites or deletes a
previous one, so "what did this field say before the human touched it" is
always answerable from the log itself.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

_AUDIT_LOG_PATH_ENV = "EXTRACTION_AUDIT_LOG_PATH"
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def default_audit_log_path() -> Path:
    """Resolved fresh on every call (not cached at import time) so
    EXTRACTION_AUDIT_LOG_PATH can be overridden per-run — the review UI
    picks this up on every script execution, and tests rely on it to
    redirect writes away from the real log."""
    override = os.environ.get(_AUDIT_LOG_PATH_ENV)
    return Path(override) if override else _PROJECT_ROOT / "var" / "audit_log.jsonl"

Action = Literal["approve", "correct"]


@dataclass(frozen=True)
class AuditLogEntry:
    timestamp: str  # ISO 8601, UTC
    reviewer: str
    file: str
    field: str
    action: Action
    old_value: str | None
    new_value: str | None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AuditLog:
    """Thin wrapper over a JSONL file. One `AuditLog` per log file."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path is not None else default_audit_log_path()

    def append(self, entry: AuditLogEntry) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(entry)) + "\n")

    def read_all(self) -> list[AuditLogEntry]:
        if not self.path.exists():
            return []
        entries = []
        with self.path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(AuditLogEntry(**json.loads(line)))
        return entries

    def entries_for_file(self, file: str) -> list[AuditLogEntry]:
        return [e for e in self.read_all() if e.file == file]


def _stringify(value: object) -> str | None:
    return None if value is None else str(value)


def record_review(
    log: AuditLog,
    *,
    reviewer: str,
    file: str,
    old_values: dict[str, object],
    new_values: dict[str, object],
) -> list[AuditLogEntry]:
    """Log one entry per field in `new_values`, comparing each against the
    extracted value it started from. A field whose value didn't change is
    logged as `approve`; a field whose value changed (including a missing
    field that got filled in) is logged as `correct`. Every field the
    reviewer looked at gets an entry, at the same timestamp, so a
    document's review shows up as one batch in the log.
    """
    timestamp = now_iso()
    entries = []
    for field, new_value in new_values.items():
        old_value = old_values.get(field)
        old_str, new_str = _stringify(old_value), _stringify(new_value)
        action: Action = "approve" if old_str == new_str else "correct"
        entry = AuditLogEntry(
            timestamp=timestamp,
            reviewer=reviewer,
            file=file,
            field=field,
            action=action,
            old_value=old_str,
            new_value=new_str,
        )
        log.append(entry)
        entries.append(entry)
    return entries
