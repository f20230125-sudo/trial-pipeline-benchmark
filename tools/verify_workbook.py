"""Compare Excel's own results with an independent calculation.

    PYTHONPATH=src python tools/verify_workbook.py <probe.json>

tools/excel_probe.ps1 drives Excel through six input scenarios and writes what Excel's formulas returned. This script
recomputes the same scorecard from data/marts/mart_study_export.csv with plain Python (no shared code with
src/tp/workbook.py, no spreadsheet engine) and compares every number: counts exactly, percentiles and scores to 1e-6,
ranks and tiers exactly. It also checks the Checks sheet, the focus box, the area matrix and the expiring-revenue sheet.
"""

from __future__ import annotations

import csv
import json
import math
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GROUPS = ["MSD", "AbbVie", "AstraZeneca", "BMS", "GSK", "J&J", "Lilly", "Novartis", "Novo Nordisk", "Pfizer", "Roche",
          "Sanofi"]
PRESETS = {"Balanced": (30, 20, 20, 20, 10), "Near-term": (15, 15, 50, 10, 10), "Regional": (10, 10, 10, 10, 60)}
TOL = 1e-6


def load():
    with (ROOT / "data" / "marts" / "mart_study_export.csv").open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        r["start_year"] = int(r["start_year"]) if r["start_year"] else None
        r["end_year"] = int(r["end_year"]) if r["end_year"] else None
        r["pc"] = date.fromisoformat(r["pc_date"]) if r["pc_date"] else None
    with (ROOT / "data" / "ref" / "rx_merck_families.csv").open(encoding="utf-8", newline="") as fh:
        fam = [r for r in csv.DictReader(fh) if r["core_end"] and "2026-01-01" <= r["core_end"] <= "2028-12-31"]
    return rows, sorted(fam, key=lambda r: r["core_end"])


def stage_code(label: str) -> str | None:
    if label == "All clinical":
        return None
    return "Early" if label.startswith("Early") else ("Mid" if label.startswith("Mid") else "Late")


