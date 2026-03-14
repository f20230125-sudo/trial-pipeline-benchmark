"""Tie MSD's trials to Merck's products in Rx Market Pulse (the sibling project, rx-analytics).

data/ref/rx_merck_families.csv is a committed extract of rx-analytics/dashboard/public/data/products.json (the 14 Merck
product families with their 2025 Medicaid spend and, from the FDA Orange Book, when protection ends). Each family is
matched to trials by the molecule's name, Merck's development code and the brand name, searched in the intervention
names, their other names and the study title.

    python -m tp.rx_link --refresh      # rewrite the CSV from rx-analytics (only needed if Rx Market Pulse changes)
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from . import sources as S

PRODUCTS_JSON = Path(r"D:\claude-workspace\rx-analytics\dashboard\public\data\products.json")
OUT = S.REF / "rx_merck_families.csv"

# family (as named in Rx Market Pulse) -> (franchise label, regex over lower-case text).
# One franchise can span families (Januvia and Janumet are both sitagliptin).
FRANCHISES: dict[str, tuple[str, str]] = {
    "KEYTRUDA": ("pembrolizumab", r"pembrolizumab|mk-3475|keytruda"),
    "JANUVIA": ("sitagliptin", r"sitagliptin|mk-0431|januvia|janumet"),
    "JANUMET": ("sitagliptin", r"sitagliptin|mk-0431|januvia|janumet"),
    "WINREVAIR": ("sotatercept", r"sotatercept|mk-7962|ace-011|winrevair"),
    "STEGLATRO": ("ertugliflozin", r"ertugliflozin|mk-8835|steglatro|segluromet|steglujan"),
    "ISENTRESS": ("raltegravir", r"raltegravir|mk-0518|isentress"),
    "PREVYMIS": ("letermovir", r"letermovir|mk-8228|aic246|prevymis"),
    "WELIREG": ("belzutifan", r"belzutifan|mk-6482|pt2977|welireg"),
    "BRIDION": ("sugammadex", r"sugammadex|mk-8616|bridion"),
    "PIFELTRO": ("doravirine", r"doravirine|mk-1439|pifeltro|delstrigo"),
    "DELSTRIGO": ("doravirine", r"doravirine|mk-1439|pifeltro|delstrigo"),
    "BELSOMRA": ("suvorexant", r"suvorexant|mk-4305|belsomra"),
    "DIFICID": ("fidaxomicin", r"fidaxomicin|opt-80|dificid"),
    "ZERBAXA": ("ceftolozane", r"ceftolozane|mk-7625|zerbaxa"),
}

COLUMNS = ["family", "franchise", "area", "spend_2025", "status", "core_end", "substance_end", "last_end",
           "molecule_regex"]


def refresh(src: Path = PRODUCTS_JSON, out: Path = OUT) -> int:
    rows = json.loads(src.read_text(encoding="utf-8"))["owners"]["Merck (MSD)"]
    missing = {r["family"] for r in rows} - set(FRANCHISES)
    if missing:
        raise SystemExit(f"no franchise regex for Rx families: {sorted(missing)}; add them to FRANCHISES")
    with out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(COLUMNS)
        for r in rows:
            franchise, rx = FRANCHISES[r["family"]]
            w.writerow([r["family"], franchise, r["area"], round(r["spend"][-1]), r["status"], r["coreEnd"] or "",
                        r["substanceEnd"] or "", r["lastEnd"] or "", rx])
    return len(rows)


def load(path: Path = OUT) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args(argv)
    if args.refresh:
        print(f"wrote {refresh()} Merck families to {OUT}")
    else:
        for r in load():
            print(f"{r['family']:12s} {r['franchise']:14s} {r['area']:30s} ${int(r['spend_2025']) / 1e6:7.1f}M  core {r['core_end'] or '-'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
