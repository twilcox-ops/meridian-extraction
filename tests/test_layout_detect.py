from extraction.layout_detect import classify_layout

TEXT_A = "Annual Safety Inspection Certificate\nCertificate No:   MES-2026-4100\n"
TEXT_B = "Conveyance Inspection Record - retain for jurisdiction audit\nUnit: B75-5\n"
TEXT_C = "The conveyance identified below was examined on 04/02/2026 by D. Whitfield\n"


def test_classifies_layout_a():
    result = classify_layout(TEXT_A)
    assert result.layout == "A"
    assert result.status == "ok"
    assert result.matched == ("A",)


def test_classifies_layout_b():
    result = classify_layout(TEXT_B)
    assert result.layout == "B"
    assert result.status == "ok"


def test_classifies_layout_c():
    result = classify_layout(TEXT_C)
    assert result.layout == "C"
    assert result.status == "ok"


def test_unknown_when_no_marker_matches():
    result = classify_layout("this document matches nothing we recognize")
    assert result.layout is None
    assert result.status == "unknown"
    assert result.matched == ()


def test_ambiguous_when_multiple_markers_match():
    """Two markers matching must never be silently resolved by picking
    one — it has to surface as ambiguous so a human looks at it."""
    mixed_text = TEXT_A + TEXT_B
    result = classify_layout(mixed_text)
    assert result.layout is None
    assert result.status == "ambiguous"
    assert set(result.matched) == {"A", "B"}


def test_classification_is_deterministic():
    assert classify_layout(TEXT_A) == classify_layout(TEXT_A)
