"""Forecast of pipeline starts per year, with a backtest, so the number comes with an honest error bar.

    python -m tp.forecast

Twelve annual points (2014-2025) is not much, so the aim is not a clever model: it is to show whether any method beats
"next year equals this year", and by how much it misses. Same method as the sibling project (rx-analytics).

Methods (each forecasts one year ahead from the history it is given):
    naive      next year = last year
    drift      last year x (1 + average growth of the last 2 years)
    log-trend  straight line through log(starts) for the last 4 years, extended one year

Backtest: for origin years 2019-2024, forecast the next year and compare with what happened. The method with the lowest
mean absolute percentage error (MAPE) is used for 2026 and 2027, and the 80th percentile of its backtest errors, widened
by the square root of the horizon, gives the range. Segments: MSD and the median of the 11 peers. 2026 in the data is a
part year, so it is shown as year to date and never used as history.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass

import numpy as np

from . import sources as S
from .build import connect

METHODS = ("naive", "drift", "log-trend")
FIRST_ORIGIN, LAST_YEAR, HORIZON_END = 2019, 2025, 2027


def predict(method: str, years: list[int], values: list[float], steps: int = 1) -> float:
    """Forecast `steps` years past the last year in `years` using only the given history."""
    if method == "naive":
        return values[-1]
    if method == "drift":
        growth = (values[-1] / values[-3]) ** 0.5 - 1 if len(values) >= 3 and values[-3] > 0 else 0.0
        return values[-1] * (1 + growth) ** steps
    if method == "log-trend":
        n = min(4, len(values))
        x = np.array(years[-n:], dtype=float)
        y = np.log(np.array(values[-n:], dtype=float))
        slope, intercept = np.polyfit(x, y, 1)
        return float(math.exp(intercept + slope * (years[-1] + steps)))
    raise ValueError(method)


@dataclass
class Backtest:
    segment: str
    method: str
    mape: float
    errors: list[float]  # signed percentage errors, forecast vs actual


def backtest(segment: str, years: list[int], values: list[float]) -> list[Backtest]:
    out = []
    for method in METHODS:
        errs = []
        for origin in range(FIRST_ORIGIN, LAST_YEAR):
            k = years.index(origin) + 1
            pred = predict(method, years[:k], values[:k])
            actual = values[years.index(origin + 1)]
            errs.append(100 * (pred - actual) / actual)
        out.append(Backtest(segment, method, float(np.mean(np.abs(errs))), errs))
    return out


def run(series: dict[str, tuple[list[int], list[float]]]) -> tuple[list[dict], list[dict]]:
    back_rows, fc_rows = [], []
    for seg, (ys, vs) in series.items():
        results = backtest(seg, ys, vs)
        best = min(results, key=lambda b: b.mape)
        naive = next(b for b in results if b.method == "naive")
        for b in results:
            back_rows.append({"segment": seg, "method": b.method, "mape_pct": round(b.mape, 2),
                              "beats_naive": b.mape < naive.mape, "chosen": b is best,
                              **{f"error_{FIRST_ORIGIN + i + 1}": round(e, 2) for i, e in enumerate(b.errors)}})
        band = float(np.percentile(np.abs(best.errors), 80)) / 100
        for y, v in zip(ys, vs):
            fc_rows.append({"segment": seg, "year": y, "kind": "actual", "studies": round(v, 1), "low": "", "high": "",
                            "method": ""})
        for steps, year in enumerate(range(LAST_YEAR + 1, HORIZON_END + 1), start=1):
            p = predict(best.method, ys, vs, steps)
            widen = band * math.sqrt(steps)
            fc_rows.append({"segment": seg, "year": year, "kind": "forecast", "studies": round(p, 1),
                            "low": round(p * (1 - widen), 1), "high": round(p * (1 + widen), 1), "method": best.method})
    return back_rows, fc_rows


def main() -> int:
    con = connect(read_only=True)
    msd = con.execute("select year, studies from mart_starts_year where grp = 'MSD' and year <= 2025 order by year").fetchall()
    peer = con.execute("select year, median_studies from mart_starts_peer_median where year <= 2025 order by year").fetchall()
    series = {"MSD": ([int(y) for y, _ in msd], [float(v) for _, v in msd]),
              "Median of the 11 peers": ([int(y) for y, _ in peer], [float(v) for _, v in peer])}
    back_rows, fc_rows = run(series)
    S.MARTS.mkdir(parents=True, exist_ok=True)
    for name, data in (("forecast_backtest.csv", back_rows), ("forecast.csv", fc_rows)):
        with (S.MARTS / name).open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(data[0]), lineterminator="\n")
            w.writeheader()
            w.writerows(data)
    for r in back_rows:
        print(f"{r['segment']:<24} {r['method']:<10} MAPE {r['mape_pct']:>5}%  beats naive: {r['beats_naive']}  "
              f"chosen: {r['chosen']}")
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
