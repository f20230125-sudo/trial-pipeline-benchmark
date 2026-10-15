import type { ActiveStudyT, Dataset } from "./schema";
import { int, longDate, monthYear, pct1, usd } from "./format";

// Pure functions that turn the validated data into what the page draws. No React in here, so they can be tested.

export const PHASE_ORDER = ["Early Phase 1", "Phase 1", "Phase 1/2", "Phase 2", "Phase 2/3", "Phase 3"] as const;

const WORDS = ["zeroth", "first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth", "eleventh", "twelfth"];
export function rankWord(n: number): string {
  return WORDS[n] ?? `${n}th`;
}

// ------------------------------------------------------------------------------------------ the ladder (first screen)

export type LadderColumn = { phase: string; total: number; berry: number; studies: ActiveStudyT[] };

/** One column per phase that has studies; inside a column the berry studies come first, so they sit at the foot. */
export function ladderColumns(studies: ActiveStudyT[]): LadderColumn[] {
  return PHASE_ORDER.map((phase) => {
    const inPhase = studies.filter((s) => s.phase === phase);
    const berry = inPhase.filter((s) => s.counts_toward_top_molecule);
    const rest = inPhase.filter((s) => !s.counts_toward_top_molecule);
    const sortKey = (s: ActiveStudyT) => `${s.pc_date ?? "9999"}${s.nct_id}`;
    berry.sort((a, b) => sortKey(a).localeCompare(sortKey(b)));
    rest.sort((a, b) => sortKey(a).localeCompare(sortKey(b)));
    return { phase, total: inPhase.length, berry: berry.length, studies: [...berry, ...rest] };
  }).filter((c) => c.total > 0);
}

export type Mark = { study: ActiveStudyT; x: number; y: number; col: number; index: number; order: number };
export type LadderLayout = {
  width: number;
  height: number;
  marks: Mark[];
  columns: { phase: string; x: number; width: number; total: number; berry: number }[];
  perRow: number;
  footY: number;
};

/** Where every mark goes. Marks fill each column from its foot upwards, `perRow` to a row. */
export function layoutLadder(
  cols: LadderColumn[],
  o: { perRow: number; mark: number; pitch: number; colGap: number; labelHeight: number },
): LadderLayout {
  const colWidth = o.perRow * o.pitch - (o.pitch - o.mark);
  const tallest = Math.max(...cols.map((c) => Math.ceil(c.total / o.perRow)));
  const gridHeight = tallest * o.pitch - (o.pitch - o.mark);
  const marks: Mark[] = [];
  let order = 0;
  const columns = cols.map((c, ci) => {
    const x0 = ci * (colWidth + o.colGap);
    c.studies.forEach((study, i) => {
      const row = Math.floor(i / o.perRow);
      const inRow = i % o.perRow;
      marks.push({
        study,
        x: x0 + inRow * o.pitch,
        y: gridHeight - o.mark - row * o.pitch,
        col: ci,
        index: i,
        order: order++,
      });
    });
    return { phase: c.phase, x: x0, width: colWidth, total: c.total, berry: c.berry };
  });
  return {
    width: cols.length * colWidth + (cols.length - 1) * o.colGap,
    height: gridHeight + o.labelHeight,
    marks,
    columns,
    perRow: o.perRow,
    footY: gridHeight,
  };
}

/** Keyboard movement: arrows move between marks; up and down move a whole row within a column. */
export function neighbour(layout: LadderLayout, order: number, key: string): number {
  const m = layout.marks[order];
  if (!m) return order;
  const inColumn = layout.marks.filter((x) => x.col === m.col);
  const at = inColumn.findIndex((x) => x.order === order);
  if (key === "ArrowRight") return Math.min(order + 1, layout.marks.length - 1);
  if (key === "ArrowLeft") return Math.max(order - 1, 0);
  if (key === "ArrowUp") return inColumn[Math.min(at + layout.perRow, inColumn.length - 1)].order;
  if (key === "ArrowDown") return inColumn[Math.max(at - layout.perRow, 0)].order;
  if (key === "Home") return 0;
  if (key === "End") return layout.marks.length - 1;
  return order;
}

// ------------------------------------------------------------------------------------------ headline figures

export type Figure = { value: string; sentence: string; href: string; berry?: boolean };

/** The five figures beside the ladder. Every number is read from headline.json. */
export function registerFigures(d: Dataset): Figure[] {
  const h = d.headline;
  const az = h.pipeline.largest_active_pipeline;
  return [
    {
      value: int(h.pipeline.msd_active_pipeline),
      sentence: `active pipeline studies, ${rankWord(h.pipeline.msd_active_pipeline_rank)} of 12 after ${h.pipeline.largest_active_pipeline_group ?? "the largest peer"}'s ${int(az)}. ${int(h.pipeline.msd_active_late)} are late-stage.`,
      href: "#pipeline",
    },
    {
      value: pct1(h.concentration.msd_share_pct),
      sentence: `of MSD's ${int(h.concentration.msd_studies_p23)} studies that reach Phase 2 or 3 involve ${h.concentration.msd_top_molecule}. The next company's top molecule is ${pct1(h.concentration.second_share_pct)}.`,
      href: "#concentration",
      berry: true,
    },
    {
      value: usd(h.expiring_revenue.top_spend_2025),
      sentence: `of 2025 Medicaid spend on Januvia and Janumet, whose core protection ends in November 2026. MSD has ${h.expiring_revenue.top_msd_active_late} active late-stage diabetes studies.`,
      href: "#revenue",
    },
    {
      value: int(h.readouts.msd_readouts_24m),
      sentence: `late-stage studies due to finish by ${monthYear(h.readouts.window.split(" to ")[1])}. ${int(h.readouts.azn_readouts_24m)} for AstraZeneca.`,
      href: "#readouts",
    },
    {
      value: `${h.gulf.msd_gcc_share_pct.toFixed(2)}%`,
      sentence: `of MSD's pipeline studies list a site in a Gulf state: ${h.gulf.msd_gcc_pipeline_studies} studies, the smallest share of the 12.`,
      href: "#gulf",
    },
  ];
}

export function dataDate(d: Dataset): string {
  return longDate(d.meta.asOf);
}

// ------------------------------------------------------------------------------------------ small helpers

export function rowsByGroup<T extends { grp: string }>(rows: T[], groups: string[]): T[] {
  const order = new Map(groups.map((g, i) => [g, i]));
  return [...rows].sort((a, b) => (order.get(a.grp) ?? 99) - (order.get(b.grp) ?? 99));
}

/** Phase bands per company for the stacked bars: Phase 1, Phase 2 (including 1/2), and late stage (Phase 3 and 2/3). */
export function phaseBands(d: Dataset): { grp: string; p1: number; p2: number; late: number; total: number; rank: number }[] {
  return d.overview.summary.map((s) => ({
    grp: s.grp,
    p1: s.active_p1,
    p2: s.active_p2,
    late: s.active_late,
    total: s.active_pipeline,
    rank: s.active_pipeline_rank,
  }));
}

/** Quarter labels from the readouts window, in order. */
export function quartersBetween(from: string, to: string): string[] {
  const out: string[] = [];
  let [y, q] = from.split("-Q").map(Number);
  const [y2, q2] = to.split("-Q").map(Number);
  while (y < y2 || (y === y2 && q <= q2)) {
    out.push(`${y}-Q${q}`);
    q += 1;
    if (q === 5) {
      q = 1;
      y += 1;
    }
  }
  return out;
}
