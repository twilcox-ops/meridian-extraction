"""Stage 1's acceptance bar: Layout A should reach 100% field accuracy
against GROUND_TRUTH.csv. This test is the thing that makes that a measured
fact rather than a claim.
"""

from extraction.accuracy import score_layout_a


def test_layout_a_reaches_100_percent(sample_data_dir):
    report = score_layout_a(sample_data_dir)

    assert report.documents_scored == 12  # 12 Layout A docs in the corpus
    assert report.mismatches == []
    assert report.overall_accuracy() == 1.0


def test_other_layouts_are_reported_as_skipped_not_silently_dropped(sample_data_dir):
    report = score_layout_a(sample_data_dir)
    assert report.documents_skipped == 24  # Layout B + C, not handled until Stage 2
