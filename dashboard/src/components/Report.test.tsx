import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { Report } from "./Report";
import { dataset } from "@/lib/fixtures";
import { int, pct1 } from "@/lib/format";

// Renders the whole page at build-test time and checks that what it says is what the data says.
const d = dataset();
const h = d.headline;
const html = renderToStaticMarkup(<Report data={d} repoUrl="https://github.com/example/repo" />);
const text = html.replace(/<[^>]+>/g, " ").replace(/&#x27;|&apos;/g, "'").replace(/&quot;/g, '"').replace(/&amp;/g, "&").replace(/\s+/g, " ");
const heading = (id: string) => (html.match(new RegExp(`<h2 id="${id}"[^>]*>(.*?)</h2>`, "s"))?.[1] ?? "").replace(/<[^>]+>/g, "").replace(/&#x27;|&apos;/g, "'").replace(/\s+/g, " ").trim();

describe("the page says what the data says", () => {
  it("has one h1 and the eight sections", () => {
    expect((html.match(/<h1/g) ?? []).length).toBe(1);
    for (const id of ["overview", "pipeline", "concentration", "revenue", "readouts", "starts", "gulf", "method"]) {
      expect(html).toContain(`id="${id}"`);
    }
  });
  it("h1 and lede carry the headline numbers", () => {
    expect(text).toContain("MSD has the second-largest trial pipeline of 12, and the most concentrated on one molecule");
    expect(text).toContain(`${int(h.pipeline.msd_active_pipeline)} active studies in Phase 1 to 3, behind only AstraZeneca`);
    expect(text).toContain(`${h.concentration.msd_top_molecule_studies} of the ${h.concentration.msd_studies_p23} at Phase 2 or later involve pembrolizumab`);
  });
  it("every section heading is built from its figures", () => {
    expect(heading("h-pipeline")).toBe(`MSD has ${h.pipeline.msd_active_pipeline} active pipeline studies, second to AstraZeneca's ${h.pipeline.largest_active_pipeline}; ${h.pipeline.msd_active_late} are late-stage`);
    expect(heading("h-conc")).toContain(`${pct1(h.concentration.msd_share_pct)} of MSD's studies at Phase 2 or later involve pembrolizumab, the highest share of the 12; the next is ${pct1(h.concentration.second_share_pct)}`);
    expect(heading("h-rev")).toContain("$417M of 2025 Medicaid spend sits on Januvia and Janumet, whose core protection ends in November 2026");
    expect(heading("h-read")).toContain(`${h.readouts.msd_readouts_24m} MSD late-stage studies are due to finish by September 2028; AstraZeneca has ${h.readouts.azn_readouts_24m}`);
    expect(heading("h-starts")).toContain(`MSD started ${h.starts.msd_starts_2025} studies in 2025 against a peer median of ${h.starts.peer_median_starts_2025}`);
    expect(heading("h-gulf")).toContain(`${h.gulf.msd_gcc_pipeline_studies} of MSD's 2,146 pipeline studies have a site in a Gulf state, the smallest share of the 12`);
    expect(heading("h-method")).toContain(`${int(h.snapshot.distinct_studies_fetched)} studies fetched, ${int(h.snapshot.studies_in_scope)} kept, ${int(h.snapshot.studies_quarantined)} set aside; ${h.quality.pass} of ${h.quality.checks} checks pass`);
  });
  it("lists every one of the 238 studies in the ladder's table view data", () => {
    expect(d.msdActive).toHaveLength(238);
    expect(new Set(d.msdActive.map((s) => s.nct_id)).size).toBe(238);
  });
  it("links each mark to its registry record and nothing else", () => {
    const links = [...html.matchAll(/href="(https:\/\/clinicaltrials\.gov\/study\/NCT\d{8})"/g)].map((m) => m[1]);
    expect(links.length).toBeGreaterThanOrEqual(238);
    const hosts = new Set([...html.matchAll(/href="(https?:\/\/[^"/]+)/g)].map((m) => m[1]));
    expect([...hosts].sort()).toEqual(["https://clinicaltrials.gov", "https://github.com"]);
  });
  it("keeps to the voice rules: no em dash, no emoji, no purpose or application talk", () => {
    expect(html.includes(String.fromCharCode(8212))).toBe(false);
    expect(html).not.toMatch(/\p{Extended_Pictographic}/u);
    for (const word of ["application", "apply", "recruiter", "hiring", "internship", "job ", "Dubai team"]) {
      expect(text.toLowerCase()).not.toContain(word.toLowerCase());
    }
  });
  it("states its limits next to the numbers", () => {
    expect(text).toContain("A registered study is not a launch plan");
    expect(text).toContain("before rebates, not company revenue");
    expect(text).toContain("A forecast has to beat \"same as last year\"");
  });
  it("offers the Excel model as a download", () => {
    expect(html).toMatch(/href="\/downloads\/Pipeline-Benchmark-Model\.xlsx"[^>]*download/);
  });
  it("uses berry only for MSD: the berry class never appears on a peer row", () => {
    expect(html).not.toMatch(/t-berry[^>]*>(AstraZeneca|Novartis|Pfizer|Roche)</);
  });
});
