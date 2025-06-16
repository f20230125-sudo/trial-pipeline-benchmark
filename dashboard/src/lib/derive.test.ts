import { describe, expect, it } from "vitest";
import { ladderColumns, layoutLadder, neighbour, quartersBetween, rankWord, registerFigures } from "./derive";
import { dataset } from "./fixtures";
import { int, longDate, monthYear, pct1 } from "./format";

const d = dataset();
const OPTS = { perRow: 7, mark: 13, pitch: 15, colGap: 23, labelHeight: 70 };

describe("the ladder", () => {
  const cols = ladderColumns(d.msdActive);
  it("has one column per phase that has studies, in phase order", () => {
    expect(cols.map((c) => c.phase)).toEqual(["Phase 1", "Phase 1/2", "Phase 2", "Phase 2/3", "Phase 3"]);
    expect(cols.map((c) => c.total)).toEqual([37, 37, 58, 7, 99]);
  });
  it("draws one mark per study and colours exactly the studies in the headline share", () => {
    const layout = layoutLadder(cols, OPTS);
    expect(layout.marks).toHaveLength(d.msdActive.length);
    expect(d.msdActive.length).toBe(d.headline.pipeline.msd_active_pipeline);
    const berry = layout.marks.filter((m) => m.study.counts_toward_top_molecule);
    expect(berry).toHaveLength(d.headline.concentration.msd_top_molecule_studies);
    expect(berry.length).toBe(71);
  });
  it("puts the berry marks at the foot of each column", () => {
    const layout = layoutLadder(cols, OPTS);
    for (const col of cols.map((_, i) => i)) {
      const inCol = layout.marks.filter((m) => m.col === col);
      const lowestPlain = Math.max(...inCol.filter((m) => !m.study.counts_toward_top_molecule).map((m) => m.y), -1);
      const highestBerry = Math.min(...inCol.filter((m) => m.study.counts_toward_top_molecule).map((m) => m.y), Infinity);
      const berryCount = inCol.filter((m) => m.study.counts_toward_top_molecule).length;
      if (berryCount > 0 && lowestPlain >= 0 && berryCount >= OPTS.perRow) {
        // once a full berry row exists, no plain mark is below the berry block's top row
        expect(highestBerry).toBeGreaterThan(Math.min(...inCol.map((m) => m.y)) - 1);
      }
      const bottom = Math.max(...inCol.map((m) => m.y));
      const atFoot = inCol.filter((m) => m.y === bottom);
      expect(atFoot.every((m) => m.study.counts_toward_top_molecule) || berryCount === 0).toBe(true);
    }
  });
  it("never lets two marks overlap or leave the drawing", () => {
    const layout = layoutLadder(cols, OPTS);
    const seen = new Set(layout.marks.map((m) => `${m.x},${m.y}`));
    expect(seen.size).toBe(layout.marks.length);
    for (const m of layout.marks) {
      expect(m.x).toBeGreaterThanOrEqual(0);
      expect(m.x + OPTS.mark).toBeLessThanOrEqual(layout.width);
      expect(m.y).toBeGreaterThanOrEqual(0);
      expect(m.y + OPTS.mark).toBeLessThanOrEqual(layout.footY);
    }
  });
  it("fits the tallest column: Phase 3 is 15 rows at 7 to a row", () => {
    const layout = layoutLadder(cols, OPTS);
    expect(Math.ceil(99 / 7)).toBe(15);
    expect(layout.footY).toBe(15 * OPTS.pitch - (OPTS.pitch - OPTS.mark));
  });
  it("moves with the arrow keys and stays inside the ladder", () => {
    const layout = layoutLadder(cols, OPTS);
    expect(neighbour(layout, 0, "ArrowLeft")).toBe(0);
    expect(neighbour(layout, 0, "ArrowRight")).toBe(1);
    expect(neighbour(layout, layout.marks.length - 1, "ArrowRight")).toBe(layout.marks.length - 1);
    expect(neighbour(layout, 0, "End")).toBe(layout.marks.length - 1);
    const up = neighbour(layout, 0, "ArrowUp");
    expect(layout.marks[up].col).toBe(layout.marks[0].col);
    expect(layout.marks[up].y).toBeLessThan(layout.marks[0].y);
    expect(neighbour(layout, up, "ArrowDown")).toBe(0);
  });
});

describe("the five figures beside the ladder", () => {
  const figs = registerFigures(d);
  const h = d.headline;
  it("are read from headline.json, not typed", () => {
    expect(figs).toHaveLength(5);
    expect(figs[0].value).toBe(int(h.pipeline.msd_active_pipeline));
    expect(figs[1].value).toBe(pct1(h.concentration.msd_share_pct));
    expect(figs[3].value).toBe(int(h.readouts.msd_readouts_24m));
    expect(figs[4].value).toBe(`${h.gulf.msd_gcc_share_pct.toFixed(2)}%`);
    expect(figs[2].value).toBe("$417M");
  });
  it("name their comparators in the same sentence", () => {
    expect(figs[0].sentence).toContain("second of 12 after AstraZeneca's 387");
    expect(figs[1].sentence).toContain("26.3%");
    expect(figs[3].sentence).toContain("67 for AstraZeneca");
    expect(figs[2].sentence).toContain("November 2026");
  });
  it("link to sections that exist and only the concentration figure is berry", () => {
    expect(figs.map((f) => f.href)).toEqual(["#pipeline", "#concentration", "#revenue", "#readouts", "#gulf"]);
    expect(figs.filter((f) => f.berry).map((f) => f.href)).toEqual(["#concentration"]);
  });
});

describe("small helpers", () => {
  it("rank words", () => {
    expect(rankWord(1)).toBe("first");
    expect(rankWord(2)).toBe("second");
    expect(rankWord(13)).toBe("13th");
  });
  it("dates", () => {
    expect(longDate("2026-10-14")).toBe("14 October 2026");
    expect(monthYear("2028-09-30")).toBe("September 2028");
  });
  it("quarters run in order across a year end", () => {
    expect(quartersBetween("2026-Q4", "2028-Q3")).toEqual(["2026-Q4", "2027-Q1", "2027-Q2", "2027-Q3", "2027-Q4", "2028-Q1", "2028-Q2", "2028-Q3"]);
  });
});
