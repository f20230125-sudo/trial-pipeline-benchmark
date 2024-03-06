"""Therapeutic area for a trial, in the same 17 areas Rx Market Pulse uses, so the two projects join.

Rules live in data/ref/area_rules.csv (priority, area, regex), applied to text. A term takes the area of the
lowest-priority-number rule that matches, which is how a specific rule ("HIV", 10) beats a general one ("Infection", 35).

The cascade for a study (the step that decided it is recorded in `area_source`):
  1. override     data/ref/area_overrides.csv, by NCT ID: a short, documented list of corrections found by review
  2. text         the free-text condition names a person typed (the most specific signal)
  3. mesh         the registry's MeSH condition terms: the directly matched ones, then their ancestors
  4. molecule     the most common area of the same molecule's other studies (catches healthy-volunteer Phase 1 studies)
  5. none         Unclassified, never spread across other areas

Why text beats MeSH: the registry's MeSH matching is automatic, and its ancestors are generic and often point the wrong way.
Multiple sclerosis inherits "Autoimmune Diseases", atopic dermatitis inherits "Skin Diseases, Genetic", and a lung-cancer study
that mentions PD-L1 is also tagged with a Parkinson disease term. Within a step the lowest priority number wins, so Oncology
(20) beats Nervous System (70). Every study where the text area and the directly matched MeSH area disagree is flagged
`area_conflict` and counted by the data-quality scorecard.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

from . import sources as S

AREAS = [
    "Neurology & psychiatry", "Immunology & inflammation", "Diabetes & obesity", "Oncology", "Respiratory & allergy",
    "Rare & genetic disease", "HIV", "Cardiovascular", "Hematology", "Pain, addiction & anesthesia",
    "Infectious disease (non-HIV)", "Endocrine & women's health", "Gastroenterology", "Unclassified", "Eye & skin",
    "Urology & renal", "Other (vitamins, fluids, diagnostics)",
]


@dataclass(frozen=True)
class Rule:
    priority: int
    area: str
    pattern: re.Pattern


def load_rules(path: Path = S.REF / "area_rules.csv") -> list[Rule]:
    with path.open(encoding="utf-8", newline="") as fh:
        rules = [Rule(int(r["priority"]), r["area"], re.compile(r["pattern"], re.IGNORECASE))
                 for r in csv.DictReader(fh)]
    bad = {r.area for r in rules} - set(AREAS)
    if bad:
        raise ValueError(f"area rules name unknown areas: {sorted(bad)}")
    return sorted(rules, key=lambda r: r.priority)


def area_for(text: str | None, rules: list[Rule]) -> tuple[str, int] | None:
    """(area, priority) of the best matching rule, or None when nothing matches."""
    if not text:
        return None
    for r in rules:  # sorted, so the first hit is the best
        if r.pattern.search(text):
            return r.area, r.priority
    return None


def load_overrides(path: Path = S.REF / "area_overrides.csv") -> dict[str, tuple[str, str]]:
    """NCT ID -> (area, reason). The file may be empty."""
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    bad = {r["area"] for r in rows} - set(AREAS)
    if bad:
        raise ValueError(f"area overrides name unknown areas: {sorted(bad)}")
    return {r["nct_id"]: (r["area"], r["reason"]) for r in rows}
