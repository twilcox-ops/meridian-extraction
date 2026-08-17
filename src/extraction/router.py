"""Stage 2 — routes a document to the parser for its detected layout.

Layout A and Layout C have parsers. Layout B does not — that's a
deliberate scope boundary, not an oversight: none of the project's stages
ever assign Layout B a parser, so it's classified correctly here and
always routed to the review queue instead. Any layout without a parser
produces an explicit "no parser implemented" result, never a silent empty
or garbage extraction that looks like success.
"""

from __future__ import annotations

from dataclasses import dataclass

from extraction.layout_a import parse_layout_a
from extraction.layout_c import parse_layout_c
from extraction.layout_detect import Layout, LayoutClassification, classify_layout
from extraction.models import ExtractionResult

# Registry of layout -> parser. Only layouts with a working parser appear
# here; Layout B is deliberately absent (see module docstring). Adding a
# parser for it later would be a one-line addition here, not a change to
# how routing works.
_PARSERS = {"A": parse_layout_a, "C": parse_layout_c}


@dataclass(frozen=True)
class RoutedDocument:
    classification: LayoutClassification
    result: ExtractionResult | None
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
