"""Stage 4 — review queue UI.

Pick a document from the review queue, see the PDF page next to its
extracted (or missing) field values, and approve or correct each field.
Submitting writes one audit log entry per field to `var/audit_log.jsonl`
— who, what, when, old value, new value.

Run with:
    streamlit run app/review_app.py
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pdfplumber
import streamlit as st

# This file lives outside the installed `extraction` package (it's a UI
# entry point, not a library module), so make sure src/ is importable
# regardless of the working directory Streamlit was launched from.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from extraction.audit_log import AuditLog, record_review  # noqa: E402
from extraction.review_queue import DEFAULT_SAMPLE_DATA, QueueItem, build_queue  # noqa: E402

st.set_page_config(page_title="Inspection Certificate Review Queue", layout="wide")


@st.cache_data(show_spinner="Evaluating documents...")
def load_queue(sample_data_dir: str) -> list[QueueItem]:
    return build_queue(Path(sample_data_dir))


@st.cache_data(show_spinner=False)
def render_page_png(pdf_path: str, page_number: int) -> bytes:
    with pdfplumber.open(pdf_path) as pdf:
        image = pdf.pages[page_number].to_image(resolution=150)
        buf = io.BytesIO()
        image.original.save(buf, format="PNG")
        return buf.getvalue()


def main() -> None:
    st.title("Inspection Certificate Review Queue")

    sample_data_dir = st.sidebar.text_input("Sample data directory", str(DEFAULT_SAMPLE_DATA))
    reviewer = st.sidebar.text_input("Reviewer name")

    items = load_queue(sample_data_dir)
    review_items = [i for i in items if i.needs_review]
    clean_items = [i for i in items if not i.needs_review]

    st.sidebar.metric("Documents", len(items))
    st.sidebar.metric("Clean (skipped here)", len(clean_items))
    st.sidebar.metric("Needs review", len(review_items))

    if not review_items:
        st.success("Review queue is empty - every document extracted cleanly and passed validation.")
        return

    log = AuditLog()  # resolves EXTRACTION_AUDIT_LOG_PATH (if set) fresh on every run
    reviewed_files = {e.file for e in log.read_all()}

    labels = [
        f"{'reviewed' if item.file in reviewed_files else 'pending'} - {item.file} ({item.layout or 'unknown'})"
        for item in review_items
    ]
    selected_idx = st.sidebar.radio(
        "Document", range(len(review_items)), format_func=lambda i: labels[i]
    )
    item = review_items[selected_idx]

    col_pdf, col_fields = st.columns([1, 1])

    with col_pdf:
        st.subheader(item.file)
        pdf_path = str(Path(sample_data_dir) / item.file)
        st.image(render_page_png(pdf_path, 0), width="stretch")

    with col_fields:
        st.subheader("Extracted values")
        st.caption(f"Layout: {item.layout or 'unknown'} - {item.routing_note}")
        if item.reasons:
            st.error("Flagged for review:\n" + "\n".join(f"- {r}" for r in item.reasons))
        if not reviewer:
            st.warning("Enter a reviewer name in the sidebar before submitting a review.")

        with st.form(key=f"review-form-{item.file}"):
            raw_inputs: dict[str, str] = {}
            for field in item.values:
                current = item.values[field]
                confidence = item.confidences[field]
                label = f"{field}  (confidence {confidence:.0%})"
                raw_inputs[field] = st.text_input(
                    label,
                    value="" if current is None else str(current),
                    key=f"{item.file}-{field}",
                )
            submitted = st.form_submit_button("Submit review", disabled=not reviewer)

        if submitted:
            # A blank input means "still missing, reviewer confirmed it" --
            # logged as approving the missing value, not inventing an
            # empty-string value in its place.
            new_values = {field: (raw.strip() or None) for field, raw in raw_inputs.items()}
            old_values = {k: (None if v is None else str(v)) for k, v in item.values.items()}
            entries = record_review(
                log, reviewer=reviewer, file=item.file, old_values=old_values, new_values=new_values
            )
            approved = sum(1 for e in entries if e.action == "approve")
            corrected = sum(1 for e in entries if e.action == "correct")
            st.success(
                f"Logged {len(entries)} field decisions for {item.file}: "
                f"{approved} approved, {corrected} corrected."
            )
            st.rerun()

    st.divider()
    with st.expander(f"Audit log for {item.file}"):
        entries = log.entries_for_file(item.file)
        if entries:
            st.table(
                [
                    {
                        "timestamp": e.timestamp,
                        "reviewer": e.reviewer,
                        "field": e.field,
                        "action": e.action,
                        "old_value": e.old_value,
                        "new_value": e.new_value,
                    }
                    for e in entries
                ]
            )
        else:
            st.write("No review decisions logged yet for this document.")


if __name__ == "__main__":
    main()
