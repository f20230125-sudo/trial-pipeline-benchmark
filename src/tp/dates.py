"""ClinicalTrials.gov dates come in three precisions and two kinds.

  "2019-08-02"  a day            "2019-08"  a month (older records)      "2019"  a year (rare)
  type ACTUAL happened           type ESTIMATED is a forecast           type missing: the registry did not say

A month is stored as the first of the month and flagged `month`, so a comparison never pretends to know the day.
Windows ("readouts due in the next 24 months") are therefore compared at month granularity.
"""

from __future__ import annotations

import re
from datetime import date

_DAY = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_MONTH = re.compile(r"^(\d{4})-(\d{2})$")
_YEAR = re.compile(r"^(\d{4})$")

TYPES = {"ACTUAL", "ESTIMATED"}


def parse(raw: str | None) -> tuple[date | None, str]:
    """(date, precision). precision is day, month, year or missing. An impossible date is missing, not guessed."""
    text = (raw or "").strip()
    try:
        if m := _DAY.match(text):
            return date(int(m[1]), int(m[2]), int(m[3])), "day"
        if m := _MONTH.match(text):
            return date(int(m[1]), int(m[2]), 1), "month"
        if m := _YEAR.match(text):
            return date(int(m[1]), 1, 1), "year"
    except ValueError:
        pass
    return None, "missing"


def date_type(raw: str | None) -> str:
    t = (raw or "").strip().upper()
    return t if t in TYPES else "NOT STATED"


def month_index(d: date | None) -> int | None:
    """Months since year 0, so two dates can be compared or subtracted at month granularity."""
    return None if d is None else d.year * 12 + d.month - 1


def add_months(d: date, months: int) -> date:
    idx = d.year * 12 + d.month - 1 + months
    return date(idx // 12, idx % 12 + 1, 1)