def add_months(d: date, m: int) -> date:
    idx = d.year * 12 + d.month - 1 + m
    return date(idx // 12, idx % 12 + 1, 1)


def pct_rank(values: list[float], x: float) -> float:
    """Excel PERCENTRANK.INC with 6 significant digits (truncated, as Excel does) for an x that is in the array."""
    n = len(values)
    below = sum(1 for v in values if v < x)
    return math.floor(below / (n - 1) * 1e6 + 1e-9) / 1e6


def scorecard(rows, s):
    area = None if s["area"] == "All areas" else s["area"]
    stage = stage_code(s["stage"])
    active_only = s["scope"] == "Active only"
    asof = date.fromisoformat(s["asof"])
    month_start = date(asof.year, asof.month, 1)
    window_end = add_months(month_start, int(s["window"]))
    y = asof.year

    def ok(r, use_stage=True, use_scope=True):
        if area and r["area"] != area:
            return False
        if use_stage and stage and r["stage"] != stage:
            return False
        if use_scope and active_only and r["active"] != "Yes":
            return False
        return True

    out = {}
    for g in GROUPS:
        mine = [r for r in rows if r["grp"] == g]
        size = sum(1 for r in mine if ok(r))
        recent = sum(1 for r in mine if ok(r, True, False) and r["real_start"] == "Yes" and r["start_year"] is not None
                     and y - 3 <= r["start_year"] <= y - 1)
        prior = sum(1 for r in mine if ok(r, True, False) and r["real_start"] == "Yes" and r["start_year"] is not None
                    and y - 6 <= r["start_year"] <= y - 4)
        readouts = sum(1 for r in mine if (not area or r["area"] == area) and r["stage"] == "Late" and r["active"] == "Yes"
                       and r["pc_type"] == "ESTIMATED" and r["pc"] is not None and month_start <= r["pc"] < window_end)
        term = sum(1 for r in mine if ok(r, True, False) and r["status"] == "TERMINATED" and r["end_year"] is not None
                   and 2016 <= r["end_year"] <= 2025)
        comp = sum(1 for r in mine if ok(r, True, False) and r["status"] == "COMPLETED" and r["end_year"] is not None
                   and 2016 <= r["end_year"] <= 2025)
        gulf = sum(1 for r in mine if ok(r) and r["gcc"] == "Yes")
        out[g] = {"size": size, "recent": recent, "prior": prior, "mom": recent / max(prior, 1), "readouts": readouts,
                  "term": term, "comp": comp, "rate": None if term + comp < 10 else term / (term + comp), "gulf": gulf,
                  "share": 0 if size == 0 else gulf / size}
    sizes = [out[g]["size"] for g in GROUPS]
    moms = [out[g]["mom"] for g in GROUPS]
    reads = [out[g]["readouts"] for g in GROUPS]
    rates = [out[g]["rate"] for g in GROUPS if out[g]["rate"] is not None]
    shares = [out[g]["share"] for g in GROUPS]
    w = PRESETS.get(s["preset"], tuple(s["custom"]))
    for g in GROUPS:
        o = out[g]
        o["p"] = [pct_rank(sizes, o["size"]), pct_rank(moms, o["mom"]), pct_rank(reads, o["readouts"]),
                  0.5 if o["rate"] is None else 1 - pct_rank(rates, o["rate"]), pct_rank(shares, o["share"])]
        raw = sum(p * wi for p, wi in zip(o["p"], w)) / sum(w)
        o["score"] = math.floor(raw * 1e9 + 0.5) / 1e9  # the workbook rounds to 9 decimals so equal scores are equal
    for i, g in enumerate(GROUPS):
        s_i = out[g]["score"]
        rank = 1 + sum(1 for h in GROUPS if out[h]["score"] > s_i) + sum(1 for h in GROUPS[:i + 1] if h != g and out[h]["score"] == s_i)
        out[g]["rank"] = rank
        out[g]["tier"] = "A" if rank <= 4 else ("B" if rank <= 8 else "C")
    return out, w


def main(path: str) -> int:
    probe = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    rows, fam = load()
    problems: list[str] = []
    for sc in probe:
        s = sc["inputs"]
        mine, weights = scorecard(rows, s)
        tag = sc["id"]
        # weights in use
        if [round(x) for x in sc["weights"]] != list(PRESETS.get(s["preset"], s["custom"])):
            problems.append(f"{tag}: weights in use {sc['weights']}")
        for i, g in enumerate(GROUPS):
            x = sc["rows"][i]
            m = mine[g]
            if x[0] != g:
                problems.append(f"{tag}: row {i} is {x[0]}, expected {g}")
                continue
            exact = {"size": x[1], "recent": x[2], "prior": x[3], "readouts": x[5], "term": x[6], "comp": x[7], "gulf": x[9]}
            for k, v in exact.items():
                if int(v) != m[k]:
                    problems.append(f"{tag} {g} {k}: excel {v} vs python {m[k]}")
            if abs(x[4] - m["mom"]) > TOL:
                problems.append(f"{tag} {g} momentum: {x[4]} vs {m['mom']}")
            if m["rate"] is None:
                if x[8] != "n/a":
                    problems.append(f"{tag} {g} termination rate should be n/a, got {x[8]}")
            elif abs(float(x[8]) - m["rate"]) > TOL:
                problems.append(f"{tag} {g} termination rate: {x[8]} vs {m['rate']}")
            if abs(x[10] - m["share"]) > TOL:
                problems.append(f"{tag} {g} gulf share: {x[10]} vs {m['share']}")
            for j in range(5):
                if abs(x[11 + j] - m["p"][j]) > TOL:
                    problems.append(f"{tag} {g} percentile {j}: {x[11 + j]} vs {m['p'][j]}")
            if abs(x[16] - m["score"]) > TOL:
                problems.append(f"{tag} {g} score: {x[16]} vs {m['score']}")
            if int(x[17]) != m["rank"]:
                problems.append(f"{tag} {g} rank: excel {x[17]} vs python {m['rank']}")
            if x[18] != m["tier"]:
                problems.append(f"{tag} {g} tier: {x[18]} vs {m['tier']}")
        # focus box
        f = s["focus"]
        peers = sorted(mine[g]["size"] for g in GROUPS if g != f)
        med = peers[5]  # the median of 11 peers is the 6th value
        if int(sc["focus_rank"]) != mine[f]["rank"]:
            problems.append(f"{tag}: focus rank {sc['focus_rank']} vs {mine[f]['rank']}")
        if sc["focus_tier"] != mine[f]["tier"]:
            problems.append(f"{tag}: focus tier")
        if int(sc["focus_studies"]) != mine[f]["size"] or abs(sc["peer_median"] - med) > TOL or abs(sc["gap"] - (mine[f]["size"] - med)) > TOL:
            problems.append(f"{tag}: focus box {sc['focus_studies']}, {sc['peer_median']}, {sc['gap']}")
        # checks sheet
        if sc["overall"] != "ALL OK" or any(c != "OK" for c in sc["checks"]):
            problems.append(f"{tag}: checks sheet says {sc['checks']} / {sc['overall']}")
        # area matrix: the sum over the 17 areas and the total column
        for i, g in enumerate(GROUPS):
            stage = stage_code(s["stage"])
            tot = sum(1 for r in rows if r["grp"] == g and (not stage or r["stage"] == stage)
                      and (s["scope"] != "Active only" or r["active"] == "Yes"))
            if int(sc["matrix"][i][17]) != tot:
                problems.append(f"{tag} {g} matrix total: excel {sc['matrix'][i][16]} vs python {tot}")
        # expiring revenue
        horizon = int(s["horizon"])
        for name, spend, msd_late, peer_med, rank in sc["expiring"]:
            risk = sum(int(r["spend_2025"]) for r in fam if r["area"] == name and int(r["core_end"][:4]) <= horizon)
            counts = {g: sum(1 for r in rows if r["grp"] == g and r["area"] == name and r["stage"] == "Late" and r["active"] == "Yes")
                      for g in GROUPS}
            peers = sorted(v for g, v in counts.items() if g != "MSD")
            pm = peers[5]
            rk = 1 + sum(1 for g, v in counts.items() if g != "MSD" and v > counts["MSD"])
            if abs(spend - risk) > 0.5 or int(msd_late) != counts["MSD"] or abs(peer_med - pm) > TOL or int(rank) != rk:
                problems.append(f"{tag} expiring {name}: excel {spend},{msd_late},{peer_med},{rank} vs python {risk},{counts['MSD']},{pm},{rk}")
        print(f"{tag}: {s['focus']:<12} {s['area']:<28} {s['stage']:<16} {s['scope']:<13} {s['window']:>2}m {s['preset']:<10} "
              f"-> focus rank {mine[f]['rank']} tier {mine[f]['tier']}, {mine[f]['size']} studies")
    if problems:
        print(f"\n{len(problems)} DIFFERENCES")
        for p in problems[:40]:
            print("  " + p)
        return 1
    print(f"\n{len(probe)} scenarios OK: every count, percentile, score, rank, tier, matrix total and expiring-revenue figure "
          f"from Excel's own formulas equals the independent Python calculation (12 companies x 20 columns x {len(probe)} scenarios)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
