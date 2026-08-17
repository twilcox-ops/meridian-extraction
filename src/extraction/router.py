"""Stage 2 — routes a document to the parser for its detected layout.

Only Layout A has a parser so far (Stage 1). Layout B and C are classified
correctly here but have no parser yet — routing one of them produces an
explicit "no parser implemented" result, never a silent empty or garbage
extraction that looks like success.
"""

from __future__ import annotations

from dataclasses import dataclass

from extraction.layout_a import LayoutAResult, parse_layout_a
from extraction.layout_detect import Layout, LayoutClassification, classify_layout

# Registry of layout -> parser. Stage 2 only ever wires up layouts that
# already have a working parser; adding Layout B/C parsers later is a
# one-line addition here, not a change to how routing works.
_PARSERS = {"A": parse_layout_a}


@dataclass(frozen=True)
class RoutedDocument:
    classification: LayoutClassification
    result: LayoutAResult | None
    note: str

    @property
    def layout(self) -> Layout | None:
        return self.classification.layout

    @property
    def misrouted(self) -> bool:
        """True whenever this document was NOT cleanly routed to a working
        parser — unknown layout, ambiguous marker match, or a layout with
        no parser yet. This is the signal a caller should surface, not bury."""
        return self.result is None


def route(text: str) -> RoutedDocument:
    classification = classify_layout(text)

    if classification.status != "ok":
        return RoutedDocument(
            classification=classification,
            result=None,
            note=f"{classification.status}: matched markers = {classification.matched or 'none'}",
        )

    parser = _PARSERS.get(classification.layout)
    if parser is None:
        return RoutedDocument(
            classification=classification,
            result=None,
            note=f"layout {classification.layout} detected correctly, but no parser exists yet",
        )

    return RoutedDocument(
        classification=classification,
        result=parser(text),
        note=f"routed to layout {classification.layout} parser",
    )
