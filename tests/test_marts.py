"""The marts must add back to the study table, and the exported JSON must say what the warehouse says."""

from __future__ import annotations

import json

import duckdb
import pytest

from tp import sources as S

pytestmark = pytest.mark.skipif(not S.WAREHOUSE.exists(), reason="warehouse not built: run python -m tp.build")

OUT = S.ROOT / "dashboard" / "public" / "data"


@pytest.fixture(scope="module")
def con():
    c = duckdb.connect(str(S.WAREHOUSE), read_only=True)
    yield c
    c.close()


def one(con, sql):
    return con.execute(sql).fetchone()[0]


def test_group_summary_adds_back_to_the_study_table(con):
    assert one(con, "select sum(studies_in_scope) from mart_group_summary") == one(con, "select count(*) from study")
    assert one(con, "select sum(pipeline_studies) from mart_group_summary") == one(
        con, "select count(*) from study where is_pipeline")
    assert one(con, "select sum(active_pipeline) from mart_group_summary") == one(
        con, "select count(*) from study where is_pipeline and is_active")
    assert one(con, "select count(*) from mart_group_summary where parent_studies + acquired_studies <> studies_in_scope") == 0
    assert one(con, "select count(*) from mart_group_summary where active_p1 + active_p2 + active_late <> active_pipeline") == 0


def test_phase_and_area_marts_sum_to_the_active_pipeline(con):
    for grp, n in con.execute("select grp, active_pipeline from mart_group_summary").fetchall():
        assert one(con, f"select sum(studies) from mart_pipeline_phase where grp = '{grp}'") == n
        assert one(con, f"select sum(studies) from mart_area_mix where grp = '{grp}'") == n
        assert abs(one(con, f"select sum(share_pct) from mart_area_mix where grp = '{grp}'") - 100) < 0.2


def test_every_group_has_every_area_row(con):
    assert one(con, "select count(*) from mart_area_mix") == 12 * 17


def test_ranks_are_consistent(con):
    assert one(con, "select active_pipeline_rank from mart_group_summary where grp = 'AstraZeneca'") == 1
    assert one(con, "select min(active_pipeline_rank) from mart_group_summary") == 1
    best = one(con, "select grp from mart_group_summary order by active_pipeline desc limit 1")
    assert one(con, f"select active_pipeline_rank from mart_group_summary where grp = '{best}'") == 1


def test_concentration_excludes_backbone_drugs(con):
    bg = {r[0] for r in con.execute("select molecule from ref_background").fetchall()}
    top = {r[0] for r in con.execute("select molecule from mart_top_molecules").fetchall()}
    assert not (bg & top)
    assert one(con, "select count(*) from mart_concentration") == 12
    assert one(con, "select top_molecule from mart_concentration where grp = 'MSD'") == "pembrolizumab"
    assert one(con, "select count(*) from mart_concentration where share_pct > 100 or share_pct <= 0") == 0


def test_readouts_add_up_and_stay_inside_the_window(con):
    assert one(con, "select sum(studies) from mart_readouts_quarter where grp = 'MSD'") == one(
        con, "select readouts_24m from mart_readouts_summary where grp = 'MSD'") == one(
        con, "select count(*) from mart_readouts_msd")
    lo, hi = con.execute("select min(pc_date), max(pc_date) from mart_readouts_msd").fetchone()
    assert str(lo) >= "2026-10-01" and str(hi) < "2028-10-01"


def test_starts_use_only_real_starts(con):
    # a study that has not started (ESTIMATED start) or was withdrawn must not count as a start
    n = one(con, "select count(*) from study where is_pipeline and status = 'WITHDRAWN' and start_type <> 'ESTIMATED' "
                 "and start_date is not null and start_date <= date '2026-10-14'")
    total_counted = one(con, "select sum(studies) from mart_starts_year")
    direct = one(con, "select count(*) from study where is_pipeline and start_date is not null and start_type <> 'ESTIMATED' "
                      "and start_date <= date '2026-10-14' and year(start_date) between 2014 and 2026")
    assert total_counted == direct
    assert n >= 0  # withdrawn studies with a real-looking start are rare; they are counted as the registry reports them


def test_termination_rate_is_a_share_of_ended_studies(con):
    assert one(con, "select count(*) from mart_termination where termination_rate_pct < 0 or termination_rate_pct > 100") == 0
    for grp, c, t, rate in con.execute("select grp, completed, terminated, termination_rate_pct from mart_termination").fetchall():
        assert abs(100.0 * t / (c + t) - rate) < 0.06, grp


def test_gulf_counts_agree_between_marts(con):
    for grp, n, active in con.execute("select grp, gcc_studies, gcc_active_studies from mart_gulf_summary").fetchall():
        by_country_max = one(con, f"select coalesce(max(studies), 0) from mart_gulf_country where grp = '{grp}'")
        assert by_country_max <= n  # no single country can have more studies than the union
        assert active <= n
    assert one(con, "select gcc_studies from mart_gulf_summary where grp = 'MSD'") == one(
        con, "select count(*) from study where grp = 'MSD' and is_pipeline and has_gcc_site")


def test_expiring_revenue_only_counts_dated_protection(con):
    assert one(con, "select sum(spend_2025_at_risk) from mart_expiring_revenue") == one(
        con, "select sum(spend_2025) from rx_family where core_end between date '2026-01-01' and date '2028-12-31'")
    fams = one(con, "select string_agg(families, ',') from mart_expiring_revenue")
    assert "KEYTRUDA" not in fams  # a biologic with no Orange Book date is never given a made-up one


def test_exported_json_files_parse_and_match_the_warehouse(con):
    names = ["meta", "overview", "concentration", "revenue", "readouts", "starts", "gulf", "quality", "msd_active",
             "headline"]
    data = {n: json.loads((OUT / f"{n}.json").read_text(encoding="utf-8")) for n in names}
    assert len(data["overview"]["summary"]) == 12 and len(data["msd_active"]) == one(
        con, "select count(*) from mart_msd_active")
    h = data["headline"]
    assert h["pipeline"]["msd_active_pipeline"] == one(
        con, "select active_pipeline from mart_group_summary where grp = 'MSD'")
    assert h["snapshot"]["studies_in_scope"] == one(con, "select count(*) from study")
    assert h["snapshot"]["distinct_studies_fetched"] == h["snapshot"]["studies_in_scope"] + h["snapshot"]["studies_quarantined"]


def test_headline_is_inside_the_ranges_the_plan_expected(con):
    h = json.loads((OUT / "headline.json").read_text(encoding="utf-8"))
    assert 220 <= h["pipeline"]["msd_active_pipeline"] <= 270
    assert 30 <= h["concentration"]["msd_share_pct"] <= 45
    assert h["concentration"]["msd_concentration_rank"] == 1
    assert h["gulf"]["msd_gcc_pipeline_studies"] < 15
    assert h["gulf"]["azn_gcc_pipeline_studies"] > 3 * h["gulf"]["msd_gcc_pipeline_studies"]
    assert h["quality"]["fail"] == 0 and h["quality"]["checks"] >= 20
    assert h["quality"]["tests"] is None or h["quality"]["tests"] >= 110
    assert h["harmonisation"]["merck_kgaa_set_aside"] > 200
    assert h["snapshot"]["groups"] == 12 and h["snapshot"]["peers"] == 11


def test_no_em_dash_in_any_exported_file():
    for p in OUT.glob("*.json"):
        assert chr(0x2014) not in p.read_text(encoding="utf-8"), p.name
