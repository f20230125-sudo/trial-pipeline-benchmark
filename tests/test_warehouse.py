"""Data tests: they run against the built warehouse (python -m tp.build) and prove its tables agree with each other
and with the API's own totals. They are skipped, not failed, when the warehouse has not been built."""

from __future__ import annotations

import json

import duckdb
import pytest

from tp import sources as S

pytestmark = pytest.mark.skipif(not S.WAREHOUSE.exists(), reason="warehouse not built: run python -m tp.build")

GROUPS = {"MSD", "Pfizer", "AstraZeneca", "Novartis", "Roche", "BMS", "Lilly", "Novo Nordisk", "AbbVie", "GSK",
          "Sanofi", "J&J"}


@pytest.fixture(scope="module")
def con():
    c = duckdb.connect(str(S.WAREHOUSE), read_only=True)
    yield c
    c.close()


def one(con, sql):
    return con.execute(sql).fetchone()[0]


def test_every_fetched_study_is_in_scope_or_quarantined_with_a_reason(con):
    fetched = one(con, "select count(distinct nct_id) from stg_study")
    in_scope = one(con, "select count(*) from study")
    quarantined = one(con, "select count(*) from quarantine")
    assert fetched == in_scope + quarantined
    assert one(con, "select count(*) from study s join quarantine q using (nct_id)") == 0
    assert one(con, "select count(*) from quarantine where reason is null or reason = ''") == 0


def test_one_row_per_study(con):
    assert one(con, "select count(*) - count(distinct nct_id) from study") == 0
    assert one(con, "select count(*) - count(distinct nct_id) from stg_study") == 0
    assert one(con, "select count(*) from study where not regexp_matches(nct_id, '^NCT[0-9]{8}$')") == 0


def test_snapshot_matches_the_api_totals_in_the_manifest(con):
    manifest = json.loads(S.MANIFEST.read_text(encoding="utf-8"))
    assert manifest["dataTimestamp_start"] == manifest["dataTimestamp_end"]
    for t in manifest["terms"]:
        assert t["studies"] == t["totalCount"], t["slug"]
    per_term = one(con, "select count(*) from study_query")
    assert per_term == sum(t["studies"] for t in manifest["terms"])  # study_query keeps every (study, term) pair
    assert one(con, "select count(distinct nct_id) from study_query") == one(con, "select count(*) from stg_study")


def test_only_the_twelve_groups_are_in_scope(con):
    assert {r[0] for r in con.execute("select distinct grp from study").fetchall()} == GROUPS
    assert one(con, "select count(*) from study where sponsor_kind not in ('parent', 'acquired')") == 0


def test_merck_kgaa_never_counts_as_msd(con):
    assert one(con, "select count(*) from study where grp = 'MSD' and "
                    "(lead_name ilike '%KGaA%' or lead_name ilike '%EMD Serono%' or lead_name ilike '%SpringWorks%')") == 0
    assert one(con, "select count(*) from quarantine where reason like '%Merck KGaA%'") > 200  # it was seen and set aside


def test_msd_counts_are_in_the_expected_range(con):
    assert 2350 <= one(con, "select count(*) from study where grp = 'MSD'") <= 2550
    assert 230 <= one(con, "select count(*) from study where grp = 'MSD' and is_pipeline and is_active") <= 260


def test_acquired_companies_are_rolled_up(con):
    names = {r[0] for r in con.execute("select lead_name from study where grp = 'MSD' and sponsor_kind = 'acquired'"
                                       ).fetchall()}
    assert any("Cubist" in n for n in names) and any("Acceleron" in n for n in names)
    assert one(con, "select count(*) from study where grp = 'Pfizer' and lead_name ilike 'Seagen%'") > 100


def test_pipeline_flag_means_what_the_readme_says(con):
    assert one(con, "select count(*) from study where is_pipeline and study_type <> 'INTERVENTIONAL'") == 0
    assert one(con, "select count(*) from study where is_pipeline and (phase_max is null or phase_max > 3)") == 0
    assert one(con, "select count(*) from study where is_pipeline and not has_drug_intervention") == 0
    assert one(con, "select count(*) from study where is_late and phase not in ('Phase 3', 'Phase 2/3')") == 0
    assert one(con, "select count(*) from study where is_active and status_class <> 'active'") == 0


def test_status_classes_cover_every_study(con):
    assert one(con, "select count(*) from study where status_class is null") == 0
    assert one(con, "select count(*) from study where is_overdue and not is_active") == 0


def test_dates_are_parsed_with_their_precision(con):
    assert one(con, "select count(*) from study where start_precision <> 'missing' and start_date is null") == 0
    assert one(con, "select count(*) from study where start_precision = 'missing' and start_date is not null") == 0
    assert one(con, "select count(*) from study where start_precision = 'month' and day(start_date) <> 1") == 0


def test_every_country_spelling_is_mapped(con):
    assert one(con, "select count(*) from stg_location l left join dim_country c on c.raw = l.country_raw "
                    "where l.country_raw is not null and c.raw is null") == 0
    gcc = {r[0] for r in con.execute("select iso3 from dim_country where is_gcc").fetchall()}
    assert gcc == {"ARE", "SAU", "QAT", "KWT", "BHR", "OMN"}


def test_site_counts_add_up(con):
    in_scope_sites = one(con, "select sum(n_sites) from study")
    mapped = one(con, "select count(*) from stg_location l join dim_country c on c.raw = l.country_raw "
                      "where l.nct_id in (select nct_id from study)")
    assert in_scope_sites == mapped
    assert one(con, "select count(*) from study where has_gcc_site and not exists "
                    "(select 1 from study_country c where c.nct_id = study.nct_id and c.is_gcc)") == 0


def test_stop_theme_is_set_only_for_stopped_studies(con):
    assert one(con, "select count(*) from study where stop_theme is not null and "
                    "status not in ('TERMINATED', 'WITHDRAWN', 'SUSPENDED')") == 0
    assert one(con, "select count(*) from study where status in ('TERMINATED', 'WITHDRAWN') and stop_theme is null") == 0
