from extraction.router import route

TEXT_A = """
Annual Safety Inspection Certificate

Certificate No:   MES-2026-4100
Unit ID:          D97-6
Building:         Kestrel Plaza
Address:          88 Ninth Ave, Denver, CO 80202
Unit Type:        Freight
Capacity (lbs):   4000
Inspection Date:  01/13/2026
Next Due:         01/13/2027
Inspector:        A. Vasquez
Result:           FAIL
Invoice Total:    $1,766.82
"""

TEXT_B = "Conveyance Inspection Record - retain for jurisdiction audit\nUnit: B75-5\n"
TEXT_C = "The conveyance identified below was examined on 04/02/2026 by D. Whitfield\n"


def test_layout_a_routes_to_its_parser_and_produces_a_result():
    routed = route(TEXT_A)
    assert routed.layout == "A"
    assert routed.result is not None
    assert routed.result.cert_no == "MES-2026-4100"
    assert not routed.misrouted


def test_layout_b_classified_correctly_but_has_no_parser_yet():
    routed = route(TEXT_B)
    assert routed.layout == "B"
    assert routed.result is None
    assert routed.misrouted  # no parser exists -> never treat this as handled
    assert "no parser" in routed.note


def test_layout_c_classified_correctly_but_has_no_parser_yet():
    routed = route(TEXT_C)
    assert routed.layout == "C"
    assert routed.result is None
    assert routed.misrouted


def test_unrecognized_text_is_never_routed_anywhere():
    routed = route("not a document we recognize at all")
    assert routed.layout is None
    assert routed.result is None
    assert routed.misrouted
