"""The Excel model: it builds from the marts, and the independent scorecard reproduces the published headline numbers.

The full proof (Excel's own formulas against the independent calculation, six scenarios) is tools/excel_probe.ps1 plus
tools/verify_workbook.py and needs Excel; these tests need neither Excel nor the warehouse."""

from __future__ import annotations

import importlib.util
import json

import pytest
from openpyxl import load_workbook  # noqa: F401  (skipped below if missing)

from tp import sources as S
from tp import workbook

pytestmark = pytest.mark.skipif(not (S.MARTS / "mart_study_export.csv").exists(), reason="marts not built")


@pytest.fixture(scope="module")
def verify():
    spec = importlib.util.spec_from_file_location("verify_workbook", S.ROOT / "tools" / "verify_workbook.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    return workbook.build(tmp_path_factory.mktemp("xlsx") / "model.xlsx")


def test_workbook_has_the_expected_sheets_and_named_inputs(built):
    wb = load_workbook(built)
    assert wb.sheetnames == ["Read me", "Inputs", "Scorecard", "Area matrix", "Expiring revenue", "Checks", "Data", "Lists"]
    names = set(wb.defined_names)
    assert {"FocusSponsor", "AreaSel", "StageSel", "ScopeSel", "WindowMonths", "AsOf", "Preset", "HorizonYear",
            "d_grp", "d_area", "d_stage", "d_active", "d_pc_date"} <= names
    assert wb["Data"].max_row == 24693  # header plus one row per pipeline study
    assert wb["Scorecard"]["B8"].value.startswith("=COUNTIFS")
    assert "PERCENTRANK.INC" in wb["Scorecard"]["L8"].value


def test_horizon_year_is_tied_to_a_sheet(built):
    wb = load_workbook(built)
    assert "Expiring revenue" in wb.defined_names["HorizonYear"].attr_text  # a bare C4 made Excel refuse the file


def test_scorecard_formulas_never_hard_code_a_result(built):
    ws = load_workbook(built)["Scorecard"]
    for row in range(8, 20):
        for col in "BCDEFGHIJKLMNOPQRS":
            v = ws[f"{col}{row}"].value
            assert isinstance(v, str) and v.startswith("="), f"{col}{row} is not a formula"


def test_independent_scorecard_reproduces_the_headline(verify):
    rows, _ = verify.load()
    s = {"focus": "MSD", "area": "All areas", "stage": "All clinical", "scope": "Active only", "window": 24,
         "asof": "2026-10-14", "preset": "Balanced", "custom": [25, 25, 25, 15, 10]}
    mine, w = verify.scorecard(rows, s)
    h = json.loads((S.ROOT / "dashboard" / "public" / "data" / "headline.json").read_text(encoding="utf-8"))
    assert mine["MSD"]["size"] == h["pipeline"]["msd_active_pipeline"]
    assert mine["MSD"]["readouts"] == h["readouts"]["msd_readouts_24m"]
    assert mine["AstraZeneca"]["readouts"] == h["readouts"]["azn_readouts_24m"]
    assert sum(w) == 100
    assert sorted(m["rank"] for m in mine.values()) == list(range(1, 13))


def test_equal_scores_break_ties_by_list_order(verify):
    # GSK and J&J tie in the default scenario once scores are rounded; the earlier company in the list ranks higher
    rows, _ = verify.load()
    s = {"focus": "MSD", "area": "All areas", "stage": "All clinical", "scope": "Active only", "window": 24,
         "asof": "2026-10-14", "preset": "Balanced", "custom": [25, 25, 25, 15, 10]}
    mine, _ = verify.scorecard(rows, s)
    assert mine["GSK"]["score"] == mine["J&J"]["score"]
    assert mine["GSK"]["rank"] + 1 == mine["J&J"]["rank"]
