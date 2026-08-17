from extraction.review_queue import build_queue, evaluate_document


def test_clean_layout_a_document_needs_no_review(sample_data_dir):
    item = evaluate_document(sample_data_dir / "MES-2026-4100.pdf")
    assert item.layout == "A"
    assert item.needs_review is False
    assert item.reasons == ()
    assert all(score == 1.0 for score in item.confidences.values())
    assert item.validation is not None and item.validation.valid


def test_unparsed_layout_document_is_flagged_for_review(sample_data_dir):
    item = evaluate_document(sample_data_dir / "MES-2026-4101.pdf")  # Layout B: no parser
    assert item.layout == "B"
    assert item.needs_review is True
    assert all(value is None for value in item.values.values())
    assert all(score == 0.0 for score in item.confidences.values())
    assert any("routing" in r for r in item.reasons)
    assert any("low-confidence" in r for r in item.reasons)


def test_missing_capacity_layout_c_document_is_flagged_for_the_right_reason(sample_data_dir):
    """Once Layout C has a parser, a missing-capacity document must still
    land in the review queue -- but now specifically because capacity_lbs
    is low-confidence, not because nothing was extracted at all."""
    item = evaluate_document(sample_data_dir / "MES-2026-4102.pdf")  # Layout C, capacity omitted
    assert item.layout == "C"
    assert item.needs_review is True
    assert item.values["capacity_lbs"] is None
    assert item.values["cert_no"] is not None  # everything else did extract
    assert item.reasons == ("low-confidence/missing fields: capacity_lbs",)


def test_fully_extracted_layout_c_document_needs_no_review(sample_data_dir):
    item = evaluate_document(sample_data_dir / "MES-2026-4105.pdf")  # Layout C, capacity present
    assert item.layout == "C"
    assert item.needs_review is False
    assert item.reasons == ()


def test_full_corpus_queue_matches_expected_counts(sample_data_dir):
    items = build_queue(sample_data_dir)
    clean = [i for i in items if not i.needs_review]
    review = [i for i in items if i.needs_review]

    assert len(items) == 36
    # clean: 12 Layout A + 8 Layout C (the ones with capacity present)
    assert len(clean) == 20
    # review: 12 Layout B (no parser) + 4 Layout C (capacity missing)
    assert len(review) == 16


def test_nothing_in_the_clean_set_has_a_missing_field():
    """Acceptance bar: no document silently produces a wrong or missing
    value in the clean output -- every clean item is fully populated."""
    from extraction.review_queue import DEFAULT_SAMPLE_DATA

    items = build_queue(DEFAULT_SAMPLE_DATA)
    for item in items:
        if not item.needs_review:
            assert all(v is not None for v in item.values.values())
