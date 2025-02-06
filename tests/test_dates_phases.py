from datetime import date

import pytest

from tp import dates, phases


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("2019-08-02", (date(2019, 8, 2), "day")),
        ("2019-08", (date(2019, 8, 1), "month")),
        ("2019", (date(2019, 1, 1), "year")),
        (" 2024-12-31 ", (date(2024, 12, 31), "day")),
        ("2019-02-30", (None, "missing")),  # impossible dates are not guessed
        ("2019-13", (None, "missing")),
        ("", (None, "missing")),
        (None, (None, "missing")),
        ("August 2019", (None, "missing")),
    ],
)
def test_parse_dates(raw, expected):
    assert dates.parse(raw) == expected


@pytest.mark.parametrize("raw,expected", [("ACTUAL", "ACTUAL"), ("estimated", "ESTIMATED"), (None, "NOT STATED"),
                                          ("", "NOT STATED"), ("ANTICIPATED", "NOT STATED")])
def test_date_type(raw, expected):
    assert dates.date_type(raw) == expected


def test_month_arithmetic_crosses_years():
    assert dates.add_months(date(2026, 10, 1), 24) == date(2028, 10, 1)
    assert dates.add_months(date(2026, 11, 1), 3) == date(2027, 2, 1)
    assert dates.add_months(date(2026, 1, 1), -1) == date(2025, 12, 1)
    assert dates.month_index(date(2026, 10, 15)) - dates.month_index(date(2026, 1, 1)) == 9
    assert dates.month_index(None) is None


@pytest.mark.parametrize(
    "codes,label,pmax,pipeline",
    [
        (["PHASE1"], "Phase 1", 1, True),
        (["EARLY_PHASE1"], "Early Phase 1", 1, True),
        (["PHASE1", "PHASE2"], "Phase 1/2", 2, True),
        (["PHASE2", "PHASE1"], "Phase 1/2", 2, True),  # order in the list does not matter
        (["PHASE2"], "Phase 2", 2, True),
        (["PHASE2", "PHASE3"], "Phase 2/3", 3, True),
        (["PHASE3"], "Phase 3", 3, True),
        (["PHASE4"], "Phase 4", 4, False),
        (["NA"], "Not applicable", None, False),
        ([], "Not stated", None, False),
        (None, "Not stated", None, False),
        ("PHASE1,PHASE2", "Phase 1/2", 2, True),
        ("PHASE2/PHASE3", "Phase 2/3", 3, True),
        (["SOMETHING_NEW"], "Not stated", None, False),
    ],
)
def test_phase_parse(codes, label, pmax, pipeline):
    p = phases.parse(codes)
    assert (p.label, p.phase_max, p.pipeline) == (label, pmax, pipeline)


def test_phase_rank_follows_display_order():
    ranks = [phases.parse(c).rank for c in (["EARLY_PHASE1"], ["PHASE1"], ["PHASE1", "PHASE2"], ["PHASE2"],
                                           ["PHASE2", "PHASE3"], ["PHASE3"], ["PHASE4"], ["NA"], [])]
    assert ranks == sorted(ranks) and len(set(ranks)) == len(ranks)
