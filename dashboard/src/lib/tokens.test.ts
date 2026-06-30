import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

// The contrast table in DESIGN.md, recomputed from the real CSS, so changing a colour cannot quietly break it.
const css = fs.readFileSync(path.join(process.cwd(), "src", "app", "globals.css"), "utf-8");

function block(selector: RegExp): Record<string, string> {
  const m = css.match(selector);
  expect(m, String(selector)).toBeTruthy();
  const out: Record<string, string> = {};
  for (const [, k, v] of m![1].matchAll(/--([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})/g)) out[k] = v;
  return out;
}
const light = block(/:root \{\s*color-scheme: light;([\s\S]*?)\n\}/);
const dark = { ...light, ...block(/:root\[data-theme="dark"\] \{([\s\S]*?)\n\}/) };

const rgb = (h: string) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
const lin = (c: number) => ((c /= 255) <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
const lum = (h: string) => {
  const [r, g, b] = rgb(h).map(lin);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
const contrast = (a: string, b: string) => {
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};
const mix = (a: string, b: string, pctA: number) => {
  const A = rgb(a);
  const B = rgb(b);
  return `#${A.map((v, i) => Math.round((v * pctA + B[i] * (100 - pctA)) / 100).toString(16).padStart(2, "0")).join("")}`;
};

describe.each([
  ["light", light],
  ["dark", dark],
] as const)("contrast, %s theme", (_name, t) => {
  it("text on paper reaches 4.5:1", () => {
    for (const k of ["ink", "ink-2", "ink-3"]) expect(contrast(t[k], t.paper), k).toBeGreaterThanOrEqual(4.5);
  });
  it("text on the raised paper reaches 4.5:1", () => {
    for (const k of ["ink", "ink-2", "ink-3"]) expect(contrast(t[k], t["paper-2"]), k).toBeGreaterThanOrEqual(4.5);
  });
  it("berry as text and as a mark", () => {
    expect(contrast(t.berry, t.paper)).toBeGreaterThanOrEqual(4.5);
    const wash = mix(t.berry, t.paper, 12);
    expect(contrast(t.berry, wash), "berry on the MSD wash").toBeGreaterThanOrEqual(4.5);
    expect(contrast(t.ink, wash), "ink on the MSD wash").toBeGreaterThanOrEqual(4.5);
  });
  it("the grey mark reaches 3:1 on paper, and berry is told apart from it", () => {
    expect(contrast(t.mute, t.paper)).toBeGreaterThanOrEqual(3);
    expect(contrast(t.berry, t.mute)).toBeGreaterThanOrEqual(1.5);
  });
  it("the four steps of both ramps keep their numbers readable", () => {
    for (const [base, name] of [[t.berry, "berry"], [t["ink-3"], "peer"]] as const) {
      for (const [pct, textColour] of [[12, t.ink], [28, t.ink], [50, t.ink], [100, t.paper]] as const) {
        const fill = mix(base, t.paper, pct);
        expect(contrast(textColour, fill), `${name} ${pct}%`).toBeGreaterThanOrEqual(4.5);
      }
    }
  });
});

describe("the tokens themselves", () => {
  it("share paper, ink and rule with Rx Market Pulse", () => {
    expect(light.paper).toBe("#faf8f3");
    expect(light.ink).toBe("#15302c");
    expect(dark.paper).toBe("#111817");
  });
  it("use the berry accent and no other hue for data", () => {
    expect(light.berry).toBe("#af1d4e");
    expect(dark.berry).toBe("#ee7da0");
  });
});
