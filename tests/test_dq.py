"""The scorecard must itself be trustworthy: a fixed set of checks, none failing, written out in full."""

from __future__ import annotations

import csv

import duckdb
import pytest

from tp import dq
from tp import sources as S

pytestmark = pytest.mark.skipif(not S.WAREHOUSE.exists(), reason="warehouse not built: run python -m tp.build")


@pytest.fixture(scope="module")
def result():
    con = duckdb.connect(str(S.WAREHOUSE), read_only=True)
    try:
        return dq.run(con, offline=True)
    finally:
        con.close()


def test_the_scorecard_has_the_expected_checks(result):
    checks, _ = result
    ids = [c.id for c in checks]
    assert ids == [f"C{i:02d}" for i in range(1, len(ids) + 1)]
    assert len(checks) >= 20
    assert {c.dimension for c in checks} >= {"Completeness", "Validity", "Uniqueness", "Reconciliation", "Coverage",
                                             "Harmonisation", "Timeliness"}


def test_no_check_fails(result):
    checks, _ = result
    failing = [f"{c.id} {c.name}: {c.result}" for c in checks if c.status == "fail"]
    assert failing == []


def test_every_check_explains_itself(result):
    checks, _ = result
    for c in checks:
        assert c.name and c.result and c.rule, c.id
        assert c.status in {"pass", "warn", "fail", "info"}, c.id


def test_the_waterfall_adds_up(result):
    _, wf = result
    steps = [r["studies"] for r in wf]
    assert wf[0]["stage"] == "Rows returned by the searches"
    assert wf[-1]["stage"] == "Studies in scope"
    assert sum(steps[:-1]) == steps[-1]  # hits minus duplicates minus everything set aside = in scope


def test_writing_the_scorecard_makes_both_files(result, tmp_path, monkeypatch):
    checks, wf = result
    monkeypatch.setattr(S, "MARTS", tmp_path / "marts")
    monkeypatch.setattr(S, "DOCS", tmp_path / "docs")
    dq.write(checks, wf)
    rows = list(csv.DictReader((tmp_path / "marts" / "dq_checks.csv").open(encoding="utf-8")))
    assert len(rows) == len(checks)
    md = (tmp_path / "docs" / "data-quality-scorecard.md").read_text(encoding="utf-8")
    assert md.startswith("# Data-quality scorecard") and "From search hits to studies in scope" in md
    assert chr(0x2014) not in md
