"""Acceptance bar: field-level accuracy against GROUND_TRUTH.csv, broken
out per layout and per field. Layout A and Layout C both have parsers and
should reach 100%; Layout B has none by design and is reported as skipped,
never scored as if it were wrong.
"""

from extraction.accuracy import score_extraction


def test_layout_a_reaches_100_percent(sample_data_dir):
    report = score_extraction(sample_data_dir)
    layout_a = report.layouts["A"]

    assert layout_a.documents_scored == 12
    assert layout_a.overall_accuracy() == 1.0
    assert not any(m.layout == "A" for m in report.mismatches)


def test_layout_c_reaches_100_percent(sample_data_dir):
    report = score_extraction(sample_data_dir)
    layout_c = report.layouts["C"]

    assert layout_c.documents_scored == 12
    assert layout_c.overall_accuracy() == 1.0
    assert not any(m.layout == "C" for m in report.mismatches)


def test_layout_b_is_reported_as_skipped_not_scored(sample_data_dir):
    """Layout B has no parser -- a deliberate scope boundary, not a bug.
    It must never show up as 0% accuracy (that would mean it was scored
    and found wrong); it must show up as skipped."""
    report = score_extraction(sample_data_dir)

    assert "B" not in report.layouts
    assert report.skipped_by_layout == {"B": 12}


def test_overall_accuracy_is_100_percent_across_both_scored_layouts(sample_data_dir):
    report = score_extraction(sample_data_dir)

    assert report.documents_scored() == 24  # 12 Layout A + 12 Layout C
    assert report.documents_skipped() == 12  # 12 Layout B
    assert report.mismatches == []
    assert report.overall_accuracy() == 1.0
