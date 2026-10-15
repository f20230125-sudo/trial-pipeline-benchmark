"""Who is who among the lead sponsors.

ClinicalTrials.gov's query.lead is a full-text search, so asking for "Roche" also returns people named Roche, asking for
"Bristol" returns the University of Bristol, and asking for "Merck" returns Merck KGaA, which is a different company from
Merck & Co. (MSD). So the download is deliberately wide and the decision about who a study belongs to is made here, by an
ordered list of rules in data/ref/sponsor_rules.csv.

Rules are tried in order and the first match wins:
  parent    the company's own legal entities (Pfizer Inc., Merck Sharp & Dohme LLC ...)
  acquired  a company bought by one of the twelve; counted for the buyer, under the owner as of October 2026
  excluded  not part of the group: a namesake (Merck KGaA), a divested or spun-off unit (Organon, Sandoz, Alcon),
            or an academic, hospital or person that the full-text search happened to return
Divested units are excluded, not reassigned. Acquisitions registered under names outside the query list are missed;
the README says so.

Usage:  python -m tp.sponsors --census     (exit 1 if a name that mentions a company falls through to the catch-all)
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from . import sources as S

GROUPS = ["MSD", "Pfizer", "AstraZeneca", "Novartis", "Roche", "BMS", "Lilly", "Novo Nordisk", "AbbVie", "GSK",
          "Sanofi", "J&J"]
KINDS = {"parent", "acquired", "excluded"}
CATCH_ALL = "Other sponsor"  # label for the last rule: names the full-text search returned that belong to nobody here


@dataclass(frozen=True)
class Rule:
    order: int
    pattern: re.Pattern
    group: str  # one of GROUPS, or the label of an excluded name
    kind: str
    note: str

    @property
    def in_scope(self) -> bool:
        return self.kind in ("parent", "acquired")


@dataclass(frozen=True)
class Match:
    group: str
    kind: str
    order: int
    note: str

    @property
    def in_scope(self) -> bool:
        return self.kind in ("parent", "acquired")


def load_rules(path: Path = S.REF / "sponsor_rules.csv") -> list[Rule]:
    rules: list[Rule] = []
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            kind = row["kind"].strip()
            group = row["group"].strip()
            if kind not in KINDS:
                raise ValueError(f"sponsor rule {row['order']}: unknown kind {kind!r}")
            if kind != "excluded" and group not in GROUPS:
                raise ValueError(f"sponsor rule {row['order']}: {group!r} is not one of the twelve groups")
            rules.append(Rule(int(row["order"]), re.compile(row["pattern"], re.IGNORECASE), group, kind,
                              row["note"].strip()))
    orders = [r.order for r in rules]
    if orders != sorted(set(orders)):
        raise ValueError("sponsor rules must have unique, increasing order numbers")
    if not rules or rules[-1].group != CATCH_ALL:
        raise ValueError("the last sponsor rule must be the catch-all")
    return rules


def classify(name: str | None, rules: list[Rule]) -> Match:
    """First matching rule. A missing name is not a sponsor of anyone."""
    text = (name or "").strip()
    for r in rules:
        if r.pattern.search(text):
            return Match(r.group, r.kind, r.order, r.note)
    return Match(CATCH_ALL, "excluded", -1, "no rule")


def search_terms() -> dict[str, list[str]]:
    """The words used to fetch each group, from data/ref/sponsor_queries.csv (lead queries only)."""
    out: dict[str, list[str]] = {}
    with (S.REF / "sponsor_queries.csv").open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if r["param"].strip() == "lead":
                out.setdefault(r["group"].strip(), []).append(r["term"].strip())
    return out


def suspicious(name: str, match: Match, terms: dict[str, list[str]]) -> str | None:
    """A name that went to the catch-all but contains a company's search word. That is how a missing alias hides."""
    if match.order != -1 and match.group != CATCH_ALL:
        return None
    for group, words in terms.items():
        for w in words:
            if len(w) >= 3 and re.search(rf"\b{re.escape(w)}\b", name, re.IGNORECASE):
                return f"{name!r} mentions {w!r} ({group}) but matched only the catch-all"
    return None


def lead_name_census(raw_dir: Path = S.RAW) -> list[tuple[str, int]]:
    """Every distinct lead-sponsor name in the downloaded pages with the number of distinct studies."""
    import duckdb

    files = (raw_dir.as_posix().rstrip("/")) + "/*/page_*.json"
    con = duckdb.connect()
    con.execute("set threads=4")
    # The largest page is 7.4 MB. maximum_object_size reserves a buffer of that size per thread, so a huge value
    # (it was 200 MB at first) runs the machine out of memory on 71 pages; 32 MB leaves room to grow.
    return con.execute(
        """
        select j->>'$.protocolSection.sponsorCollaboratorsModule.leadSponsor.name' as lead,
               count(distinct j->>'$.protocolSection.identificationModule.nctId') as n
        from (select unnest(studies) as j from read_json(?, columns={studies: 'JSON[]'},
                                                         maximum_object_size=33554432))
        group by 1 order by 2 desc, 1
        """,
        [files],
    ).fetchall()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--census", action="store_true", help="classify every fetched lead-sponsor name")
    ap.add_argument("--show", default="", help="comma-separated kinds or groups to list in full")
    args = ap.parse_args(argv)
    if not args.census:
        ap.print_help()
        return 0
    rules = load_rules()
    terms = search_terms()
    census = lead_name_census()
    by_label: dict[tuple[str, str], list[tuple[str, int]]] = {}
    problems: list[str] = []
    for name, n in census:
        m = classify(name, rules)
        by_label.setdefault((m.group, m.kind), []).append((name, n))
        issue = suspicious(name or "", m, terms)
        if issue:
            problems.append(issue)
    print(f"{len(census):,} distinct lead-sponsor names, {sum(n for _, n in census):,} study-name pairs")
    wanted = {s.strip().lower() for s in args.show.split(",") if s.strip()}
    for (group, kind), rows in sorted(by_label.items(), key=lambda kv: (kv[0][1] != "parent", kv[0][0], kv[0][1])):
        total = sum(n for _, n in rows)
        print(f"  {group:34s} {kind:9s} {len(rows):5d} names {total:7,d} studies")
        if group.lower() in wanted or kind in wanted:
            for name, n in rows:
                print(f"      {n:6d}  {name}")
    if problems:
        print(f"\n{len(problems)} name(s) mention a company but matched no rule:")
        for p in problems:
            print("  " + p)
        return 1
    print("\nno name that mentions a company falls through to the catch-all")
    return 0


if __name__ == "__main__":
    sys.exit(main())
