"use client";

import { scaleLinear } from "d3-scale";
import { useMemo, useRef, useState } from "react";
import { niceTicks, useWidth } from "./chart";
import { int, longDate, monthYear } from "@/lib/format";

const FORMATS = { int, pct: (n: number) => `${n}%` } as const;

// Plain SVG charts. Colour rule: MSD is berry, every other company is mute; nothing else is coloured.

export type BarRow = { key: string; label: string; msd?: boolean; value: number; segs?: number[]; text?: string };

/** Horizontal bars, one row per company. `segs` (if given) stacks the bar in bands lightest to darkest. */
export function BarChart({
  rows,
  max,
  ariaLabel,
  steps = [2, 3, 4],
  dot = false,
  format = "int",
  ticksCount = 4,
}: {
  rows: BarRow[];
  max?: number;
  ariaLabel: string;
  steps?: number[];
  dot?: boolean;
  format?: keyof typeof FORMATS;
  ticksCount?: number;
}) {
  const [ref, width] = useWidth<HTMLDivElement>(560);
  const fmt = FORMATS[format];
  const rowH = 26;
  const labelW = Math.min(138, Math.max(92, Math.round(width * 0.27)));
  const longest = Math.max(0, ...rows.map((r) => (r.text ? r.text.length : 0)));
  const valueW = longest > 0 ? Math.min(168, Math.round(longest * 6.3) + 14) : 56;
  const plotW = Math.max(60, width - labelW - valueW);
  const top = 4;
  const { top: axisMax, ticks } = niceTicks(max ?? Math.max(...rows.map((r) => r.value)), ticksCount);
  const x = scaleLinear().domain([0, axisMax]).range([0, plotW]);
  const h = top + rows.length * rowH + 22;
  return (
    <div ref={ref}>
      <svg className="svg" viewBox={`0 0 ${width} ${h}`} width={width} height={h} role="img" aria-label={ariaLabel}>
        {ticks.map((t) => (
          <g key={t}>
            <line className="grid" x1={labelW + x(t)} x2={labelW + x(t)} y1={top} y2={top + rows.length * rowH} />
            <text className="t-mute" x={labelW + x(t)} y={h - 4} textAnchor="middle">
              {fmt(t)}
            </text>
          </g>
        ))}
        <line className="axis" x1={labelW} x2={labelW} y1={top} y2={top + rows.length * rowH} />
        {rows.map((r, i) => {
          const y = top + i * rowH;
          const cy = y + rowH / 2;
          let acc = 0;
          return (
            <g key={r.key}>
              <text className={r.msd ? "t-berry" : ""} x={labelW - 8} y={cy + 4} textAnchor="end">
                {r.label}
              </text>
              {dot ? (
                <>
                  <line className="grid" x1={labelW} x2={labelW + x(r.value)} y1={cy} y2={cy} />
                  <circle cx={labelW + x(r.value)} cy={cy} r={5.5} className={r.msd ? "bar-b" : "bar-m"} />
                </>
              ) : r.segs ? (
                r.segs.map((v, k) => {
                  const x0 = x(acc);
                  acc += v;
                  const w = x(acc) - x0;
                  if (w <= 0) return null;
                  const step = steps[k] ?? steps[steps.length - 1];
                  return (
                    <rect
                      key={k}
                      x={labelW + x0}
                      y={y + 4}
                      width={Math.max(0, w - 1)}
                      height={rowH - 8}
                      style={{ fill: `var(--${r.msd ? "m" : "p"}${step})` }}
                    />
                  );
                })
              ) : (
                <rect className={r.msd ? "bar-b" : "bar-m"} x={labelW} y={y + 4} width={Math.max(1, x(r.value))} height={rowH - 8} rx={0} />
              )}
              <text className={r.msd ? "t-berry" : "t-strong"} x={labelW + x(r.value) + (dot ? 12 : 6)} y={cy + 4}>
                {r.text ?? fmt(r.value)}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

/** Two thin bars per row: MSD (berry) above, the median of the 11 peers (mute) below. Used for the area comparison. */
export function PairBars({
  rows,
  max,
  ariaLabel,
}: {
  rows: { key: string; label: string; msd: number; peer: number }[];
  max: number;
  ariaLabel: string;
}) {
  const [ref, width] = useWidth<HTMLDivElement>(420);
  const rowH = 34;
  const labelW = Math.min(158, Math.max(96, Math.round(width * 0.4)));
  const valueW = 74;
  const plotW = Math.max(40, width - labelW - valueW);
  const x = scaleLinear().domain([0, max]).range([0, plotW]);
  const h = rows.length * rowH + 4;
  return (
    <div ref={ref}>
      <svg className="svg" viewBox={`0 0 ${width} ${h}`} width={width} height={h} role="img" aria-label={ariaLabel}>
        <line className="axis" x1={labelW} x2={labelW} y1={0} y2={h - 4} />
        {rows.map((r, i) => {
          const y = i * rowH + 2;
          return (
            <g key={r.key}>
              <text x={labelW - 8} y={y + rowH / 2 + 3} textAnchor="end">
                {r.label}
              </text>
              <rect className="bar-b" x={labelW} y={y + 4} width={Math.max(1, x(r.msd))} height={11} />
              <rect className="bar-m" x={labelW} y={y + 18} width={Math.max(1, x(r.peer))} height={11} />
              <text className="t-berry" x={labelW + x(r.msd) + 6} y={y + 14}>
                {r.msd.toFixed(1)}%
              </text>
              <text className="t-mute" x={labelW + x(r.peer) + 6} y={y + 28}>
                {r.peer.toFixed(1)}%
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

// ------------------------------------------------------------------------------------------ starts per year with a forecast

export type LinePoint = { year: number; value: number };
export function StartsChart({
  msd,
  peers,
  msdYtd,
  forecast,
  band,
  peerForecast,
  ariaLabel,
}: {
  msd: LinePoint[];
  peers: LinePoint[];
  msdYtd: LinePoint;
  forecast: { year: number; value: number; low: number; high: number }[];
  band: boolean;
  peerForecast: { year: number; value: number }[];
  ariaLabel: string;
}) {
  const [ref, width] = useWidth<HTMLDivElement>(680);
  const h = 280;
  const m = { l: 40, r: 128, t: 14, b: 30 };
  const years = [...msd.map((p) => p.year), ...forecast.map((f) => f.year)];
  const x = scaleLinear().domain([Math.min(...years), Math.max(...years)]).range([m.l, width - m.r]);
  const ymax = Math.max(...msd.map((p) => p.value), ...peers.map((p) => p.value), ...forecast.map((f) => f.high));
  const { top, ticks } = niceTicks(ymax, 4);
  const y = scaleLinear().domain([0, top]).range([h - m.b, m.t]);
  const path = (pts: LinePoint[]) => pts.map((p, i) => `${i ? "L" : "M"}${x(p.year)},${y(p.value)}`).join(" ");
  const lastMsd = msd[msd.length - 1];
  const lastPeer = peers[peers.length - 1];
  const fcPath = `M${x(lastMsd.year)},${y(lastMsd.value)} ${forecast.map((f) => `L${x(f.year)},${y(f.value)}`).join(" ")}`;
  const peerFcPath = `M${x(lastPeer.year)},${y(lastPeer.value)} ${peerForecast.map((f) => `L${x(f.year)},${y(f.value)}`).join(" ")}`;
  const bandPath =
    forecast.map((f, i) => `${i ? "L" : "M"}${x(f.year)},${y(f.high)}`).join(" ") +
    " " +
    [...forecast].reverse().map((f) => `L${x(f.year)},${y(f.low)}`).join(" ") +
    " Z";
  const xs = [2014, 2016, 2018, 2020, 2022, 2024, 2026];
  return (
    <div ref={ref}>
      <svg className="svg" viewBox={`0 0 ${width} ${h}`} width={width} height={h} role="img" aria-label={ariaLabel}>
        <defs>
          <pattern id="hatch" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="5" stroke="var(--ink-3)" strokeWidth="1" />
          </pattern>
        </defs>
        {ticks.map((t) => (
          <g key={t}>
            <line className="grid" x1={m.l} x2={width - m.r} y1={y(t)} y2={y(t)} />
            <text className="t-mute" x={m.l - 6} y={y(t) + 4} textAnchor="end">
              {t}
            </text>
          </g>
        ))}
        {xs.map((v) => (
          <text key={v} className="t-mute" x={x(v)} y={h - 8} textAnchor="middle">
            {v}
          </text>
        ))}
        {band && <path d={bandPath} fill="url(#hatch)" opacity={0.7} />}
        <path d={path(peers)} fill="none" stroke="var(--mute)" strokeWidth={2} />
        <path d={peerFcPath} fill="none" stroke="var(--mute)" strokeWidth={2} strokeDasharray="4 4" />
        <path d={path(msd)} fill="none" stroke="var(--berry)" strokeWidth={2.5} />
        <path d={fcPath} fill="none" stroke="var(--berry)" strokeWidth={2.5} strokeDasharray="5 4" />
        {msd.map((p) => (
          <circle key={p.year} cx={x(p.year)} cy={y(p.value)} r={3} className="bar-b" />
        ))}
        <circle cx={x(msdYtd.year)} cy={y(msdYtd.value)} r={4.5} fill="var(--paper)" stroke="var(--ink)" strokeWidth={1.5} />
        <text x={x(msdYtd.year) - 8} y={y(msdYtd.value) + 16} textAnchor="end" className="t-mute">
          2026 to date: {msdYtd.value}
        </text>
        {forecast.map((f) => (
          <circle key={f.year} cx={x(f.year)} cy={y(f.value)} r={4} fill="var(--paper)" stroke="var(--berry)" strokeWidth={2} />
        ))}
        <text x={x(lastMsd.year) + 2} y={y(lastMsd.value) - 10} className="t-berry" textAnchor="middle">
          {lastMsd.value}
        </text>
        <text x={width - m.r + 10} y={y(forecast[forecast.length - 1].value) + 4} className="t-berry">
          MSD
        </text>
        <text x={width - m.r + 10} y={y(peerForecast[peerForecast.length - 1].value) + 4} className="t-strong">
          Median of the 11 peers
        </text>
      </svg>
    </div>
  );
}

// ------------------------------------------------------------------------------------------ marks by quarter (readouts)

export type QuarterStudy = { id: string; quarter: string; label: string };

export function QuarterMarks({ quarters, studies, ariaLabel }: { quarters: string[]; studies: QuarterStudy[]; ariaLabel: string }) {
  const perRow = 3;
  const mark = 12;
  const pitch = 15;
  const colW = perRow * pitch - (pitch - mark);
  const gap = 16;
  const byQ = useMemo(() => quarters.map((q) => studies.filter((s) => s.quarter === q)), [quarters, studies]);
  const tallest = Math.max(1, ...byQ.map((c) => Math.ceil(c.length / perRow)));
  const gridH = tallest * pitch - (pitch - mark);
  const W = quarters.length * colW + (quarters.length - 1) * gap;
  const H = gridH + 56;
  const flat = byQ.flat();
  const [active, setActive] = useState(0);
  const [sel, setSel] = useState<QuarterStudy | null>(null);
  const ref = useRef<SVGSVGElement | null>(null);
  const move = (to: number) => {
    const t = Math.max(0, Math.min(flat.length - 1, to));
    setActive(t);
    setSel(flat[t]);
    ref.current?.querySelector<SVGAElement>(`[data-i="${t}"]`)?.focus();
  };
  const firstIndex = byQ.map((_, i) => byQ.slice(0, i).reduce((a, c) => a + c.length, 0));
  return (
    <div>
      <svg
        ref={ref}
        className="svg ladder"
        viewBox={`0 0 ${W} ${H}`}
        width="100%"
        role="group"
        aria-label={ariaLabel}
        onKeyDown={(e) => {
          const k = e.key;
          if (k === "ArrowRight") move(active + 1);
          else if (k === "ArrowLeft") move(active - 1);
          else if (k === "Home") move(0);
          else if (k === "End") move(flat.length - 1);
          else return;
          e.preventDefault();
        }}
      >
        {byQ.map((c, qi) => {
          const x0 = qi * (colW + gap);
          return (
            <g key={quarters[qi]}>
              {c.map((s, i) => {
                const idx = firstIndex[qi] + i;
                return (
                  <a
                    key={s.id}
                    href={`https://clinicaltrials.gov/study/${s.id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    data-i={idx}
                    tabIndex={idx === active ? 0 : -1}
                    aria-label={`${s.id}. ${s.label}`}
                    onFocus={() => {
                      setActive(idx);
                      setSel(s);
                    }}
                    onMouseEnter={() => setSel(s)}
                  >
                    <rect className="mk b" style={{ ["--i" as string]: 0, animation: "none" }} x={x0 + (i % perRow) * pitch} y={gridH - mark - Math.floor(i / perRow) * pitch} width={mark} height={mark} />
                  </a>
                );
              })}
              <line className="foot-rule" x1={x0} x2={x0 + colW} y1={gridH + 8} y2={gridH + 8} />
              <text className="col-n" style={{ fontSize: 18 }} x={x0} y={gridH + 30}>
                {c.length}
              </text>
              <text className="col-p" x={x0} y={gridH + 48}>
                {`Q${quarters[qi].split("-Q")[1]} ${quarters[qi].slice(2, 4)}`}
              </text>
            </g>
          );
        })}
      </svg>
      <p className="detail" aria-live="polite">
        {sel ? (
          <>
            <a className="id" href={`https://clinicaltrials.gov/study/${sel.id}`} target="_blank" rel="noopener noreferrer">
              {sel.id}
            </a>{" "}
            {sel.label}
          </>
        ) : (
          "Select a mark to see its registry record."
        )}
      </p>
    </div>
  );
}

// ------------------------------------------------------------------------------------------ one 100% strip (pembrolizumab sponsors)

export type StripPart = { key: string; label: string; value: number; kind: "msd" | "peer" | "industry" | "academic" };
export function Strip({ parts, ariaLabel }: { parts: StripPart[]; ariaLabel: string }) {
  const [ref, width] = useWidth<HTMLDivElement>(560);
  const total = parts.reduce((a, p) => a + p.value, 0);
  const starts = parts.map((_, i) => parts.slice(0, i).reduce((a, p) => a + p.value, 0));
  const h = 50 + parts.length * 22;
  const fillOf = (k: StripPart["kind"]) =>
    k === "msd" ? "var(--berry)" : k === "peer" ? "var(--mute)" : k === "industry" ? "url(#hatch2)" : "var(--paper)";
  const strokeOf = (k: StripPart["kind"]) => (k === "academic" ? "var(--ink-3)" : k === "industry" ? "var(--mute)" : "none");
  return (
    <div ref={ref}>
      <svg className="svg" viewBox={`0 0 ${width} ${h}`} width={width} height={h} role="img" aria-label={ariaLabel}>
        <defs>
          <pattern id="hatch2" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="5" height="5" fill="var(--paper)" />
            <line x1="0" y1="0" x2="0" y2="5" stroke="var(--mute)" strokeWidth="1.5" />
          </pattern>
        </defs>
        {parts.map((p, i) => {
          const x0 = (starts[i] / total) * width;
          const w = (p.value / total) * width;
          return <rect key={p.key} x={x0} y={4} width={Math.max(1, w - 1)} height={30} fill={fillOf(p.kind)} stroke={strokeOf(p.kind)} strokeWidth={1} />;
        })}
        {parts.map((p, i) => (
          <g key={`l${p.key}`}>
            <rect x={0} y={52 + i * 22 - 10} width={14} height={12} fill={fillOf(p.kind)} stroke={strokeOf(p.kind) === "none" ? "var(--rule-2)" : strokeOf(p.kind)} strokeWidth={1} />
            <text className={p.kind === "msd" ? "t-berry" : "t-strong"} x={22} y={52 + i * 22}>
              {int(p.value)} {p.label} ({((p.value / total) * 100).toFixed(1)}%)
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}

export { longDate, monthYear };
