"""One key per drug, so "Pembrolizumab 200 mg IV", "MK-3475" and the registry's MeSH term "pembrolizumab" count once.

normalise() works on a single intervention name and returns a lower-case key, or None when the name is a comparator
(placebo, saline, standard of care ...) or empty. It removes doses, routes and forms, drops anything in brackets and
writes Merck's development codes the same way (MK-3475, MK 3475 and mk3475-A all become mk-3475). It does not know that a
brand name equals a generic name; that is what the registry's MeSH terms are for, and for Merck products tp.rx_link.
"""

from __future__ import annotations

import re

_COMPARATOR = re.compile(
    r"\b(placebos?|sham|saline|standard of care|usual care|best supportive care|supportive care|no treatment|"
    r"no intervention|vehicle|dummy|observation|watchful waiting|control|comparator|standard therapy|standard treatment|background therapy|"
    r"matching|rescue (?:medication|therapy|treatment|drug)s?)\b",
    re.IGNORECASE,
)
# "Physician's choice", "Physicians' Choice", "Investigator's Treatment of Choice": a name that BEGINS this way is the
# comparator arm. Anchored, so "ivonescimab + investigator-choice platinum doublet" still counts ivonescimab.
_CHOICE = re.compile(r"^(?:the )?(?:physician|investigator)s?['’`]?s?[\s-]+(?:treatment of )?choice|^treatment of physician",
                     re.IGNORECASE)
_BRACKETS = re.compile(r"\([^)]*\)|\[[^\]]*\]")
_MK = re.compile(r"\bmk[\s_-]?(\d{4})(?:[\s_-]?[a-z0-9]{0,3})?\b", re.IGNORECASE)
_DOSE = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:mg|mcg|µg|ug|g|kg|ml|l|iu|units?|u|%|mci|gbq|mmol|nmol)\b(?:\s*/\s*\w+)?", re.IGNORECASE)
_FORM = re.compile(
    r"\b(oral|orally|intravenous|intravenously|iv|subcutaneous|subcutaneously|sc|sq|intramuscular|im|topical|"
    r"injection|injectable|infusion|tablets?|capsules?|solution|suspension|cream|gel|ointment|patch|spray|drops|"
    r"inhaled|inhalation|powder|vial|syringe|autoinjector|pen|film[- ]coated|extended[- ]release|immediate[- ]release|"
    r"xr|er|sr|ir|formulation|doses?|dosing|low|high|medium|single|multiple|once|twice|daily|weekly|monthly|"
    r"every \d+ weeks?|q\d+w|q\d+h|bid|qd|tid|and|or|plus|with|in combination)\b",
    re.IGNORECASE,
)


def is_comparator(text: str | None) -> bool:
    return bool(text) and bool(_COMPARATOR.search(text) or _CHOICE.search(text.strip()))


def normalise(name: str | None) -> str | None:
    if not name or not name.strip() or is_comparator(name):
        return None
    text = name.replace("®", " ").replace("™", " ").replace("©", " ")
    text = _BRACKETS.sub(" ", text)
    if m := _MK.search(text):
        return f"mk-{m.group(1)}"
    text = _DOSE.sub(" ", text)
    text = _FORM.sub(" ", text)
    text = re.sub(r"[^\w+/-]+", " ", text.lower())
    text = re.sub(r"\s+", " ", text).strip(" -/+")
    return text or None
