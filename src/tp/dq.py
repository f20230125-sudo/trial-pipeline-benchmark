"""Data-quality scorecard.

    python -m tp.dq [--offline]

Runs every check against the built warehouse, then writes
    data/marts/dq_checks.csv       one row per check (also read by the dashboard)
    data/marts/dq_waterfall.csv    from search hits to studies in scope, and what the sponsor roll-up recovers
    docs/data-quality-scorecard.md the same, readable

Each check says what it measured, the number, the rule it was held to, and how many studies it touches. A check that
fails its rule is not hidden: the report leads with it, and the command exits 1. --offline skips the one check that asks
the live API (C14).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime

import duckdb

from . import sources as S
from . import sponsors
from .build import connect


@dataclass
class Check:
    id: str
    dimension: str
    name: str
    result: str
    rule: str
    status: str  # pass | warn | fail | info
    studies: int | None
    note: str


def _one(con: duckdb.DuckDBPyConnection, sql: str):
    return con.execute(sql).fetchone()


def _pct(x: float | None, digits: int = 1) -> str:
    return "n/a" if x is None else f"{x:.{digits}f}%"


def _grade(value: float, ok: float, warn: float) -> str:
    return "pass" if value >= ok else ("warn" if value >= warn else "fail")


def _live_count(term: str) -> tuple[int, str] | None:
    """(totalCount, dataTimestamp) from the live API, or None when offline."""
    try:
        import requests

        h = {"User-Agent": S.USER_AGENT}
        total = requests.get(S.STUDIES_URL, params={"query.lead": term, "pageSize": "1", "countTotal": "true",
                                                   "format": "json", "fields": "NCTId"}, headers=h, timeout=30)
        ver = requests.get(S.VERSION_URL, headers=h, timeout=30)
        return total.json()["totalCount"], ver.json()["dataTimestamp"]
    except Exception:
        return None


LIVE_RECORD = S.SNAPSHOT / "live_check.json"


def _write_live_record(manifest: dict, warehouse: int, api: int, ts: str) -> None:
    LIVE_RECORD.write_text(json.dumps({
        "checked_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "term": "Merck Sharp & Dohme (lead sponsor, full-text)",
        "api_data_timestamp": ts, "api_count": api, "warehouse_count": warehouse,
        "snapshot_data_timestamp": manifest["dataTimestamp_start"],
    }, indent=2) + "\n", encoding="utf-8")


def _read_live_record(manifest: dict) -> dict | None:
    if not LIVE_RECORD.exists():
        return None
    rec = json.loads(LIVE_RECORD.read_text(encoding="utf-8"))
    return rec if rec.get("snapshot_data_timestamp") == manifest["dataTimestamp_start"] else None


def run(con: duckdb.DuckDBPyConnection, offline: bool = False) -> tuple[list[Check], list[dict]]:
    checks: list[Check] = []
    manifest = json.loads(S.MANIFEST.read_text(encoding="utf-8"))
    n_pipe = _one(con, "select count(*) from study where is_pipeline")[0]
    n_act = _one(con, "select count(*) from study where is_pipeline and is_active")[0]

    # ------------------------------------------------------------ completeness
    missing = _one(con, """select count(*) from study where nct_id is null or lead_name is null or status is null
                           or study_type is null""")[0]
    checks.append(Check("C01", "Completeness", "Study ID, lead sponsor, status and type are present on every study",
                        f"{missing:,} studies missing one", "0", "pass" if missing == 0 else "fail", missing, ""))
    has_start = _one(con, "select count(*) from study where is_pipeline and start_date is not null")[0]
    checks.append(Check("C02", "Completeness", "Pipeline studies with a start date",
                        f"{_pct(100 * has_start / n_pipe)} ({n_pipe - has_start:,} without)", ">= 98%",
                        _grade(100 * has_start / n_pipe, 98, 90), n_pipe - has_start,
                        "Older records and withdrawn studies often have none. Studies without a start date are left "
                        "out of start-year counts, never given a made-up year."))
    has_pc = _one(con, "select count(*) from study where is_pipeline and is_active and pc_date is not null")[0]
    checks.append(Check("C03", "Completeness", "Active pipeline studies with a primary completion date",
                        f"{_pct(100 * has_pc / n_act)} ({n_act - has_pc:,} without)", ">= 99%",
                        _grade(100 * has_pc / n_act, 99, 95), n_act - has_pc,
                        "Without a date a study cannot appear in the readouts-due view."))
    has_mesh = _one(con, """select count(distinct s.nct_id) from study s join stg_condition_mesh m using (nct_id)
                            where s.is_pipeline""")[0]
    checks.append(Check("C04", "Completeness", "Pipeline studies with a registry MeSH condition term",
                        f"{_pct(100 * has_mesh / n_pipe)}", "reported", "info", n_pipe - has_mesh,
                        "The rest are mostly healthy-volunteer Phase 1 studies. Area comes from the condition text, "
                        "then MeSH, then the molecule (see C15)."))

    # ------------------------------------------------------------ validity
    bad_id = _one(con, "select count(*) from stg_study where not regexp_matches(coalesce(nct_id, ''), '^NCT[0-9]{8}$')")[0]
    checks.append(Check("C05", "Validity", "Study IDs look like NCT plus 8 digits", f"{bad_id:,} do not",
                        "0 (any are quarantined)", "pass" if bad_id == 0 else "warn", bad_id, ""))
    unparsed = _one(con, """select count(*) from (
        select start_raw r from stg_study union all select pc_raw from stg_study union all select completion_raw
        from stg_study) t join map_date d on d.raw = t.r where t.r is not null and d.d is null""")[0]
    checks.append(Check("C06", "Validity", "Every date the registry gives can be read", f"{unparsed:,} cannot",
                        "0", "pass" if unparsed == 0 else "warn", unparsed,
                        "Dates come as a day, a month or a year; a month is stored as the first of the month and flagged."))
    incons = _one(con, "select count(*) from study where dates_inconsistent")[0]
    checks.append(Check("C07", "Validity", "Start is not after primary completion when both are ACTUAL",
                        f"{incons:,} studies", "0", "pass" if incons == 0 else "warn", incons,
                        "Kept and flagged, left out of timing measures if any appear."))
    known = "('COMPLETED','TERMINATED','RECRUITING','ACTIVE_NOT_RECRUITING','WITHDRAWN','NOT_YET_RECRUITING'," \
            "'NO_LONGER_AVAILABLE','APPROVED_FOR_MARKETING','AVAILABLE','ENROLLING_BY_INVITATION','UNKNOWN'," \
            "'SUSPENDED','TEMPORARILY_NOT_AVAILABLE','WITHHELD')"
    odd = _one(con, f"select count(*) from study where status not in {known}")[0]
    odd_phase = _one(con, "select count(*) from study s left join dim_phase p on p.label = s.phase where p.label is null")[0]
    checks.append(Check("C08", "Validity", "Status and phase are values the model knows",
                        f"{odd:,} unknown statuses, {odd_phase:,} unknown phases", "0",
                        "pass" if odd + odd_phase == 0 else "fail", odd + odd_phase, ""))
    badn = _one(con, "select count(*) from study where is_pipeline and enrollment_count is not null and "
                     "(enrollment_count < 0 or enrollment_count > 100000)")[0]
    big = _one(con, "select count(*) from study where not is_pipeline and enrollment_count > 100000")[0]
    checks.append(Check("C09", "Validity", "Pipeline enrollment is between 0 and 100,000", f"{badn:,} outside", "0",
                        "pass" if badn == 0 else "warn", badn,
                        f"{big:,} studies outside the pipeline exceed 100,000: observational database studies (one covers "
                        "188 million people). They are real, not errors, and are not drug-development studies."))

    # ------------------------------------------------------------ uniqueness
    dup = _one(con, "select count(*) - count(distinct nct_id) from study")[0]
    checks.append(Check("C10", "Uniqueness", "One row per study", f"{dup:,} duplicates", "0",
                        "pass" if dup == 0 else "fail", dup,
                        "The same study is found by several searches (Merck and MSD); it is kept once."))
    dupc = _one(con, "select count(*) - (select count(*) from (select distinct nct_id, iso3 from study_country)) "
                     "from study_country")[0]
    checks.append(Check("C11", "Uniqueness", "One row per study and country", f"{dupc:,} duplicates", "0",
                        "pass" if dupc == 0 else "fail", dupc, ""))

    # ------------------------------------------------------------ reconciliation
    per_term = dict(con.execute("select term_slug, count(*) from study_query group by 1").fetchall())
    bad_terms = [t["slug"] for t in manifest["terms"] if per_term.get(t["slug"]) != t["totalCount"]]
    checks.append(Check("C12", "Reconciliation", "Studies loaded per search equal the total the API announced",
                        f"{len(manifest['terms']) - len(bad_terms)} of {len(manifest['terms'])} searches match",
                        "every search equal", "pass" if not bad_terms else "fail", len(bad_terms),
                        f"{sum(t['totalCount'] for t in manifest['terms']):,} study rows over {len(manifest['terms'])} "
                        f"searches; API data as of {manifest['dataTimestamp_start']} (unchanged at the end of the download)."))
    fetched = _one(con, "select count(*) from stg_study")[0]
    in_scope = _one(con, "select count(*) from study")[0]
    quar = _one(con, "select count(*) from quarantine")[0]
    checks.append(Check("C13", "Reconciliation", "Every distinct study fetched is in scope or quarantined with a reason",
                        f"{fetched:,} fetched = {in_scope:,} in scope + {quar:,} quarantined",
                        "difference 0", "pass" if fetched == in_scope + quar else "fail", abs(fetched - in_scope - quar),
                        "Nothing is dropped silently."))
    msd_names = _one(con, "select count(*) from study where lead_name ilike '%Merck Sharp & Dohme%'")[0]
    live = None if offline else _live_count("Merck Sharp & Dohme")
    record = _read_live_record(manifest)
    note14 = "Studies whose lead name contains 'Merck Sharp & Dohme', including ArQule's. "
    if live is not None and live[1] == manifest["dataTimestamp_start"]:
        # The API still holds the data the snapshot was taken from: compare, and keep the evidence in the repository.
        total, ts = live
        status = "pass" if total == msd_names else "fail"
        _write_live_record(manifest, msd_names, total, ts)
        checks.append(Check("C14", "Reconciliation", "MSD study count equals a fresh count from the API",
                            f"{msd_names:,} in the warehouse vs {total:,} from the API (data date {ts[:10]})",
                            "equal on the same data date", status, abs(total - msd_names), note14))
    elif record and record["api_data_timestamp"] == manifest["dataTimestamp_start"]:
        # Offline, or the API has refreshed since: the API can no longer give the snapshot's own answer, so use the record
        # written when it could (data/snapshot/live_check.json) and say so.
        ok = record["api_count"] == record["warehouse_count"] == msd_names
        extra = "The API has refreshed since" if live is not None else "Not asked this run"
        checks.append(Check("C14", "Reconciliation", "MSD study count equals a fresh count from the API",
                            f"{msd_names:,} in the warehouse vs {record['api_count']:,} from the API on {record['checked_at'][:10]} "
                            f"(data date {record['api_data_timestamp'][:10]})", "equal on the same data date",
                            "pass" if ok else "fail", None if ok else abs(record["api_count"] - msd_names),
                            note14 + f"{extra}; this is the comparison recorded in data/snapshot/live_check.json when the API still "
                            "held the snapshot's data date."))
    else:
        checks.append(Check("C14", "Reconciliation", "MSD study count equals a fresh count from the API",
                            f"{msd_names:,} in the warehouse; no live comparison on this data date yet", "equal on the same data date",
                            "info", None, "Run `python -m tp.dq` (without --offline) on the snapshot's data date to record it."))

    # ------------------------------------------------------------ coverage
    area_ok = _one(con, "select count(*) from study where is_pipeline and is_active and area <> 'Unclassified'")[0]
    pct_area = 100 * area_ok / n_act
    checks.append(Check("C15", "Coverage", "Active pipeline studies assigned a therapeutic area",
                        f"{_pct(pct_area)} ({n_act - area_ok:,} Unclassified)", ">= 95%", _grade(pct_area, 95, 90),
                        n_act - area_ok,
                        "Text first, then MeSH, then the molecule's usual area. What no step can place stays "
                        "Unclassified, never spread across other areas."))
    mol_ok = _one(con, """select count(distinct s.nct_id) from study s join study_molecule m using (nct_id)
                          where s.is_pipeline and s.is_active""")[0]
    checks.append(Check("C16", "Coverage", "Active pipeline studies with a molecule key",
                        f"{_pct(100 * mol_ok / n_act)}", ">= 95%", _grade(100 * mol_ok / n_act, 95, 85), n_act - mol_ok,
                        "Placebo, saline, standard of care and similar comparators are not counted as molecules."))
    fams = _one(con, "select count(distinct family) from study_rx_link")[0]
    zero = [r[0] for r in con.execute("select family from rx_family where family not in "
                                      "(select family from study_rx_link) order by 1").fetchall()]
    checks.append(Check("C17", "Coverage", "Merck products in Rx Market Pulse with at least one MSD study",
                        f"{fams} of 14", "reported", "info", 14 - fams,
                        ("No study found by name, code or brand for: " + ", ".join(zero)) if zero else
                        "All 14 families match by molecule name, MK development code or brand name."))
    conf = _one(con, "select count(*) from study where is_pipeline and area_conflict")[0]
    checks.append(Check("C18", "Coverage", "Condition text and registry MeSH terms agree on the area",
                        f"{conf:,} of {n_pipe:,} pipeline studies disagree ({_pct(100 * conf / n_pipe)})", "< 3%",
                        "pass" if conf / n_pipe < 0.03 else "warn", conf,
                        "The registry's MeSH matching is automatic: a lung-cancer study that mentions PD-L1 is also "
                        "tagged with a Parkinson disease term. Text wins, so those disagreements do not change the area."))
    stop_n = _one(con, "select count(*) from study where is_pipeline and status_class = 'stopped'")[0]
    stop_u = _one(con, "select count(*) from study where is_pipeline and status_class = 'stopped' and stop_theme in "
                       "('Other', 'Not stated')")[0]
    checks.append(Check("C19", "Coverage", "Stopped pipeline studies whose reason fits a theme",
                        f"{_pct(100 * (stop_n - stop_u) / stop_n)} ({stop_u:,} are 'Not stated' or 'Other')", "reported",
                        "info", stop_u,
                        "The reason is free text and often reads 'see detailed description'. It is mapped by rules, so "
                        "treat the themes as indicative."))

    # ------------------------------------------------------------ harmonisation
    rules = sponsors.load_rules()
    terms = sponsors.search_terms()
    names = [r[0] for r in con.execute("select lead_name from map_sponsor").fetchall()]
    flagged = [sponsors.suspicious(n or "", sponsors.classify(n, rules), terms) for n in names]
    flagged = [f for f in flagged if f]
    checks.append(Check("C20", "Harmonisation", "No sponsor name that mentions a company falls through the rules",
                        f"{len(names):,} distinct names checked, {len(flagged)} unresolved", "0",
                        "pass" if not flagged else "fail", len(flagged),
                        "The search is full-text, so names such as 'University of Bristol' come back for 'Bristol'. "
                        "Each is set aside by an explicit rule; a name that mentions a company and matches no rule is a failure."))
    kgaa = _one(con, """select count(*) from study where grp = 'MSD' and (lead_name ilike '%KGaA%' or
                        lead_name ilike '%EMD Serono%' or lead_name ilike '%SpringWorks%')""")[0]
    kg_set_aside = _one(con, "select count(*) from quarantine where reason like '%Merck KGaA%'")[0]
    checks.append(Check("C21", "Harmonisation", "Merck KGaA is never counted as MSD",
                        f"{kgaa} in the MSD group; {kg_set_aside:,} Merck KGaA studies set aside", "0",
                        "pass" if kgaa == 0 else "fail", kgaa,
                        "Same name, different company: Merck KGaA of Darmstadt owns the name outside the US and Canada."))
    gained = dict(con.execute("select sponsor_kind, count(*) from study where grp = 'MSD' group by 1").fetchall())
    checks.append(Check("C22", "Harmonisation", "Studies MSD gains from the roll-up of acquired companies",
                        f"{gained.get('acquired', 0):,} of {sum(gained.values()):,} "
                        f"({_pct(100 * gained.get('acquired', 0) / sum(gained.values()))})", "reported", "info",
                        gained.get("acquired", 0),
                        "Cubist, Acceleron, Verona, Prometheus, ArQule and others, under their current owner as of "
                        "October 2026. Divested or spun-off units (Organon, Alcon, Sandoz) are excluded, not reassigned."))
    unm = _one(con, """select count(*) from stg_location l left join dim_country c on c.raw = l.country_raw
                       where l.country_raw is not null and c.raw is null""")[0]
    nocountry = _one(con, "select count(*) from stg_location where country_raw is null")[0]
    checks.append(Check("C23", "Harmonisation", "Every country spelling maps to an ISO code",
                        f"{unm:,} unmapped ({nocountry:,} sites list no country)", "0", "pass" if unm == 0 else "fail",
                        unm, "Spellings such as 'Turkey (Türkiye)' and 'Korea, Republic of' are mapped in data/ref/countries.csv."))

    # ------------------------------------------------------------ timeliness
    as_of = datetime.fromisoformat(manifest["dataTimestamp_start"]).date()
    age = (date.today() - as_of).days
    checks.append(Check("C24", "Timeliness", "Age of the data snapshot at build time",
                        f"{age} day{'' if age == 1 else 's'} (API data as of {as_of})", "<= 7 days", "pass" if age <= 7 else "warn", None,
                        "The snapshot is frozen on purpose so every number on the site and the CV agree."))
    stale = _one(con, f"""select count(*) from study where is_pipeline and is_active and
                         verified_date < date '{as_of.isoformat()}' - interval 12 month""")[0]
    overdue = _one(con, "select count(*) from study where is_pipeline and is_overdue")[0]
    checks.append(Check("C25", "Timeliness", "Active studies verified in the last 12 months",
                        f"{n_act - stale:,} of {n_act:,}; {overdue:,} are overdue (estimated primary completion already passed)",
                        "reported", "info", stale + overdue,
                        "An overdue study still says it will finish in a month that has gone: the forecast was not updated."))

    # waterfall: from search hits to studies in scope
    hits = sum(t["studies"] for t in manifest["terms"])
    wf = [("Rows returned by the searches", hits),
          ("Found by more than one search (counted once)", -(hits - fetched))]
    for label, n in con.execute("""select regexp_replace(reason, '^lead sponsor not in the twelve groups: ', '') as label,
                                          count(*) from quarantine group by 1 order by 2 desc""").fetchall():
        wf.append((f"Set aside: {label}", -n))
    wf.append(("Studies in scope", in_scope))
    waterfall = [{"stage": s, "studies": n} for s, n in wf]
    return checks, waterfall


def write(checks: list[Check], waterfall: list[dict]) -> None:
    S.MARTS.mkdir(parents=True, exist_ok=True)
    S.DOCS.mkdir(parents=True, exist_ok=True)
    with (S.MARTS / "dq_checks.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(asdict(checks[0])), lineterminator="\n")
        w.writeheader()
        w.writerows(asdict(c) for c in checks)
    with (S.MARTS / "dq_waterfall.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["stage", "studies"], lineterminator="\n")
        w.writeheader()
        w.writerows(waterfall)

    order = {"fail": 0, "warn": 1, "info": 2, "pass": 3}
    badge = {"pass": "PASS", "warn": "WARN", "fail": "FAIL", "info": "INFO"}
    lines = ["# Data-quality scorecard", "",
             "Generated by `python -m tp.dq` from the built warehouse. Nothing here is typed by hand.", "",
             f"**{sum(c.status == 'pass' for c in checks)} pass, {sum(c.status == 'warn' for c in checks)} warn, "
             f"{sum(c.status == 'fail' for c in checks)} fail, {sum(c.status == 'info' for c in checks)} info** "
             f"across {len(checks)} checks. Warnings are understood and explained, not ignored.", "",
             "| # | Dimension | Check | Result | Rule | Status | Studies touched |", "|---|---|---|---|---|---|---|"]
    for c in sorted(checks, key=lambda c: (order[c.status], c.id)):
        touched = "n/a" if c.studies is None else f"{c.studies:,}"
        lines.append(f"| {c.id} | {c.dimension} | {c.name} | {c.result} | {c.rule} | {badge[c.status]} | {touched} |")
    lines += ["", "## Notes", ""]
    for c in sorted(checks, key=lambda c: c.id):
        if c.note:
            lines.append(f"- **{c.id}**: {c.note}")
    lines += ["", "## From search hits to studies in scope", "", "| Stage | Studies |", "|---|---|"]
    for r in waterfall:
        lines.append(f"| {r['stage']} | {r['studies']:,} |")
    (S.DOCS / "data-quality-scorecard.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--offline", action="store_true", help="do not ask the live API (skips C14)")
    args = ap.parse_args(argv)
    con = connect()
    checks, waterfall = run(con, offline=args.offline)
    write(checks, waterfall)
    for c in checks:
        print(f"{c.id} {c.status.upper():<5} {c.name}: {c.result}")
    con.close()
    return 1 if any(c.status == "fail" for c in checks) else 0


if __name__ == "__main__":
    sys.exit(main())
