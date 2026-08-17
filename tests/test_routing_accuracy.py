"""Stage 2's acceptance bar: every document in the sample corpus should
land on its correct layout, measured against GROUND_TRUTH.csv rather than
assumed.
"""

from extraction.routing_report import build_routing_rows


def test_all_36_documents_route_to_the_correct_layout(sample_data_dir):
    rows = build_routing_rows(sample_data_dir)

    assert len(rows) == 36
    misrouted = [row for row in rows if row.is_misrouted]
    assert misrouted == []


def test_layout_counts_are_twelve_each(sample_data_dir):
    rows = build_routing_rows(sample_data_dir)
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.detected] = counts.get(row.detected, 0) + 1
    assert counts == {"A": 12, "B": 12, "C": 12}
