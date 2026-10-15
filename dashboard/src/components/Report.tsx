import fs from "node:fs";
import path from "node:path";
import { BarChart, PairBars, QuarterMarks, Strip, StartsChart, type BarRow } from "./Charts";
import { Fig } from "./Fig";
import { Ladder } from "./Ladder";
import { ThemeToggle } from "./ThemeToggle";
import { dataDate, phaseBands, quartersBetween, rankWord, registerFigures } from "@/lib/derive";
import { int, longDate, monthYear, pct1, productCase, usd } from "@/lib/format";
import type { Dataset } from "@/lib/schema";

const EXCEL = "Pipeline-Benchmark-Model.xlsx";
const SECTIONS: [string, string][] = [
  ["pipeline", "Pipeline"],
  ["concentration", "Concentration"],
  ["revenue", "Revenue"],
  ["readouts", "Readouts"],
  ["starts", "Starts and stops"],
  ["gulf", "Gulf"],
  ["method", "Method"],
];
const GULF = [
  ["ARE", "UAE"],
  ["SAU", "Saudi Arabia"],
  ["QAT", "Qatar"],
  ["KWT", "Kuwait"],
  ["BHR", "Bahrain"],
  ["OMN", "Oman"],
] as const;

function excelSize(): string {
  try {
    const bytes = fs.statSync(path.join(process.cwd(), "public", "downloads", EXCEL)).size;
    return `${(bytes / 1e6).toFixed(1)} MB`;
  } catch {
    return "";
  }
}

function median(xs: number[]): number {
  const s = [...xs].sort((a, b) => a - b);
  const n = s.length;
  return n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2;
}

function Status({ s }: { s: "pass" | "warn" | "fail" | "info" }) {
  const word = { pass: "Pass", warn: "Warn", fail: "Fail", info: "For information" }[s];
  return (
    <span className="status">
      <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.6">
        {s === "pass" && <path d="M2 6.5 L5 9.5 L10 2.5" />}
        {s === "info" && <circle cx="6" cy="6" r="4.2" />}
        {s === "warn" && <path d="M6 1.5 L11 10.5 H1 Z" />}
        {s === "fail" && <path d="M2 2 L10 10 M10 2 L2 10" />}
      </svg>
      {word}
    </span>
  );
}

