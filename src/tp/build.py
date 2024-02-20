"""Build the DuckDB warehouse from data/raw.

    python -m tp.build              # stage -> model -> marts
    python -m tp.build stage        # only the staging layer
    python -m tp.build model marts  # re-run later layers on an existing staging layer

Layers (each is a numbered SQL file in sql/, run in order):
    01-02  staging: the API pages as published, typed, nothing removed
    03     quarantine: studies left out of the analysis, each with the reason
    04     dimensions: sponsors, phases, countries, areas
    05     facts: one clean row per in-scope study, plus its molecules, countries and sites
    06+    marts: small tables the dashboard, workbook and report read

The tested Python rules (sponsor roll-up, dates, phases, countries, stop themes) are applied to DISTINCT values and the
result is stored as a map_* table, which SQL then joins. Calling Python once per row would be slow and adds nothing.
"""

from __future__ import annotations

import csv
import json
import sys
import tempfile
import time
from pathlib import Path

import duckdb

from . import dates, phases, sources as S, sponsors, stops

SQL_DIR = S.SQL


def connect(path: Path = S.WAREHOUSE) -> duckdb.DuckDBPyConnection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path))
    con.execute("set threads=4")
    return con


def _run_sql(con: duckdb.DuckDBPyConnection, name: str, **params: str) -> None:
    sql = (SQL_DIR / name).read_text(encoding="utf-8")
    for key, value in params.items():
        sql = sql.replace("{" + key + "}", value)
    started = time.time()
    con.execute(sql)
    print(f"  {name:<28} {time.time() - started:5.1f}s")


def as_of() -> str:
    """The date of the data, not the date of the build: the API's dataTimestamp."""
    return json.loads(S.MANIFEST.read_text(encoding="utf-8"))["dataTimestamp_start"][:10]


def load_rows(con: duckdb.DuckDBPyConnection, table: str, columns: dict[str, str], rows: list[tuple]) -> None:
    """Bulk-load Python rows through a temporary CSV. executemany inserts one row at a time and took 5 ms a row."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / f"{table}.csv"
        with path.open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            for r in rows:
                w.writerow(["\\N" if v is None else v for v in r])
        cols = ", ".join(f"'{k}': '{v}'" for k, v in columns.items())
        con.execute(f"create or replace table {table} as select * from read_csv('{path.as_posix()}', header=false, "
                    f"columns={{{cols}}}, nullstr='\\N')")


def build_maps(con: duckdb.DuckDBPyConnection) -> None:
    started = time.time()
    # sponsors
    rules = sponsors.load_rules()
    names = [r[0] for r in con.execute("select distinct lead_name from stg_study").fetchall()]
    rows = []
    for n in names:
        m = sponsors.classify(n, rules)
        rows.append((n, m.group, m.kind, m.order, m.note))
    load_rows(con, "map_sponsor", {"lead_name": "VARCHAR", "grp": "VARCHAR", "kind": "VARCHAR",
                                   "rule_order": "INTEGER", "note": "VARCHAR"}, rows)
    # dates
    raws = [r[0] for r in con.execute(
        """select start_raw from stg_study union select pc_raw from stg_study union select completion_raw from stg_study
           union select status_verified_raw from stg_study union select first_post_raw from stg_study
           union select last_update_raw from stg_study""").fetchall() if r[0] is not None]
    load_rows(con, "map_date", {"raw": "VARCHAR", "d": "DATE", "precision": "VARCHAR"},
              [(r, *dates.parse(r)) for r in raws])
    # phases
    codes = [r[0] for r in con.execute("select distinct phases_raw from stg_study where phases_raw is not null"
                                       ).fetchall()]
    load_rows(con, "map_phase", {"phases_raw": "VARCHAR", "label": "VARCHAR", "phase_max": "INTEGER",
                                 "rank": "INTEGER", "pipeline": "BOOLEAN"},
              [(c, p.label, p.phase_max, p.rank, str(p.pipeline).lower()) for c in codes if (p := phases.parse(c))])
    # why a study stopped
    stop_rules = stops.load_rules()
    texts = [r[0] for r in con.execute("select distinct why_stopped from stg_study where why_stopped is not null"
                                       ).fetchall()]
    load_rows(con, "map_stop", {"why_stopped": "VARCHAR", "theme": "VARCHAR"},
              [(t, stops.theme(t, stop_rules)) for t in texts])
    print(f"  {'maps (python)':<28} {time.time() - started:5.1f}s  {len(names)} sponsor names, {len(raws)} date "
          f"strings, {len(codes)} phase codes, {len(texts)} stop texts")


def stage(con: duckdb.DuckDBPyConnection) -> None:
    print("stage")
    if not S.RAW.exists() or not list(S.RAW.glob("*/page_*.json")):
        raise SystemExit("no pages in data/raw/ctgov: run python -m tp.fetch first")
    _run_sql(con, "01_stage.sql", raw_glob=S.RAW.as_posix().rstrip("/") + "/*/page_*.json")
    build_maps(con)
    _run_sql(con, "02_stage_children.sql")


def model(con: duckdb.DuckDBPyConnection) -> None:
    print("model")
    for name in sorted(p.name for p in SQL_DIR.glob("0[3-5]*.sql")):
        _run_sql(con, name, ref_dir=S.REF.as_posix(), as_of=as_of())


def marts(con: duckdb.DuckDBPyConnection) -> None:
    print("marts")
    S.MARTS.mkdir(parents=True, exist_ok=True)
    for name in sorted(p.name for p in SQL_DIR.glob("[0-9][0-9]*.sql") if int(p.name[:2]) >= 6):
        _run_sql(con, name, marts_dir=S.MARTS.as_posix(), ref_dir=S.REF.as_posix(), as_of=as_of())


LAYERS = {"stage": stage, "model": model, "marts": marts}


def main(argv: list[str] | None = None) -> int:
    wanted = (argv if argv is not None else sys.argv[1:]) or list(LAYERS)
    unknown = [w for w in wanted if w not in LAYERS]
    if unknown:
        print(f"unknown layer(s): {', '.join(unknown)}; choose from {', '.join(LAYERS)}", file=sys.stderr)
        return 2
    started = time.time()
    con = connect()
    for layer in wanted:
        LAYERS[layer](con)
    con.close()
    print(f"built in {time.time() - started:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
