"""Why a study stopped: free text from the registry's whyStopped field, mapped to a handful of themes.

Rules are tried in the order of data/ref/why_stopped_rules.csv; the first match wins. One trap is handled in code: a
sentence like "sponsor decision, not related to any safety concern" mentions safety in order to deny it, so a negated
mention of safety or efficacy is removed before the rules run. The mapping is a heuristic: the README reports how much
lands in "Other" and "Not stated" rather than hiding it.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

from . import sources as S

THEMES = ["Business or strategic", "Efficacy or futility", "Safety", "Enrolment", "Supply, regulatory or operational",
          "COVID-19", "Other", "Not stated"]

# "not related to (vaccine) safety or efficacy", "no safety concern", "unrelated to safety", "without safety ..."
_NEGATED = re.compile(
    r"\b(?:not|no|nor|unrelated to|without)\b[^.;]{0,60}?\b(?:safety|efficacy)\w*"
    r"(?:\s*(?:or|and|/|,)\s*(?:safety|efficacy)\w*)*",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Rule:
    order: int
    theme: str
    pattern: re.Pattern


def load_rules(path: Path = S.REF / "why_stopped_rules.csv") -> list[Rule]:
    with path.open(encoding="utf-8", newline="") as fh:
        rules = [Rule(int(r["order"]), r["theme"], re.compile(r["pattern"], re.IGNORECASE)) for r in csv.DictReader(fh)]
    unknown = {r.theme for r in rules} - set(THEMES)
    if unknown:
        raise ValueError(f"unknown stop themes in rules file: {sorted(unknown)}")
    if rules[-1].pattern.pattern != ".*":
        raise ValueError("the last stop rule must be the catch-all")
    return rules


def theme(text: str | None, rules: list[Rule]) -> str:
    cleaned = _NEGATED.sub(" ", (text or "").strip())
    for r in rules:
        if r.pattern.search(cleaned):
            return r.theme
    return "Other"
