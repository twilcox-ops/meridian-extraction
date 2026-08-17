"""Stage 2 — layout detection.

Classifies a document's layout (A, B, or C) from a load-bearing text
marker, before any field parser runs. Detection is deliberately
conservative: a document must match exactly one layout's marker to be
routed anywhere. Zero matches or more than one match is never silently
resolved by picking the "most likely" one — it comes back as `unknown` /
`ambiguous` so a human looks at it. Guessing the layout is exactly as
dangerous as guessing a field value: a document parsed with the wrong
parser produces confidently wrong output, not an error.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

Layout = Literal["A", "B", "C"]

# One marker per layout, chosen because it's boilerplate specific to that
# template rather than data that happens to vary per document. Verified
# against the full 36-document sample corpus: each document matches
# exactly one of these, never zero, never more than one.
_MARKERS: dict[Layout, re.Pattern[str]] = {
    "A": re.compile(r"Annual Safety Inspection Certificate"),
    "B": re.compile(r"Conveyance Inspection Record - retain for jurisdiction audit"),
    "C": re.compile(r"The conveyance identified below was examined on"),
}


@dataclass(frozen=True)
class LayoutClassification:
    """Result of classifying one document's text.

    `layout` is only set when classification is unambiguous. `matched`
    lists every marker that hit, which is what makes an `ambiguous` result
    diagnosable instead of just a mystery "None".
    """

    matched: tuple[Layout, ...]

    @property
    def layout(self) -> Layout | None:
        return self.matched[0] if len(self.matched) == 1 else None

    @property
    def status(self) -> Literal["ok", "unknown", "ambiguous"]:
        if len(self.matched) == 1:
            return "ok"
        if len(self.matched) == 0:
            return "unknown"
        return "ambiguous"


def classify_layout(text: str) -> LayoutClassification:
    """Check every layout marker against `text` and return what matched.

    Deterministic and pure — same text in, same classification out, which
    is what lets routing satisfy "reprocessing the same PDF twice produces
    identical output" the same way Stage 1's parsing does.
    """
    matched = tuple(layout for layout, pattern in _MARKERS.items() if pattern.search(text))
    return LayoutClassification(matched=matched)