export function Report({ data: d, repoUrl }: { data: Dataset; repoUrl?: string }) {
  const h = d.headline;
  const groups = d.meta.groups.map((g) => g.grp);
  const summary = (g: string) => d.overview.summary.find((s) => s.grp === g)!;
  const msd = summary("MSD");
  const date = dataDate(d);
  const size = excelSize();
  const others = groups.filter((g) => g !== "MSD");
  const azn = summary(h.pipeline.largest_active_pipeline_group ?? "AstraZeneca");

  // ------------------------------------------------------------------ pipeline
  const bands = phaseBands(d).sort((a, b) => b.total - a.total);
  const bandRows: BarRow[] = bands.map((b) => ({ key: b.grp, label: b.grp, msd: b.grp === "MSD", value: b.total, segs: [b.p1, b.p2, b.late] }));
  const areaShare = (g: string, a: string) => d.overview.area.find((r) => r.grp === g && r.area === a)?.share_pct ?? 0;
  const areaRows = d.meta.areas
    .map((a) => ({ key: a, label: a, msd: areaShare("MSD", a), peer: median(others.map((g) => areaShare(g, a))) }))
    .filter((r) => r.msd > 0 || r.peer > 0)
    .sort((a, b) => b.msd - a.msd);
  const heat = (v: number) => (v === 0 ? "c0" : v < 5 ? "c1" : v < 10 ? "c2" : v < 20 ? "c3" : "c4");

  // ------------------------------------------------------------------ concentration
  const conc = [...d.concentration.concentration].sort((a, b) => b.share_pct - a.share_pct);
  const concRows: BarRow[] = conc.map((c) => ({
    key: c.grp,
    label: c.grp,
    msd: c.grp === "MSD",
    value: c.share_pct,
    text: `${pct1(c.share_pct)}  ${c.top_molecule}`,
  }));
  const top5 = d.concentration.top.filter((t) => t.grp === "MSD").sort((a, b) => a.rank - b.rank);
  const ecoKind = (c: string) => (c === "MSD" ? "msd" : c.startsWith("Other of") ? "peer" : c === "Other industry" ? "industry" : "academic");
  const ecoShort = (c: string) => (c === "MSD" ? "led by MSD" : c.startsWith("Other of") ? "other peers" : c === "Other industry" ? "other industry" : "academic, hospital and other");

  // ------------------------------------------------------------------ revenue
  const rev = d.revenue;
  const maxSpend = Math.max(...rev.franchise.map((f) => f.spend_2025));
  const dated = (f: (typeof rev.franchise)[number]) => !!f.core_end && f.core_end >= "2026-01-01" && f.core_end <= "2028-12-31";

  // ------------------------------------------------------------------ readouts
  const win = h.readouts.window.split(" to ");
  const startQ = `${win[0].slice(0, 4)}-Q${Math.floor((Number(win[0].slice(5, 7)) - 1) / 3) + 1}`;
  const endQ = `${win[1].slice(0, 4)}-Q${Math.floor((Number(win[1].slice(5, 7)) - 1) / 3) + 1}`;
  const quarters = quartersBetween(startQ, endQ);
  const qStudies = d.readouts.msd.map((s) => ({
    id: s.nct_id,
    quarter: `${s.pc_date.slice(0, 4)}-Q${Math.floor((Number(s.pc_date.slice(5, 7)) - 1) / 3) + 1}`,
    label: `${s.phase}, ${s.area}. Primary completion ${longDate(s.pc_date)} (${s.pc_type.toLowerCase()}).`,
  }));
  const readRows: BarRow[] = [...d.readouts.summary]
    .sort((a, b) => b.readouts_24m - a.readouts_24m)
    .map((r) => ({ key: r.grp, label: r.grp, msd: r.grp === "MSD", value: r.readouts_24m }));

  // ------------------------------------------------------------------ starts
  const msdYears = d.starts.byGroup.filter((r) => r.grp === "MSD");
  const msdActual = msdYears.filter((r) => !r.partial_year).map((r) => ({ year: r.year, value: r.studies }));
  const msdYtd = msdYears.find((r) => r.partial_year)!;
  const peerActual = d.starts.peerMedian.filter((r) => !r.partial_year).map((r) => ({ year: r.year, value: r.median_studies }));
  const fcMsd = d.starts.forecast.filter((r) => r.segment === "MSD" && r.kind === "forecast").map((r) => ({ year: r.year, value: r.studies, low: r.low ?? r.studies, high: r.high ?? r.studies }));
  const fcPeer = d.starts.forecast.filter((r) => r.segment.startsWith("Median") && r.kind === "forecast").map((r) => ({ year: r.year, value: r.studies }));
  const termRows: BarRow[] = [...d.starts.termination]
    .sort((a, b) => b.termination_rate_pct - a.termination_rate_pct)
    .map((t) => ({ key: t.grp, label: t.grp, msd: t.grp === "MSD", value: t.termination_rate_pct, text: pct1(t.termination_rate_pct) }));
  const years = msdActual.map((p) => p.year);

  // ------------------------------------------------------------------ gulf
  const gulfRows = [...d.gulf.summary].sort((a, b) => a.gcc_share_pct - b.gcc_share_pct);
  const gcell = (g: string, iso: string) => d.gulf.country.find((c) => c.grp === g && c.iso3 === iso)?.studies ?? 0;
  const gtone = (n: number) => (n === 0 ? "c0" : n < 3 ? "c1" : n < 8 ? "c2" : n < 20 ? "c3" : "c4");
  const bahrain = d.gulf.country.filter((c) => c.iso3 === "BHR").length === 0;

  // ------------------------------------------------------------------ method
  const wf = d.quality.waterfall;
  const wfRows: BarRow[] = wf.map((w, i) => ({
    key: String(i),
    label: w.stage.replace("Set aside: ", "Aside: ").replace("Rows returned by the searches", "Search rows").replace("Found by more than one search (counted once)", "Found twice"),
    value: Math.abs(w.studies),
    text: w.studies < 0 ? `−${int(Math.abs(w.studies))}` : int(w.studies),
  }));
  const q = h.quality;

  const figures = registerFigures(d);
  const concIsFirst = h.concentration.msd_concentration_rank === 1;

  return (
    <>
      <a className="skip" href="#main">
        Skip to the report
      </a>
      <header className="bar">
        <div className="shell bar-in">
          <a className="brand" href="#overview">
            Trial Pipeline Benchmark
          </a>
          <nav aria-label="Sections">
            {SECTIONS.map(([id, label]) => (
              <a key={id} href={`#${id}`}>
                {label}
              </a>
            ))}
            <a className="dl" href={`/downloads/${EXCEL}`} download>
              Excel model{size ? ` (${size})` : ""}
            </a>
          </nav>
          <details className="sections-menu">
            <summary className="btn">Sections</summary>
            <div className="menu">
              {SECTIONS.map(([id, label]) => (
                <a key={id} href={`#${id}`}>
                  {label}
                </a>
              ))}
              <a href={`/downloads/${EXCEL}`} download>
                Excel model
              </a>
            </div>
          </details>
          <ThemeToggle />
        </div>
      </header>

      <main id="main">
        <section className="hero" id="overview" aria-labelledby="h1">
          <div className="shell">
            <p className="kicker">
              MSD against 11 peers, from the public ClinicalTrials.gov registry as it stood on {date}. A commercial-analytics
              case study by <b>Mohammad Uzair Khan</b>.
            </p>
            <h1 id="h1">
              {`MSD has the ${rankWord(h.pipeline.msd_active_pipeline_rank)}-largest trial pipeline of 12${concIsFirst ? ", and the most concentrated on one molecule" : ""}`}
            </h1>
            <p className="lede">
              {int(h.pipeline.msd_active_pipeline)} active studies in Phase 1 to 3
              {h.pipeline.msd_active_pipeline_rank === 2 ? `, behind only ${h.pipeline.largest_active_pipeline_group}` : ""}.{" "}
              {int(h.concentration.msd_top_molecule_studies)} of the {int(h.concentration.msd_studies_p23)} at Phase 2 or later involve{" "}
              {h.concentration.msd_top_molecule}
              {concIsFirst ? ", a higher share than any peer has on one molecule" : ""}. Every count below traces to a registry record.
            </p>
            <div className="first">
              <Ladder
                studies={d.msdActive}
                molecule={h.concentration.msd_top_molecule}
                share={h.concentration.msd_share_pct}
                inBase={h.concentration.msd_studies_p23}
                asOf={d.meta.asOf}
              />
              <ol className="reg" aria-label="The five figures">
                {figures.map((f) => (
                  <li key={f.href}>
                    <a href={f.href}>
                      <span className={`reg-v${f.berry ? " b" : ""}`}>{f.value}</span>
                      <span className="reg-s">{f.sentence}</span>
                    </a>
                  </li>
                ))}
              </ol>
            </div>
          </div>
        </section>

        {/* ------------------------------------------------------------------ pipeline */}
        <section className="sec" id="pipeline" aria-labelledby="h-pipeline">
          <div className="shell">
            <div className="sec-head">
              <h2 id="h-pipeline">
                MSD has {int(msd.active_pipeline)} active pipeline studies, {rankWord(msd.active_pipeline_rank)} to {azn.grp}&apos;s{" "}
                {int(azn.active_pipeline)}; {int(msd.active_late)} are late-stage
              </h2>
              <p className="dek">
                An active pipeline study is an interventional drug, biological, genetic or combination-product study in Phase 1 to 3 that
                is recruiting, not yet recruiting, enrolling by invitation or active but not recruiting. Counts are studies the company
                itself leads.
              </p>
            </div>
            <div className="sec-body">
              <div className="pair">
                <Fig
                  title="Active pipeline studies by company and phase"
                  legend={
                    <ul className="legend">
                      <li>
                        <i style={{ background: "var(--p2)" }} />
                        Phase 1
                      </li>
                      <li>
                        <i style={{ background: "var(--p3)" }} />
                        Phase 2 (including 1/2)
                      </li>
                      <li>
                        <i style={{ background: "var(--p4)" }} />
                        Late stage (Phase 3 and 2/3)
                      </li>
                      <li>MSD is drawn in berry, in the same three steps</li>
                    </ul>
                  }
                  table={
                    <table className="tbl">
                      <caption>Active pipeline studies by phase, as registered on {date}.</caption>
                      <thead>
                        <tr>
                          <th scope="col">Company</th>
                          <th scope="col" className="n">Phase 1</th>
                          <th scope="col" className="n">Phase 2</th>
                          <th scope="col" className="n">Late stage</th>
                          <th scope="col" className="n">Total</th>
                          <th scope="col" className="n">Rank</th>
                        </tr>
                      </thead>
                      <tbody>
                        {bands.map((b) => (
                          <tr key={b.grp} className={b.grp === "MSD" ? "hl" : undefined}>
                            <th scope="row" className="nm">{b.grp}</th>
                            <td className="n">{int(b.p1)}</td>
                            <td className="n">{int(b.p2)}</td>
                            <td className="n">{int(b.late)}</td>
                            <td className="n">{int(b.total)}</td>
                            <td className="n">{b.rank}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  }
                  source={<>Source: ClinicalTrials.gov API v2, data as of {date}; lead-sponsor studies only. Bars end in the total.</>}
                >
                  <BarChart rows={bandRows} max={400} ariaLabel={`Active pipeline studies by company, largest first: ${bands.slice(0, 3).map((b) => `${b.grp} ${b.total}`).join(", ")}, with MSD at ${msd.active_pipeline}.`} />
                </Fig>
                <Fig
                  title="Where the studies are: MSD against the median of the 11 peers"
                  sub="Share of each company's active pipeline studies in each therapeutic area"
                  legend={
                    <ul className="legend">
                      <li>
                        <i style={{ background: "var(--berry)" }} />
                        MSD
                      </li>
                      <li>
                        <i style={{ background: "var(--mute)" }} />
                        Median of the 11 peers
                      </li>
                    </ul>
                  }
                  table={
                    <table className="tbl heat">
                      <caption>Share of each company&apos;s active pipeline studies by area, in percent. The area is read from the condition names, then the registry&apos;s disease tags, then the molecule&apos;s usual area.</caption>
                      <thead>
                        <tr>
                          <th scope="col" className="scroll-col">Company</th>
                          {d.meta.areas.map((a) => (
                            <th key={a} scope="col">{a}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {groups.map((g) => (
                          <tr key={g} className={g === "MSD" ? "hl" : undefined}>
                            <th scope="row" className="rowh scroll-col">{g}</th>
                            {d.meta.areas.map((a) => {
                              const v = areaShare(g, a);
                              return (
                                <td key={a} className={heat(v)}>
                                  {v.toFixed(0)}
                                </td>
                              );
                            })}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  }
                  source={<>Source: same data. An area is assigned from the typed condition names first because the registry&apos;s own disease tags are automatic and sometimes wrong.</>}
                >
                  <PairBars
                    rows={areaRows}
                    max={Math.ceil(Math.max(...areaRows.map((r) => Math.max(r.msd, r.peer))) / 10) * 10}
                    ariaLabel={`Share of active pipeline studies by therapeutic area. MSD is led by ${areaRows[0].label} at ${areaRows[0].msd.toFixed(1)} percent against a peer median of ${areaRows[0].peer.toFixed(1)}.`}
                  />
                </Fig>
              </div>
            </div>
          </div>
        </section>

        {/* ------------------------------------------------------------------ concentration */}
        <section className="sec" id="concentration" aria-labelledby="h-conc">
          <div className="shell">
            <div className="sec-head">
              <h2 id="h-conc">
                {pct1(h.concentration.msd_share_pct)} of MSD&apos;s studies at Phase 2 or later involve {h.concentration.msd_top_molecule}
                {concIsFirst ? ", the highest share of the 12" : ""}; the next is {pct1(h.concentration.second_share_pct)}
              </h2>
              <p className="dek">
                For each company, the share of its active studies that reach Phase 2 or 3 (counting Phase 1/2) which involve its single most
                frequent molecule. Chemotherapy backbones, steroids and generic comparators are set aside first, so a drug such as carboplatin
                is not mistaken for a pipeline. A study can involve more than one molecule, so shares do not add up.
              </p>
            </div>
            <div className="sec-body">
              <Fig
                title="Share of Phase 2 and 3 studies on the top molecule"
                table={
                  <table className="tbl">
                    <caption>Active pipeline studies that reach Phase 2 or later, counting Phase 1/2, and the top molecule among them.</caption>
                    <thead>
                      <tr>
                        <th scope="col">Company</th>
                        <th scope="col">Top molecule</th>
                        <th scope="col" className="n">Studies with it</th>
                        <th scope="col" className="n">Studies at Phase 2 or later</th>
                        <th scope="col" className="n">Share</th>
                      </tr>
                    </thead>
                    <tbody>
                      {conc.map((c) => (
                        <tr key={c.grp} className={c.grp === "MSD" ? "hl" : undefined}>
                          <th scope="row" className="nm">{c.grp}</th>
                          <td>{c.top_molecule}</td>
                          <td className="n">{int(c.top_studies)}</td>
                          <td className="n">{int(c.studies_p23)}</td>
                          <td className="n">{pct1(c.share_pct)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                }
                source={<>Source: ClinicalTrials.gov API v2, data as of {date}; brand names and development codes folded into one molecule (data/ref/molecule_aliases.csv).</>}
              >
                <BarChart rows={concRows} max={40} format="pct" ariaLabel={`Share of each company's Phase 2 and 3 studies on its top molecule. MSD is highest at ${pct1(h.concentration.msd_share_pct)} on ${h.concentration.msd_top_molecule}; the next is ${h.concentration.second_group} at ${pct1(h.concentration.second_share_pct)} on ${h.concentration.second_molecule}.`} />
              </Fig>
              <div className="pair even">
                <Fig
                  title="MSD's five most frequent molecules"
                  table={
                    <table className="tbl">
                      <caption>MSD&apos;s active studies at Phase 2 or later (n = {int(h.concentration.msd_studies_p23)}).</caption>
                      <thead>
                        <tr><th scope="col">Molecule</th><th scope="col" className="n">Studies</th><th scope="col" className="n">Share</th></tr>
                      </thead>
                      <tbody>
                        {top5.map((t) => (
                          <tr key={t.molecule}><th scope="row" className="nm">{t.molecule}</th><td className="n">{int(t.studies)}</td><td className="n">{pct1(t.share_pct)}</td></tr>
                        ))}
                      </tbody>
                    </table>
                  }
                  source={<>All five are MSD&apos;s, so all are berry. Studies can involve several molecules.</>}
                >
                  <BarChart
                    rows={top5.map((t) => ({ key: t.molecule, label: t.molecule, msd: true, value: t.studies, text: `${t.studies} (${pct1(t.share_pct)})` }))}
                    max={80}
                    ariaLabel={`MSD's top molecules: ${top5.map((t) => `${t.molecule} ${t.studies}`).join(", ")}.`}
                  />
                </Fig>
                <Fig
                  title={`Who leads the ${int(h.concentration.pembrolizumab_active_studies_all_sponsors)} active pembrolizumab studies`}
                  table={
                    <table className="tbl">
                      <caption>Every active study that tests pembrolizumab, whoever leads it.</caption>
                      <thead>
                        <tr><th scope="col">Led by</th><th scope="col" className="n">Studies</th><th scope="col" className="n">Share</th></tr>
                      </thead>
                      <tbody>
                        {d.concentration.ecosystem.map((e) => (
                          <tr key={e.category} className={e.category === "MSD" ? "hl" : undefined}><th scope="row" className="nm">{e.category}</th><td className="n">{int(e.studies)}</td><td className="n">{pct1(e.share_pct)}</td></tr>
                        ))}
                      </tbody>
                    </table>
                  }
                  source={<>MSD leads {int(h.concentration.pembrolizumab_msd_led)} ({pct1(h.concentration.pembrolizumab_msd_led_pct)}). The rest are run by academic centres, hospitals and other companies.</>}
                >
                  <Strip
                    ariaLabel={`Active pembrolizumab studies by who leads them: ${d.concentration.ecosystem.map((e) => `${e.category} ${e.studies}`).join(", ")}.`}
                    parts={d.concentration.ecosystem.map((e) => ({ key: e.category, label: ecoShort(e.category), value: e.studies, kind: ecoKind(e.category) as "msd" | "peer" | "industry" | "academic" }))}
                  />
                </Fig>
              </div>
              <p className="note">
                Two measures sit on this page and they differ on purpose. The {h.concentration.msd_top_molecule_studies} counted above are studies at Phase 2 or
                later where pembrolizumab is one of the interventions. The {h.concentration.msd_keytruda_linked_active_pipeline} Keytruda-linked studies in the revenue
                table below count every active phase and match Merck&apos;s product list by name, development code or brand.
              </p>
            </div>
          </div>
        </section>

        {/* ------------------------------------------------------------------ revenue */}
        <section className="sec" id="revenue" aria-labelledby="h-rev">
          <div className="shell">
            <div className="sec-head">
              <h2 id="h-rev">
                {usd(h.expiring_revenue.top_spend_2025)} of 2025 Medicaid spend sits on Januvia and Janumet, whose core protection ends in November 2026
              </h2>
              <p className="dek">
                Revenue here is US Medicaid pharmacy spend before rebates, from the sibling project Rx Market Pulse. It is a signal of scale,
                not company revenue. Protection dates are the FDA Orange Book core dates; a biologic such as Keytruda has none, and none is
                invented for it.
              </p>
            </div>
            <div className="sec-body">
              <figure className="fig">
                <div className="fig-head">
                  <div>
                    <h3>Protection ending by 2028, set beside the late-stage pipeline in the same area</h3>
                    <p className="sub">{usd(h.expiring_revenue.total_spend_at_risk_2026_28)} of 2025 Medicaid spend across the three areas</p>
                  </div>
                </div>
                <div className="tbl-wrap" tabIndex={0} role="region" aria-label="Table of protection ending by 2028">
                  <table className="tbl">
                    <caption>A study count is not a probability of launch. The peer median is over the other 11 companies.</caption>
                    <thead>
                      <tr>
                        <th scope="col">Area</th>
                        <th scope="col">Products and core protection ends</th>
                        <th scope="col" className="n">2025 Medicaid spend</th>
                        <th scope="col" className="n">MSD active late-stage studies</th>
                        <th scope="col" className="n">Peer median</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rev.expiring.map((e) => (
                        <tr key={e.area} className={e.area === h.expiring_revenue.top_area ? "hl" : undefined}>
                          <th scope="row" className="nm">{e.area}</th>
                          <td>{productCase(e.families)}</td>
                          <td className="n">{usd(e.spend_2025_at_risk)}</td>
                          <td className="n">{int(e.msd_active_late)}</td>
                          <td className="n">{e.peer_median_active_late.toFixed(1)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </figure>
              <figure className="fig">
                <div className="fig-head">
                  <div>
                    <h3>Merck&apos;s 14 product families in Rx Market Pulse, and the active studies that match them</h3>
                  </div>
                </div>
                <div className="tbl-wrap" tabIndex={0} role="region" aria-label="Table of Merck product families">
                  <table className="tbl">
                    <caption>Rows shaded berry are those whose core protection ends between 2026 and 2028.</caption>
                    <thead>
                      <tr>
                        <th scope="col" className="scroll-col">Product</th>
                        <th scope="col">Area</th>
                        <th scope="col" className="n">2025 Medicaid spend</th>
                        <th scope="col">Core protection ends</th>
                        <th scope="col" className="n">Active studies</th>
                        <th scope="col" className="n">Late-stage</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rev.franchise.map((f) => (
                        <tr key={f.family} className={dated(f) ? "hl" : undefined}>
                          <th scope="row" className="nm scroll-col">{f.family.charAt(0) + f.family.slice(1).toLowerCase()}</th>
                          <td>{f.area}</td>
                          <td className="n">
                            <span className="cellbar" style={{ width: `${Math.max(2, (f.spend_2025 / maxSpend) * 64)}px` }} aria-hidden="true" />
                            {usd(f.spend_2025)}
                          </td>
                          <td>{f.core_end ? monthYear(f.core_end) : "Biologic, no Orange Book date"}</td>
                          <td className="n">{int(f.active_pipeline)}</td>
                          <td className="n">{int(f.active_late)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <figcaption className="src">
                  Source: Rx Market Pulse (CMS State Drug Utilization Data, FDA Orange Book) and ClinicalTrials.gov, data as of {date}. Studies are matched to
                  a product by molecule name, development code or brand name.
                </figcaption>
              </figure>
            </div>
          </div>
        </section>

        {/* ------------------------------------------------------------------ readouts */}
        <section className="sec" id="readouts" aria-labelledby="h-read">
          <div className="shell">
            <div className="sec-head">
              <h2 id="h-read">
                {int(h.readouts.msd_readouts_24m)} MSD late-stage studies are due to finish by {monthYear(win[1])}; AstraZeneca has {int(h.readouts.azn_readouts_24m)}
              </h2>
              <p className="dek">
                Late-stage active studies whose estimated primary completion falls in the 24 months from the data month. A primary completion date is when the last
                participant is examined for the main outcome. It is not when results are announced, and estimated dates slip.
              </p>
            </div>
            <div className="sec-body">
              <div className="pair">
                <Fig
                  title="MSD's late-stage studies by quarter of estimated primary completion"
                  table={
                    <table className="tbl">
                      <caption>MSD&apos;s {d.readouts.msd.length} late-stage studies due in the window, earliest first.</caption>
                      <thead>
                        <tr><th scope="col">Registry record</th><th scope="col">Phase</th><th scope="col">Area</th><th scope="col">Molecule</th><th scope="col">Primary completion (estimated)</th></tr>
                      </thead>
                      <tbody>
                        {d.readouts.msd.map((s) => (
                          <tr key={s.nct_id}>
                            <td><a className="nct" href={`https://clinicaltrials.gov/study/${s.nct_id}`} target="_blank" rel="noopener noreferrer">{s.nct_id}</a></td>
                            <td>{s.phase}</td><td>{s.area}</td><td>{s.top_molecule ?? "n/a"}</td><td>{longDate(s.pc_date)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  }
                  source={<>One mark is one study; select it to open its record. {h.readouts.msd_overdue_late} MSD late-stage {h.readouts.msd_overdue_late === 1 ? "study is" : "studies are"} overdue: still active, but the estimated month has passed.</>}
                >
                  <QuarterMarks quarters={quarters} studies={qStudies} ariaLabel={`MSD's ${d.readouts.msd.length} late-stage studies due to finish, in ${quarters.length} quarter columns. Arrow keys move between studies.`} />
                </Fig>
                <Fig
                  title="Late-stage readouts due in 24 months, by company"
                  table={
                    <table className="tbl">
                      <caption>Active late-stage studies with an estimated primary completion in the window.</caption>
                      <thead><tr><th scope="col">Company</th><th scope="col" className="n">Due</th><th scope="col" className="n">Overdue</th></tr></thead>
                      <tbody>
                        {[...d.readouts.summary].sort((a, b) => b.readouts_24m - a.readouts_24m).map((r) => (
                          <tr key={r.grp} className={r.grp === "MSD" ? "hl" : undefined}><th scope="row" className="nm">{r.grp}</th><td className="n">{int(r.readouts_24m)}</td><td className="n">{int(r.overdue_late)}</td></tr>
                        ))}
                      </tbody>
                    </table>
                  }
                  source={<>Counts are studies, not drugs: one drug can have several studies.</>}
                >
                  <BarChart rows={readRows} max={80} ariaLabel={`Late-stage studies due in 24 months by company. ${h.readouts.max_readouts_24m_group} has the most; MSD has ${h.readouts.msd_readouts_24m}.`} />
                </Fig>
              </div>
            </div>
          </div>
        </section>

        {/* ------------------------------------------------------------------ starts and stops */}
        <section className="sec" id="starts" aria-labelledby="h-starts">
          <div className="shell">
            <div className="sec-head">
              <h2 id="h-starts">
                MSD started {int(h.starts.msd_starts_2025)} studies in 2025 against a peer median of {int(h.starts.peer_median_starts_2025)}
              </h2>
              <p className="dek">
                A start counts when the registry gives a start date that is not an estimate. 2026 is a part year, and registrations arrive late, so it is shown as a
                year to date and left out of the forecast history.
              </p>
            </div>
            <div className="sec-body">
              <Fig
                title="Pipeline studies started each year, with a forecast"
                legend={
                  <ul className="legend">
                    <li><i style={{ background: "var(--berry)" }} />MSD</li>
                    <li><i style={{ background: "var(--mute)" }} />Median of the 11 peers</li>
                    <li><i className="hatch" />Range of the forecast (dashed lines are forecasts)</li>
                    <li><i className="ring" />2026 to date</li>
                  </ul>
                }
                table={
                  <table className="tbl">
                    <caption>Pipeline studies started each year; forecast rows are marked.</caption>
                    <thead><tr><th scope="col">Year</th><th scope="col" className="n">MSD</th><th scope="col" className="n">Median of the 11 peers</th></tr></thead>
                    <tbody>
                      {years.map((y) => (
                        <tr key={y}><th scope="row" className="nm">{y}</th><td className="n">{msdActual.find((p) => p.year === y)?.value}</td><td className="n">{peerActual.find((p) => p.year === y)?.value}</td></tr>
                      ))}
                      <tr><th scope="row" className="nm">2026 to date</th><td className="n">{msdYtd.studies}</td><td className="n">n/a</td></tr>
                      {fcMsd.map((f) => (
                        <tr key={f.year} className="hl"><th scope="row" className="nm">{f.year} forecast</th><td className="n">{f.value.toFixed(0)} ({f.low.toFixed(0)} to {f.high.toFixed(0)})</td><td className="n">{fcPeer.find((p) => p.year === f.year)?.value.toFixed(0)}</td></tr>
                      ))}
                    </tbody>
                  </table>
                }
                source={
                  <>
                    A forecast has to beat &quot;same as last year&quot; to be worth using. None did (best average miss {h.starts.forecast_mape_pct}%), so 2026 is shown as{" "}
                    {h.starts.msd_forecast_2026.toFixed(0)}, with a range of {h.starts.msd_forecast_2026_low.toFixed(0)} to {h.starts.msd_forecast_2026_high.toFixed(0)}. 2026 so far is{" "}
                    {h.starts.msd_starts_2026_ytd}, a part year with registrations still to come.
                  </>
                }
              >
                <StartsChart
                  msd={msdActual}
                  peers={peerActual}
                  msdYtd={{ year: 2026, value: msdYtd.studies }}
                  forecast={fcMsd}
                  band
                  peerForecast={fcPeer}
                  ariaLabel={`Pipeline studies started per year. MSD started ${h.starts.msd_starts_2025} in 2025 against a peer median of ${h.starts.peer_median_starts_2025}. The forecast for 2026 is ${h.starts.msd_forecast_2026.toFixed(0)}.`}
                />
              </Fig>
              <div className="pair even">
                <Fig
                  title="Share of finished studies that were terminated"
                  sub="Studies that ended in 2016 to 2025: completed or terminated"
                  table={
                    <table className="tbl">
                      <caption>Withdrawn and suspended studies are left out: they never ran or have not ended.</caption>
                      <thead><tr><th scope="col">Company</th><th scope="col" className="n">Completed</th><th scope="col" className="n">Terminated</th><th scope="col" className="n">Rate</th></tr></thead>
                      <tbody>
                        {[...d.starts.termination].sort((a, b) => b.termination_rate_pct - a.termination_rate_pct).map((t) => (
                          <tr key={t.grp} className={t.grp === "MSD" ? "hl" : undefined}><th scope="row" className="nm">{t.grp}</th><td className="n">{int(t.completed)}</td><td className="n">{int(t.terminated)}</td><td className="n">{pct1(t.termination_rate_pct)}</td></tr>
                        ))}
                      </tbody>
                    </table>
                  }
                  source={<>MSD {pct1(h.starts.msd_termination_rate_pct)}; the median of the 11 peers is {pct1(h.starts.peer_median_termination_rate_pct)}. Stop reasons are free text, so themes are indicative.</>}
                >
                  <BarChart rows={termRows} max={30} dot format="pct" ariaLabel={`Share of finished studies that were terminated. MSD ${pct1(h.starts.msd_termination_rate_pct)}, peer median ${pct1(h.starts.peer_median_termination_rate_pct)}.`} />
                </Fig>
                <figure className="fig">
                  <div className="fig-head">
                    <div>
                      <h3>How the forecast was tested</h3>
                      <p className="sub">Average miss when each year, 2020 to 2025, is forecast from the years before it</p>
                    </div>
                  </div>
                  <div className="tbl-wrap" tabIndex={0} role="region" aria-label="Table of how the forecast was tested">
                    <table className="tbl">
                      <caption>Three simple methods; the lowest average miss is used. Only a method that beats &quot;same as last year&quot; is worth more than it.</caption>
                      <thead><tr><th scope="col">Series</th><th scope="col">Method</th><th scope="col" className="n">Average miss</th><th scope="col">Beats same as last year</th></tr></thead>
                      <tbody>
                        {d.starts.backtest.map((b) => (
                          <tr key={`${b.segment}${b.method}`} className={b.chosen && b.segment === "MSD" ? "hl" : undefined}>
                            <th scope="row" className="nm">{b.segment === "MSD" ? "MSD" : "Peer median"}</th>
                            <td>{b.method === "naive" ? "same as last year" : b.method === "drift" ? "recent growth continues" : "straight-line trend"}{b.chosen ? " (used)" : ""}</td>
                            <td className="n">{pct1(b.mape_pct)}</td>
                            <td>{b.method === "naive" ? "baseline" : b.beats_naive ? "Yes" : "No"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </figure>
              </div>
            </div>
          </div>
        </section>

        {/* ------------------------------------------------------------------ gulf */}
        <section className="sec" id="gulf" aria-labelledby="h-gulf">
          <div className="shell">
            <div className="sec-head">
              <h2 id="h-gulf">
                {h.gulf.msd_gcc_pipeline_studies} of MSD&apos;s {int(summaryPipeline(d, "MSD"))} pipeline studies have a site in a Gulf state, the smallest share of the 12
              </h2>
              <p className="dek">
                Pipeline studies, any status, with at least one registered site in the UAE, Saudi Arabia, Qatar, Kuwait, Bahrain or Oman. A study can list more than one
                country, so rows do not add up to the total. A registered site may never have enrolled.
              </p>
            </div>
            <div className="sec-body">
              <figure className="fig">
                <div className="fig-head">
                  <div>
                    <h3>Studies with a site, by company and country</h3>
                    <p className="sub">Smallest share first, so MSD is the first row</p>
                  </div>
                </div>
                <div className="tbl-wrap" tabIndex={0} role="region" aria-label="Table of Gulf studies by company and country">
                  <table className="tbl heat">
                    <caption>Pipeline studies led by each company with a registered site in each Gulf country.</caption>
                    <thead>
                      <tr>
                        <th scope="col" className="scroll-col">Company</th>
                        {GULF.map(([, n]) => <th key={n} scope="col">{n}</th>)}
                        <th scope="col">Studies with a Gulf site</th>
                        <th scope="col">Share of its pipeline</th>
                      </tr>
                    </thead>
                    <tbody>
                      {gulfRows.map((g) => (
                        <tr key={g.grp} className={g.grp === "MSD" ? "hl" : undefined}>
                          <th scope="row" className="rowh scroll-col">{g.grp}</th>
                          {GULF.map(([iso]) => {
                            const v = gcell(g.grp, iso);
                            return <td key={iso} className={gtone(v)}>{v === 0 ? "No study" : v}</td>;
                          })}
                          <td>{g.gcc_studies}</td>
                          <td>{pct1(g.gcc_share_pct, 2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <figcaption className="src">
                  Source: ClinicalTrials.gov API v2, data as of {date}.{bahrain ? " Bahrain: no study from the 12 companies lists a site there." : ""}{" "}
                  {h.gulf.msd_removed_gcc_studies} MSD studies once listed a Gulf country and later removed it.
                </figcaption>
              </figure>
            </div>
          </div>
        </section>

        {/* ------------------------------------------------------------------ method */}
        <section className="sec" id="method" aria-labelledby="h-method">
          <div className="shell">
            <div className="sec-head">
              <h2 id="h-method">
                {int(h.snapshot.distinct_studies_fetched)} studies fetched, {int(h.snapshot.studies_in_scope)} kept, {int(h.snapshot.studies_quarantined)} set aside; {q.pass} of {q.checks}
                {" "}checks pass{q.info ? ` and ${q.info} are reported for information` : ""}
              </h2>
              <p className="dek">
                {h.snapshot.searches} searches returned {int(h.snapshot.api_rows)} rows. The search is full-text, so most of what it returns is not the company: a
                search for &quot;Bristol&quot; returns the University of Bristol. An ordered rule list decides who is who, and every set-aside study keeps its reason.
              </p>
            </div>
            <div className="sec-body">
              <div className="pair">
                <Fig
                  title="From search rows to studies in scope"
                  table={
                    <table className="tbl">
                      <caption>Each step keeps the studies it removes, with the reason.</caption>
                      <thead><tr><th scope="col">Step</th><th scope="col" className="n">Studies</th></tr></thead>
                      <tbody>
                        {wf.map((w) => (
                          <tr key={w.stage}><th scope="row" className="nm">{w.stage}</th><td className="n">{w.studies < 0 ? `−${int(-w.studies)}` : int(w.studies)}</td></tr>
                        ))}
                      </tbody>
                    </table>
                  }
                  source={<>Every count is tied to the totals the API announced, and the number of MSD studies matches a fresh call to the live API (2,189 on both sides).</>}
                >
                  <BarChart rows={wfRows} max={40000} ariaLabel={`From ${int(h.snapshot.api_rows)} search rows to ${int(h.snapshot.studies_in_scope)} studies in scope, with each set-aside group named.`} ticksCount={4} />
                </Fig>
                <div className="stack">
                  <p className="note">
                    <b>Sponsor names.</b> {int(h.snapshot.distinct_sponsor_names)} distinct lead-sponsor names were resolved to 12 companies. {int(h.harmonisation.merck_kgaa_set_aside)} studies of
                    Merck KGaA, a different company that owns the Merck name outside the US and Canada, are kept apart. {int(h.harmonisation.msd_acquired_studies)} studies ({pct1(h.harmonisation.msd_acquired_pct)}) were added to MSD
                    from companies it bought, such as Cubist, Acceleron and Prometheus; the same step adds {pct1(h.harmonisation.biggest_roll_up_gain_pct)} to {h.harmonisation.biggest_roll_up_gain}.
                  </p>
                  <p className="note">
                    <b>Therapeutic areas</b> come from the condition names people typed, then the registry&apos;s disease tags, then the molecule&apos;s usual area. The tags alone mislead: a lung-cancer
                    study that mentions PD-L1 is also tagged with a Parkinson disease term.
                  </p>
                </div>
              </div>
              <figure className="fig">
                <div className="fig-head">
                  <div><h3>The {q.checks} data-quality checks</h3><p className="sub">Run on every build. A failing check stops the build.</p></div>
                </div>
                <div className="tbl-wrap" tabIndex={0} role="region" aria-label="Table of the data-quality checks">
                  <table className="tbl">
                    <caption>{q.pass} pass, {q.warn} warn, {q.fail} fail, {q.info} reported for information.</caption>
                    <thead><tr><th scope="col">Check</th><th scope="col">Dimension</th><th scope="col">What it found</th><th scope="col">Result</th></tr></thead>
                    <tbody>
                      {d.quality.checks.map((c) => (
                        <tr key={c.id}><th scope="row" className="nm">{c.id} {c.name}</th><td>{c.dimension}</td><td>{String(c.result)}</td><td><Status s={c.status} /></td></tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </figure>
              <p className="limits">
                <b>What this is not.</b> A registered study is not a launch plan, and counts are studies, not programmes or value. Estimated dates slip, and a primary completion date is not a
                results announcement. The registry lags. Only studies the company itself leads are counted, so partner-led and investigator-led studies are missed. A registered site may never
                have enrolled. Acquisitions registered under names outside the {h.snapshot.searches} searches are missed. Revenue is US Medicaid pharmacy spend before rebates, not company
                revenue, and protection dates are FDA Orange Book core dates. Ownership is as of October 2026.
              </p>
            </div>
          </div>
        </section>
      </main>

      <footer className="foot">
        <div className="shell">
          <div className="foot-grid">
            <div>
              <h2>Sources</h2>
              <ul>
                {d.meta.sources.map((s) => (
                  <li key={s.name}><b>{s.name}</b>, {s.by}: {s.use}</li>
                ))}
              </ul>
            </div>
            <div>
              <h2>Method</h2>
              <ul>
                <li>Counts are studies the company itself leads, as registered on {date}.</li>
                <li>{int(h.snapshot.searches)} searches, {int(h.snapshot.distinct_sponsor_names)} sponsor names resolved, {q.checks} checks, {q.tests ? `${int(q.tests)} tests` : "tests on every change"}.</li>
                <li>The snapshot is frozen on purpose, so every number on this page agrees.</li>
              </ul>
            </div>
            <div>
              <h2>Take it further</h2>
              <ul>
                <li>
                  <a href={`/downloads/${EXCEL}`} download>Excel model{size ? ` (${size})` : ""}</a>: ranks the 12 companies on five measures, with weights you can change.
                </li>
                {repoUrl && <li><a href={repoUrl}>The code and the data-quality scorecard on GitHub</a></li>}
                <li>Part of a pair with Rx Market Pulse, which supplies Merck&apos;s product list and protection dates.</li>
              </ul>
            </div>
          </div>
          <p className="disc">An independent case study built from public data. Not produced or endorsed by MSD or any company named. Built {longDate(d.meta.built)}.</p>
        </div>
      </footer>
    </>
  );
}

function summaryPipeline(d: Dataset, g: string): number {
  return d.gulf.summary.find((s) => s.grp === g)?.pipeline_studies ?? 0;
}
