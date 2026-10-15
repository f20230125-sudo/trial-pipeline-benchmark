"use client";

import { useMemo, useRef, useState } from "react";
import { Frame, useView, useWidth } from "./chart";
import { ladderColumns, layoutLadder, neighbour } from "@/lib/derive";
import { int, longDate, pct1 } from "@/lib/format";
import type { ActiveStudyT } from "@/lib/schema";

const registry = (id: string) => `https://clinicaltrials.gov/study/${id}`;
const statusWords = (s: string) => s.toLowerCase().replaceAll("_", " ");

function describe(s: ActiveStudyT): string {
  const date = s.pc_date ? `Primary completion ${longDate(s.pc_date)} (${s.pc_type.toLowerCase()})` : "No primary completion date";
  return `${s.phase}, ${statusWords(s.status)}, ${s.area}. ${date}${s.is_overdue ? ", overdue" : ""}.`;
}

/** The first screen: one mark for each of MSD's active pipeline studies, in a column for each phase. */
export function Ladder({
  studies,
  molecule,
  share,
  inBase,
  asOf,
}: {
  studies: ActiveStudyT[];
  molecule: string;
  share: number;
  inBase: number;
  asOf: string;
}) {
  const [view, setView] = useView();
  const [wrapRef, width] = useWidth<HTMLDivElement>(640);
  const cols = useMemo(() => ladderColumns(studies), [studies]);
  const small = width < 560;
  const layout = useMemo(
    () =>
      layoutLadder(cols, small
        ? { perRow: 5, mark: 9, pitch: 11, colGap: 15, labelHeight: 74 }
        : { perRow: 7, mark: 13, pitch: 15, colGap: 23, labelHeight: 70 }),
    [cols, small],
  );
  const [active, setActive] = useState(0);
  const [selected, setSelected] = useState<number | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const berryTotal = studies.filter((s) => s.counts_toward_top_molecule).length;
  const scale = Math.min(1, width / layout.width);

  const focusMark = (order: number) => {
    setActive(order);
    setSelected(order);
    svgRef.current?.querySelector<SVGAElement>(`[data-order="${order}"]`)?.focus();
  };
  const onKey = (e: React.KeyboardEvent) => {
    if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End"].includes(e.key)) return;
    e.preventDefault();
    focusMark(neighbour(layout, active, e.key));
  };
  const chosen = selected != null ? layout.marks[selected]?.study : null;

  const table = (
    <table className="tbl">
      <caption>
        All {int(studies.length)} active pipeline studies led by MSD, as registered on {longDate(asOf)}. The last column says
        whether the study is in the {pct1(share)} figure.
      </caption>
      <thead>
        <tr>
          <th scope="col">Registry record</th>
          <th scope="col">Phase</th>
          <th scope="col">Status</th>
          <th scope="col">Area</th>
          <th scope="col">Primary completion</th>
          <th scope="col">Counts toward {molecule}</th>
        </tr>
      </thead>
      <tbody>
        {cols.flatMap((c) => c.studies).map((s) => (
          <tr key={s.nct_id} className={s.counts_toward_top_molecule ? "hl" : undefined}>
            <td>
              <a className="nct" href={registry(s.nct_id)} target="_blank" rel="noopener noreferrer">
                {s.nct_id}
              </a>
            </td>
            <td>{s.phase}</td>
            <td>{statusWords(s.status)}</td>
            <td>{s.area}</td>
            <td>
              {s.pc_date ? `${longDate(s.pc_date)} (${s.pc_type.toLowerCase()})` : "none"}
              {s.is_overdue ? ", overdue" : ""}
            </td>
            <td>{s.counts_toward_top_molecule ? "Yes" : "No"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );

  return (
    <Frame
      title={`MSD's ${int(studies.length)} active pipeline studies, by phase`}
      view={view}
      onView={setView}
      table={table}
      legend={
        <ul className="legend">
          <li>
            <i style={{ background: "var(--berry)" }} />
            Involves {molecule} ({int(berryTotal)} of {int(inBase)} at Phase 2 or later)
          </li>
          <li>
            <i style={{ background: "var(--mute)" }} />
            Other studies
          </li>
        </ul>
      }
      source={
        <>
          One mark is one registered study. Select a mark to see its record; press Enter or use the link to open it at
          ClinicalTrials.gov. Berry marks are the studies in the {pct1(share)} figure: studies at Phase 2 or later (counting
          Phase 1/2) that involve {molecule}. Phase 1 studies are outside that measure.
        </>
      }
    >
      <div ref={wrapRef}>
        <svg
          ref={svgRef}
          className="ladder"
          viewBox={`0 0 ${layout.width} ${layout.height}`}
          width={layout.width * scale}
          height={layout.height * scale}
          role="group"
          aria-label={`${int(studies.length)} active MSD pipeline studies in ${cols.length} phase columns: ${cols
            .map((c) => `${c.phase} ${c.total}`)
            .join(", ")}. ${int(berryTotal)} involve ${molecule}. Arrow keys move between studies.`}
          onKeyDown={onKey}
        >
          {layout.marks.map((m) => {
            const berry = m.study.counts_toward_top_molecule;
            const pad = small ? 1 : 1;
            return (
              <a
                key={m.study.nct_id}
                href={registry(m.study.nct_id)}
                target="_blank"
                rel="noopener noreferrer"
                data-order={m.order}
                tabIndex={m.order === active ? 0 : -1}
                aria-label={`${m.study.nct_id}. ${describe(m.study)}${berry ? ` Involves ${molecule}.` : ""}`}
                onFocus={() => {
                  setActive(m.order);
                  setSelected(m.order);
                }}
                onMouseEnter={() => setSelected(m.order)}
                onClick={(e) => {
                  // On a touch screen the first tap selects the mark (so its detail can be read); a second tap opens it.
                  if (window.matchMedia("(pointer: coarse)").matches && selected !== m.order) {
                    e.preventDefault();
                    setSelected(m.order);
                    setActive(m.order);
                  }
                }}
              >
                <rect
                  className={`mk${berry ? " b" : ""}${selected === m.order ? " sel" : ""}`}
                  style={{ ["--i" as string]: m.order }}
                  x={m.x}
                  y={m.y}
                  width={small ? 9 : 13}
                  height={small ? 9 : 13}
                />
                <rect x={m.x - pad} y={m.y - pad} width={(small ? 9 : 13) + pad * 2} height={(small ? 9 : 13) + pad * 2} fill="transparent" />
              </a>
            );
          })}
          <line className="foot-rule" x1={0} x2={layout.width} y1={layout.footY + 8} y2={layout.footY + 8} />
          {layout.columns.map((c) => (
            <g key={c.phase}>
              <text className="col-n" x={c.x} y={layout.footY + 34}>
                {c.total}
              </text>
              <text className="col-p" x={c.x} y={layout.footY + 52}>
                {c.phase}
              </text>
              {c.berry > 0 && (
                <text className="col-b" x={c.x} y={layout.footY + 68}>
                  {small ? c.berry : `${c.berry} ${molecule}`}
                </text>
              )}
            </g>
          ))}
        </svg>
        <p className="detail" aria-live="polite">
          {chosen ? (
            <>
              <a className="id" href={registry(chosen.nct_id)} target="_blank" rel="noopener noreferrer">
                {chosen.nct_id}
              </a>{" "}
              {describe(chosen)}
              {chosen.counts_toward_top_molecule ? ` Involves ${molecule}.` : ""} Opens the record at ClinicalTrials.gov.
            </>
          ) : (
            "Select a mark to see its registry record."
          )}
        </p>
      </div>
    </Frame>
  );
}
