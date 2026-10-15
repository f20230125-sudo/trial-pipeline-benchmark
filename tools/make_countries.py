"""Write data/ref/countries.csv: every country spelling that occurs in the downloaded sites, mapped to an ISO code.

Run once after staging (needs `pip install pycountry`, which is only used here, not by the pipeline):
    PYTHONPATH=src python tools/make_countries.py
The CSV is committed, so the build itself needs nothing but the CSV. Unresolved spellings are printed and exit 1:
add them to ALIASES below and run again.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import duckdb
import pycountry

ROOT = Path(__file__).resolve().parents[1]
GCC = {"ARE", "SAU", "QAT", "KWT", "BHR", "OMN"}
# World Bank "Middle East and North Africa"; the GCC six are inside it.
MENA = GCC | {"JOR", "LBN", "ISR", "PSE", "SYR", "IRQ", "IRN", "YEM", "EGY", "LBY", "TUN", "DZA", "MAR", "DJI"}

# How ClinicalTrials.gov spells countries that pycountry names differently.
ALIASES = {
    "Korea, Republic of": "KOR", "Korea, Democratic People's Republic of": "PRK", "South Korea": "KOR",
    "Taiwan": "TWN", "Russia": "RUS", "Russian Federation": "RUS", "Turkey (Türkiye)": "TUR", "Türkiye": "TUR",
    "Turkey": "TUR", "Czechia": "CZE", "Czech Republic": "CZE", "Iran, Islamic Republic of": "IRN", "Iran": "IRN",
    "Hong Kong": "HKG", "Macau": "MAC", "Macao": "MAC", "Palestinian Territory, Occupied": "PSE",
    "Palestine, State of": "PSE", "Palestine": "PSE", "West Bank and Gaza": "PSE",
    "Congo, The Democratic Republic of the": "COD", "Congo, Democratic Republic of the": "COD",
    "Congo, Republic of the": "COG", "Congo": "COG", "Kosovo": "XKX", "Vietnam": "VNM", "Viet Nam": "VNM",
    "Moldova, Republic of": "MDA", "Moldova": "MDA", "Syrian Arab Republic": "SYR", "Syria": "SYR",
    "Tanzania, United Republic of": "TZA", "Tanzania": "TZA", "Bolivia": "BOL", "Venezuela": "VEN",
    "Brunei": "BRN", "Laos": "LAO", "Lao People's Democratic Republic": "LAO", "North Macedonia": "MKD",
    "Macedonia, The Former Yugoslav Republic of": "MKD", "Macedonia": "MKD", "Cote D'Ivoire": "CIV",
    "Côte d'Ivoire": "CIV", "Ivory Coast": "CIV", "United Kingdom": "GBR", "United States": "USA",
    "Virgin Islands (U.S.)": "VIR", "Virgin Islands, U.S.": "VIR", "Reunion": "REU", "Réunion": "REU",
    "Curacao": "CUW", "Curaçao": "CUW", "Saint Martin": "MAF", "Swaziland": "SWZ", "Eswatini": "SWZ",
    "Cape Verde": "CPV", "East Timor": "TLS", "Timor-Leste": "TLS", "Burma": "MMR", "Myanmar": "MMR",
    "Gambia": "GMB", "Bahamas": "BHS", "Falkland Islands (Malvinas)": "FLK", "Guernsey": "GGY", "Jersey": "JEY",
    "Isle of Man": "IMN", "Gibraltar": "GIB", "Faroe Islands": "FRO", "Greenland": "GRL", "Netherlands Antilles": "ANT",
    "Serbia and Montenegro": "SCG", "Yugoslavia": "YUG", "Czechoslovakia": "CSK", "Soviet Union": "SUN",
    "Saint Helena": "SHN", "Holy See (Vatican City State)": "VAT", "Saint Pierre and Miquelon": "SPM",
    "Micronesia, Federated States of": "FSM", "Western Sahara": "ESH", "Guadeloupe": "GLP", "Martinique": "MTQ",
    "French Guiana": "GUF", "Mayotte": "MYT", "New Caledonia": "NCL", "French Polynesia": "PYF", "Puerto Rico": "PRI",
    "Guam": "GUM", "American Samoa": "ASM", "Aruba": "ABW", "Bermuda": "BMU", "Cayman Islands": "CYM",
    "Côte d’Ivoire": "CIV", "Democratic Republic of the Congo": "COD", "Federal Republic of Yugoslavia": "YUG",
    "The Bahamas": "BHS", "The Gambia": "GMB", "Virgin Islands": "VIR",
}


def resolve(raw: str) -> tuple[str, str] | None:
    code = ALIASES.get(raw)
    if code in ("XKX", "ANT", "SCG", "YUG", "CSK", "SUN"):  # not in the current ISO list
        return code, raw.split(",")[0].split(" (")[0]
    if code:
        c = pycountry.countries.get(alpha_3=code)
        return (code, c.name) if c else (code, raw)
    try:
        c = pycountry.countries.lookup(raw)
        return c.alpha_3, c.name
    except LookupError:
        return None


def main() -> int:
    con = duckdb.connect(str(ROOT / "data" / "warehouse" / "tp.duckdb"), read_only=True)
    raws = [r[0] for r in con.execute(
        "select country_raw from stg_location where country_raw is not null "
        "union select country_raw from stg_removed_country where country_raw is not null order by 1").fetchall()]
    rows, bad = [], []
    for raw in raws:
        hit = resolve(raw)
        if hit is None:
            bad.append(raw)
            continue
        iso3, name = hit
        rows.append((raw, iso3, name, str(iso3 in GCC).lower(), str(iso3 in MENA).lower()))
    out = ROOT / "data" / "ref" / "countries.csv"
    with out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["raw", "iso3", "name", "is_gcc", "is_mena"])
        w.writerows(rows)
    print(f"{len(rows)} of {len(raws)} spellings mapped; wrote {out}")
    if bad:
        print("unresolved (add to ALIASES):", bad)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
