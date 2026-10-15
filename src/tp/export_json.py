"""Write the JSON the dashboard reads, and headline.json: every number the README and the CV quote.

    python -m tp.build && python -m tp.dq && python -m tp.forecast && python -m tp.export_json

Everything here is read from the warehouse and the marts; nothing is typed by hand, so a number in the README or the CV
can be found in headline.json and traced to a mart. The files go to dashboard/public/data (committed, so the dashboard
builds without the warehouse).
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from . import areas, phases, sources as S
from .build import connect

OUT = S.ROOT / "dashboard" / "public" / "data"


def _clean(v):
    if isinstance(v, (date, datetime)):
        return v.isoformat()[:10]
    if isinstance(v, Decimal):
        return float(v)
    return v


def rows(con, sql: str) -> list[dict]:
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    return [{c: _clean(v) for c, v in zip(cols, r)} for r in cur.fetchall()]


def read_csv(name: str) -> list[dict]:
    out = []
    with (S.MARTS / name).open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            row = {}
            for k, v in r.items():
                if v == "":
                    row[k] = None
                elif v in ("True", "False"):
                    row[k] = v == "True"
                else:
                    try:
                        row[k] = int(v)
                    except ValueError:
                        try:
                            row[k] = float(v)
                        except ValueError:
                            row[k] = v
            out.append(row)
    return out


def write(name: str, data) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def count_tests() -> int | None:
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", "-c", str(S.ROOT / "pytest.ini"), str(S.ROOT / "tests"),
                            "--collect-only", "-q"], capture_output=True, text=True, timeout=180)
        last = [ln for ln in r.stdout.splitlines() if "collected" in ln or " tests" in ln]
        return int(last[-1].split()[0]) if last else None
    except Exception:
        return None


def build_headline(con, manifest: dict) -> dict:
    g = {r["grp"]: r for r in rows(con, "select * from mart_group_summary")}
    conc = {r["grp"]: r for r in rows(con, "select * from mart_concentration")}
    msd, az = g["MSD"], g["AstraZeneca"]
    top = rows(con, "select * from mart_top_molecules where grp = 'MSD' order by rank")
    second = sorted((r for r in conc.values() if r["grp"] != "MSD"), key=lambda r: -r["share_pct"])[0]
    eco = {r["category"]: r for r in rows(con, "select * from mart_pembrolizumab_ecosystem")}
    eco_total = sum(r["studies"] for r in eco.values())
    rd = {r["grp"]: r for r in rows(con, "select * from mart_readouts_summary")}
    gulf = {r["grp"]: r for r in rows(con, "select * from mart_gulf_summary")}
    term = {r["grp"]: r for r in rows(con, "select * from mart_termination")}
    gain = {r["grp"]: r for r in rows(con, "select * from mart_harmonisation_gain")}
    exp_rows = rows(con, "select * from mart_expiring_revenue order by spend_2025_at_risk desc")
    exp = exp_rows[0] if exp_rows else {}
    checks = read_csv("dq_checks.csv")
    fc = {(r["segment"], r["year"]): r for r in read_csv("forecast.csv")}
    back = [r for r in read_csv("forecast_backtest.csv") if r["segment"] == "MSD" and r["chosen"]]
    peers_sorted = sorted((r for r in gulf.values() if r["grp"] != "MSD"), key=lambda r: -r["gcc_studies"])
    msd_gulf_rank = 1 + sum(1 for r in gulf.values() if r["gcc_share_pct"] < gulf["MSD"]["gcc_share_pct"])
    stat = lambda sql: con.execute(sql).fetchone()[0]
    fetched = stat("select count(*) from stg_study")
    in_scope = stat("select count(*) from study")
    quarantined = stat("select count(*) from quarantine")
    kgaa = stat("select count(*) from quarantine where reason like '%Merck KGaA%'")
    window_end = stat("select (date_trunc('month', date '%s') + interval 24 month - interval 1 day)::date" % manifest["dataTimestamp_start"][:10])
    families = rows(con, "select family from mart_msd_franchise where studies_all > 0")
    sponsor_names = stat("select count(*) from map_sponsor")
    return {
        "snapshot": {
            "api_data_timestamp": manifest["dataTimestamp_start"],
            "as_of": manifest["dataTimestamp_start"][:10],
            "fetched_at": manifest["fetched_at"],
            "searches": len(manifest["terms"]),
            "api_rows": sum(t["studies"] for t in manifest["terms"]),
            "distinct_studies_fetched": fetched,
            "studies_in_scope": in_scope,
            "studies_quarantined": quarantined,
            "distinct_sponsor_names": sponsor_names,
            "groups": 12,
            "peers": 11,
        },
        "quality": {
            "checks": len(checks),
            "pass": sum(1 for c in checks if c["status"] == "pass"),
            "warn": sum(1 for c in checks if c["status"] == "warn"),
            "fail": sum(1 for c in checks if c["status"] == "fail"),
            "info": sum(1 for c in checks if c["status"] == "info"),
            "tests": count_tests(),
        },
        "harmonisation": {
            "msd_in_scope": msd["studies_in_scope"],
            "msd_parent_studies": msd["parent_studies"],
            "msd_acquired_studies": msd["acquired_studies"],
            "msd_acquired_pct": gain["MSD"]["gain_pct"],
            "merck_kgaa_set_aside": kgaa,
            "biggest_roll_up_gain": max(gain.values(), key=lambda r: r["gain_pct"])["grp"],
            "biggest_roll_up_gain_pct": max(r["gain_pct"] for r in gain.values()),
        },
        "pipeline": {
            "msd_active_pipeline": msd["active_pipeline"],
            "msd_active_pipeline_rank": msd["active_pipeline_rank"],
            "msd_active_late": msd["active_late"],
            "msd_active_late_rank": msd["active_late_rank"],
            "largest_active_pipeline_group": az["grp"] if az["active_pipeline_rank"] == 1 else None,
            "largest_active_pipeline": az["active_pipeline"],
        },
        "concentration": {
            "msd_top_molecule": conc["MSD"]["top_molecule"],
            "msd_top_molecule_studies": conc["MSD"]["top_studies"],
            "msd_studies_p23": conc["MSD"]["studies_p23"],
            "msd_share_pct": conc["MSD"]["share_pct"],
            "msd_concentration_rank": conc["MSD"]["concentration_rank"],
            "second_group": second["grp"],
            "second_molecule": second["top_molecule"],
            "second_share_pct": second["share_pct"],
            "msd_top3": [{"molecule": r["molecule"], "studies": r["studies"], "share_pct": r["share_pct"]} for r in top[:3]],
            "pembrolizumab_active_studies_all_sponsors": eco_total,
            "pembrolizumab_msd_led": eco.get("MSD", {}).get("studies"),
            "pembrolizumab_msd_led_pct": eco.get("MSD", {}).get("share_pct"),
            "msd_keytruda_linked_active_pipeline": stat("select active_pipeline from mart_msd_franchise where family = 'KEYTRUDA'"),
            "merck_families_matched": len(families),
        },
        "expiring_revenue": {
            "top_area": exp.get("area"),
            "top_families": exp.get("families"),
            "top_spend_2025": exp.get("spend_2025_at_risk"),
            "top_msd_active_late": exp.get("msd_active_late"),
            "top_peer_median_active_late": exp.get("peer_median_active_late"),
            "total_spend_at_risk_2026_28": sum(r["spend_2025_at_risk"] for r in exp_rows),
        },
        "readouts": {
            "window": f"{manifest['dataTimestamp_start'][:7]} to {window_end}",
            "msd_readouts_24m": rd["MSD"]["readouts_24m"],
            "azn_readouts_24m": rd["AstraZeneca"]["readouts_24m"],
            "max_readouts_24m_group": max(rd.values(), key=lambda r: r["readouts_24m"])["grp"],
            "msd_overdue_late": rd["MSD"]["overdue_late"],
            "overdue_active_all_groups": sum(r["overdue_late"] for r in rd.values()),
        },
        "starts": {
            "msd_starts_2025": stat("select studies from mart_starts_year where grp = 'MSD' and year = 2025"),
            "msd_starts_2026_ytd": stat("select studies from mart_starts_year where grp = 'MSD' and year = 2026"),
            "peer_median_starts_2025": stat("select median_studies from mart_starts_peer_median where year = 2025"),
            "msd_termination_rate_pct": term["MSD"]["termination_rate_pct"],
            "peer_median_termination_rate_pct": stat(
                "select median(termination_rate_pct) from mart_termination where grp <> 'MSD'"),
            "forecast_method": back[0]["method"] if back else None,
            "forecast_mape_pct": back[0]["mape_pct"] if back else None,
            "msd_forecast_2026": fc[("MSD", 2026)]["studies"],
            "msd_forecast_2026_low": fc[("MSD", 2026)]["low"],
            "msd_forecast_2026_high": fc[("MSD", 2026)]["high"],
        },
        "gulf": {
            "msd_gcc_pipeline_studies": gulf["MSD"]["gcc_studies"],
            "msd_gcc_share_pct": gulf["MSD"]["gcc_share_pct"],
            "msd_gcc_rank_lowest_share": msd_gulf_rank,
            "msd_removed_gcc_studies": gulf["MSD"]["removed_gcc_studies"],
            "azn_gcc_pipeline_studies": gulf["AstraZeneca"]["gcc_studies"],
            "max_gcc_group": peers_sorted[0]["grp"],
            "max_gcc_studies": peers_sorted[0]["gcc_studies"],
            "by_group": {r["grp"]: r["gcc_studies"] for r in gulf.values()},
        },
    }


def main() -> int:
    manifest = json.loads(S.MANIFEST.read_text(encoding="utf-8"))
    con = connect(read_only=True)
    groups = rows(con, "select grp, short_name, is_focus, sort_order from dim_group order by sort_order")
    write("meta.json", {
        "built": date.today().isoformat(),
        "asOf": manifest["dataTimestamp_start"][:10],
        "dataTimestamp": manifest["dataTimestamp_start"],
        "api": S.STUDIES_URL,
        "groups": groups,
        "areas": areas.AREAS,
        "phases": [p for p in phases.LABELS if p not in ("Phase 4", "Not applicable", "Not stated")],
        "sources": [
            {"name": "ClinicalTrials.gov API v2", "by": "US National Library of Medicine",
             "use": "every study led by one of 12 companies, plus every pembrolizumab study (all sponsors)"},
            {"name": "Rx Market Pulse", "by": "sibling project, from CMS State Drug Utilization Data and the FDA Orange Book",
             "use": "Merck 2025 Medicaid spend by product and when protection ends"},
        ],
    })
    write("overview.json", {
        "summary": rows(con, "select * from mart_group_summary"),
        "phase": rows(con, "select * from mart_pipeline_phase"),
        "area": rows(con, "select * from mart_area_mix"),
    })
    write("concentration.json", {
        "top": rows(con, "select * from mart_top_molecules"),
        "concentration": rows(con, "select * from mart_concentration"),
        "ecosystem": rows(con, "select * from mart_pembrolizumab_ecosystem"),
    })
    write("revenue.json", {
        "expiring": rows(con, "select * from mart_expiring_revenue"),
        "franchise": rows(con, "select * from mart_msd_franchise"),
    })
    write("readouts.json", {
        "quarter": rows(con, "select * from mart_readouts_quarter"),
        "summary": rows(con, "select * from mart_readouts_summary"),
        "msd": rows(con, "select * from mart_readouts_msd"),
    })
    write("starts.json", {
        "byGroup": rows(con, "select * from mart_starts_year"),
        "peerMedian": rows(con, "select * from mart_starts_peer_median"),
        "termination": rows(con, "select * from mart_termination"),
        "stopThemes": rows(con, "select * from mart_stop_themes"),
        "forecast": read_csv("forecast.csv"),
        "backtest": read_csv("forecast_backtest.csv"),
    })
    write("gulf.json", {
        "summary": rows(con, "select * from mart_gulf_summary"),
        "country": rows(con, "select * from mart_gulf_country"),
        "removed": rows(con, "select * from mart_gulf_removed"),
    })
    write("quality.json", {
        "checks": read_csv("dq_checks.csv"),
        "waterfall": read_csv("dq_waterfall.csv"),
        "gain": rows(con, "select * from mart_harmonisation_gain"),
    })
    write("msd_active.json", rows(con, "select * from mart_msd_active"))
    headline = build_headline(con, manifest)
    write("headline.json", headline)
    con.close()
    print(f"wrote {len(list(OUT.glob('*.json')))} files to {OUT}")
    print(json.dumps(headline, indent=1, ensure_ascii=False)[:6000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
