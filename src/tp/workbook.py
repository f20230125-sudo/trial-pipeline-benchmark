"""Pipeline Benchmark Model: an Excel workbook that ranks MSD and 11 peers and lets the reader change the question.

    python -m tp.workbook            # writes excel/Pipeline-Benchmark-Model.xlsx

Every number on the Scorecard is a live formula (COUNTIFS over the Data sheet, PERCENTRANK.INC, RANK.EQ), so changing a
yellow input on the Inputs sheet recalculates the whole model. The Data sheet holds one row per pipeline study from the
warehouse; no result is pasted in. It is a comparison tool, not a pivot table: five measures are turned into percentiles
among the 12 companies, weighted, ranked and tiered, and the weights are the reader's choice.

The five measures (each is explained again on the Read me sheet):
    Size       studies counted (area, stage and status chosen on Inputs)
    Momentum   starts in the last 3 full years divided by the 3 before (at least 1)
    Readouts   late-stage active studies whose estimated primary completion falls in the window
    Execution  1 minus the percentile of the termination rate (fewer terminations is better)
    Gulf       share of the counted studies with a site in the UAE, Saudi Arabia, Qatar, Kuwait, Bahrain or Oman
"""

from __future__ import annotations

import csv
import json
from datetime import date, datetime
from pathlib import Path

import xlsxwriter

from . import areas as areas_mod
from . import sources as S

OUT = S.ROOT / "excel" / "Pipeline-Benchmark-Model.xlsx"

# One palette across the workbook, the dashboard and the Power BI kit (same family as Rx Market Pulse).
INK = "#16302F"
TEAL = "#0F766E"
TEAL_LIGHT = "#D9EEEA"
SLATE = "#5B6B73"
RULE = "#D5DEDD"
INPUT_FILL = "#FFF6D6"
INPUT_FONT = "#1D4ED8"
AMBER = "#B45309"
FOCUS_FILL = "#E3F1EE"

GROUPS = ["MSD", "AbbVie", "AstraZeneca", "BMS", "GSK", "J&J", "Lilly", "Novartis", "Novo Nordisk", "Pfizer", "Roche",
          "Sanofi"]
STAGES = ["All clinical", "Early (Phase 1)", "Mid (Phase 2)", "Late (Phase 3)"]
SCOPES = ["Active only", "All statuses"]
PRESETS = {  # weights: size, momentum, readouts, execution, gulf (percent)
    "Balanced": (30, 20, 20, 20, 10),
    "Near-term": (15, 15, 50, 10, 10),
    "Regional": (10, 10, 10, 10, 60),
}
MEASURES = ["Size", "Momentum", "Readouts", "Execution", "Gulf"]
DEFAULTS = {"focus": "MSD", "area": "All areas", "stage": "All clinical", "scope": "Active only", "window": 24,
            "preset": "Balanced"}

# Data sheet columns (row 1 is the header; data from row 2)
DATA_COLS = ["nct_id", "grp", "area", "phase", "stage", "active", "status_class", "status", "start_year", "real_start",
             "end_year", "pc_date", "pc_type", "gcc", "top_molecule"]
NUMERIC = {"start_year", "end_year"}

# Scorecard layout (1-based rows)
FIRST, LAST = 8, 19  # twelve companies


def load_rows() -> list[dict]:
    with (S.MARTS / "mart_study_export.csv").open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def load_expiring() -> list[dict]:
    with (S.REF / "rx_merck_families.csv").open(encoding="utf-8", newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if r["core_end"]]
    keep = [r for r in rows if "2026-01-01" <= r["core_end"] <= "2028-12-31"]
    return sorted(keep, key=lambda r: r["core_end"])


def as_of_date() -> date:
    m = json.loads(S.MANIFEST.read_text(encoding="utf-8"))
    return datetime.fromisoformat(m["dataTimestamp_start"]).date()


def build(path: Path = OUT) -> Path:
    rows = load_rows()
    n = len(rows)
    expiring = load_expiring()
    as_of = as_of_date()
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = xlsxwriter.Workbook(str(path), {"use_future_functions": True})
    wb.set_calc_mode("auto")
    wb.set_properties({"title": "Pipeline Benchmark Model", "author": "Mohammad Uzair Khan",
                       "comments": "Built from the public ClinicalTrials.gov registry (API data as of %s)." % as_of})

    base = {"font_name": "Calibri", "font_size": 10, "font_color": INK}
    f = lambda **kw: wb.add_format({**base, **kw})
    title = f(font_size=18, bold=True)
    sub = f(font_color=SLATE, italic=True)
    h = f(bold=True, font_color="white", bg_color=INK, valign="vcenter", text_wrap=True, align="center")
    h_left = f(bold=True, font_color="white", bg_color=INK, valign="vcenter", text_wrap=True)
    cell = f(bottom=1, bottom_color=RULE)
    cell_c = f(bottom=1, bottom_color=RULE, align="center")
    num0 = f(num_format="#,##0", bottom=1, bottom_color=RULE)
    num2 = f(num_format="0.00", bottom=1, bottom_color=RULE)
    pct1 = f(num_format="0.0%", bottom=1, bottom_color=RULE)
    pct0 = f(num_format="0%", bottom=1, bottom_color=RULE)
    pct0c = f(num_format="0%", bottom=1, bottom_color=RULE, align="center")
    money = f(num_format='$#,##0.0,,"M"', bottom=1, bottom_color=RULE)
    date_f = f(num_format="yyyy-mm-dd", bottom=1, bottom_color=RULE)
    label = f(bold=True, font_color=SLATE)
    bold = f(bold=True)
    note = f(font_color=SLATE, text_wrap=True, valign="top")
    inp = f(bg_color=INPUT_FILL, font_color=INPUT_FONT, border=1, border_color="#E6D9A8", bold=True, align="center")
    inp_pct = f(bg_color=INPUT_FILL, font_color=INPUT_FONT, border=1, border_color="#E6D9A8", bold=True,
                num_format="0", align="center")
    inp_date = f(bg_color=INPUT_FILL, font_color=INPUT_FONT, border=1, border_color="#E6D9A8", bold=True,
                 num_format="yyyy-mm-dd", align="center")
    calc_c = f(align="center", bold=True, bottom=1, bottom_color=RULE)
    ok = f(bold=True, font_color=TEAL)
    kpi = f(font_size=14, bold=True, font_color=TEAL)
    kpi_lbl = f(font_color=SLATE)

    ws_read = wb.add_worksheet("Read me")
    ws_in = wb.add_worksheet("Inputs")
    ws_sc = wb.add_worksheet("Scorecard")
    ws_mx = wb.add_worksheet("Area matrix")
    ws_ex = wb.add_worksheet("Expiring revenue")
    ws_ck = wb.add_worksheet("Checks")
    ws_data = wb.add_worksheet("Data")
    ws_lists = wb.add_worksheet("Lists")
    for ws, colour in ((ws_read, SLATE), (ws_in, "#CA8A04"), (ws_sc, TEAL), (ws_mx, TEAL), (ws_ex, TEAL), (ws_ck, SLATE),
                       (ws_data, "#94A3B8"), (ws_lists, "#94A3B8")):
        ws.set_tab_color(colour)
        ws.hide_gridlines(2)

    # ------------------------------------------------------------------ Lists (dropdown sources)
    area_list = ["All areas"] + [a for a in areas_mod.AREAS if a != "Unclassified"] + ["Unclassified"]
    ws_lists.write_row(0, 0, ["Companies"], h_left)
    for i, g in enumerate(GROUPS):
        ws_lists.write(i + 1, 0, g)
    ws_lists.write_row(0, 2, ["Areas"], h_left)
    for i, a in enumerate(area_list):
        ws_lists.write(i + 1, 2, a)
    ws_lists.write_row(0, 4, ["Stages"], h_left)
    for i, s in enumerate(STAGES):
        ws_lists.write(i + 1, 4, s)
    ws_lists.write_row(0, 6, ["Status scope"], h_left)
    for i, s in enumerate(SCOPES):
        ws_lists.write(i + 1, 6, s)
    ws_lists.write_row(0, 8, ["Window (months)"], h_left)
    for i, m in enumerate((12, 18, 24, 36)):
        ws_lists.write_number(i + 1, 8, m)
    ws_lists.write_row(0, 10, ["Presets"], h_left)
    for i, p in enumerate(list(PRESETS) + ["Custom"]):
        ws_lists.write(i + 1, 10, p)
    ws_lists.write_row(0, 12, ["Horizon year"], h_left)
    for i, y in enumerate((2026, 2027, 2028)):
        ws_lists.write_number(i + 1, 12, y)
    ws_lists.set_column(0, 12, 22)

    # ------------------------------------------------------------------ Data
    ws_data.write_row(0, 0, DATA_COLS, h_left)
    for i, r in enumerate(rows, start=1):
        for j, c in enumerate(DATA_COLS):
            v = r[c]
            if c in NUMERIC:
                if v != "":
                    ws_data.write_number(i, j, int(v))
            elif c == "pc_date":
                if v:
                    ws_data.write_datetime(i, j, datetime.fromisoformat(v), date_f)
            else:
                ws_data.write_string(i, j, v)
    last = n + 1
    ws_data.freeze_panes(1, 0)
    ws_data.set_column(0, 0, 13)
    ws_data.set_column(1, 14, 16)
    ws_data.set_column(11, 11, 12, date_f)
    colname = {c: chr(ord("A") + k) for k, c in enumerate(DATA_COLS)}
    for c in DATA_COLS:
        wb.define_name(f"d_{c}", f"=Data!${colname[c]}$2:${colname[c]}${last}")

    # ------------------------------------------------------------------ Inputs
    ws_in.set_column(0, 0, 2)
    ws_in.set_column(1, 1, 30)
    ws_in.set_column(2, 8, 16)
    ws_in.write("B1", "Pipeline Benchmark Model: inputs", title)
    ws_in.write("B2", "Change the yellow cells. Every number on the other sheets recalculates.", sub)
    labels = [("Focus company (highlighted)", "FocusSponsor", DEFAULTS["focus"], "Lists!$A$2:$A$13"),
              ("Therapeutic area", "AreaSel", DEFAULTS["area"], f"Lists!$C$2:$C${len(area_list) + 1}"),
              ("Stage", "StageSel", DEFAULTS["stage"], "Lists!$E$2:$E$5"),
              ("Studies counted", "ScopeSel", DEFAULTS["scope"], "Lists!$G$2:$G$3"),
              ("Readout window (months)", "WindowMonths", DEFAULTS["window"], "Lists!$I$2:$I$5")]
    for k, (lab, name, val, src) in enumerate(labels):
        r = 4 + k  # rows 4..8
        ws_in.write(r - 1, 1, lab, label)
        if isinstance(val, int):
            ws_in.write_number(r - 1, 2, val, inp_pct)
        else:
            ws_in.write_string(r - 1, 2, val, inp)
        ws_in.data_validation(r - 1, 2, r - 1, 2, {"validate": "list", "source": "=" + src})
        wb.define_name(name, f"=Inputs!$C${r}")
    ws_in.write("B9", "Data date", label)
    ws_in.write_datetime("C9", datetime.combine(as_of, datetime.min.time()), inp_date)
    wb.define_name("AsOf", "=Inputs!$C$9")
    ws_in.write("D9", "the API's data date; a month is the unit for windows", sub)
    ws_in.write("B10", "Weighting preset", label)
    ws_in.write_string("C10", DEFAULTS["preset"], inp)
    ws_in.data_validation("C10", {"validate": "list", "source": "=Lists!$K$2:$K$5"})
    wb.define_name("Preset", "=Inputs!$C$10")

    ws_in.write("B12", "Weights (percent)", h_left)
    ws_in.write_row("C12", MEASURES + ["Total"], h)
    for k, (name, w) in enumerate(PRESETS.items()):
        r = 13 + k  # 13..15
        ws_in.write(r - 1, 1, name, cell)
        for j, v in enumerate(w):
            ws_in.write_number(r - 1, 2 + j, v, num0)
        ws_in.write_formula(r - 1, 7, f"=SUM(C{r}:G{r})", num0)
    ws_in.write("B16", "Custom (yours)", f(bold=True, bottom=1, bottom_color=RULE))
    for j, v in enumerate((25, 25, 25, 15, 10)):
        ws_in.write_number(15, 2 + j, v, inp_pct)
    ws_in.write_formula("H16", "=SUM(C16:G16)", num0)
    ws_in.write("B17", "In use", f(bold=True, top=2, top_color=INK))
    for j in range(5):
        col = chr(ord("C") + j)
        ws_in.write_formula(16, 2 + j, f'=INDEX({col}13:{col}16,MATCH(Preset,Lists!$K$2:$K$5,0))',
                            f(bold=True, top=2, top_color=INK, num_format="0", align="right"))
    ws_in.write_formula("H17", "=SUM(C17:G17)", f(bold=True, top=2, top_color=INK, num_format="0"))
    ws_in.write("I17", "must be 100", sub)
    for j, nm in enumerate(["w_size", "w_mom", "w_near", "w_exec", "w_gulf"]):
        wb.define_name(nm, f"=Inputs!${chr(ord('C') + j)}$17")

    ws_in.write("B19", "Derived criteria (do not edit)", h_left)
    ws_in.write("C19", "", h_left)
    crit = [
        ("Area criterion", "AreaCrit", '=IF(AreaSel="All areas","*",AreaSel)'),
        ("Stage criterion", "StageCrit",
         '=IF(StageSel="All clinical","*",IF(LEFT(StageSel,5)="Early","Early",IF(LEFT(StageSel,3)="Mid","Mid","Late")))'),
        ("Status criterion", "ScopeCrit", '=IF(ScopeSel="Active only","Yes","*")'),
        ("Month of the data date", "MonthStart", "=DATE(YEAR(AsOf),MONTH(AsOf),1)"),
        ("Window ends before", "WindowEnd", "=EDATE(MonthStart,WindowMonths)"),
    ]
    for k, (lab, name, fx) in enumerate(crit):
        r = 20 + k
        ws_in.write(r - 1, 1, lab, cell)
        ws_in.write_formula(r - 1, 2, fx, date_f if name in ("MonthStart", "WindowEnd") else cell_c)
        wb.define_name(name, f"=Inputs!$C${r}")

    # ------------------------------------------------------------------ Scorecard
    ws_sc.set_column(0, 0, 16)
    ws_sc.set_column(1, 10, 11)
    ws_sc.set_column(11, 15, 10)
    ws_sc.set_column(16, 18, 9)
    ws_sc.set_column(19, 19, 12)
    ws_sc.write("A1", "Scorecard: 12 companies on five measures", title)
    ws_sc.write_formula("A2", '="Area: "&AreaSel&"  |  Stage: "&StageSel&"  |  Counting: "&ScopeSel&"  |  Window: "&WindowMonths&" months  |  Weights: "&Preset', sub)
    # focus box
    ws_sc.write("A4", "Focus", label)
    ws_sc.write_formula("B4", "=FocusSponsor", kpi)
    ws_sc.write("D4", "Rank", kpi_lbl)
    ws_sc.write_formula("E4", f'=INDEX($R${FIRST}:$R${LAST},MATCH(FocusSponsor,$A${FIRST}:$A${LAST},0))', kpi)
    ws_sc.write("F4", "of 12", kpi_lbl)
    ws_sc.write("G4", "Tier", kpi_lbl)
    ws_sc.write_formula("H4", f'=INDEX($S${FIRST}:$S${LAST},MATCH(FocusSponsor,$A${FIRST}:$A${LAST},0))', kpi)
    ws_sc.write("I4", "Studies", kpi_lbl)
    ws_sc.write_formula("J4", f'=INDEX($B${FIRST}:$B${LAST},MATCH(FocusSponsor,$A${FIRST}:$A${LAST},0))', kpi)
    ws_sc.write("K4", "Peer median", kpi_lbl)
    ws_sc.write_formula("L4", f"=MEDIAN($T${FIRST}:$T${LAST})", kpi)
    ws_sc.write("M4", "Gap", kpi_lbl)
    ws_sc.write_formula("N4", "=J4-L4", kpi)

    headers = ["Company", "Studies counted", "Starts, last 3 years", "Starts, 3 years before", "Momentum (ratio)",
               "Late-stage readouts due", "Terminated", "Completed", "Termination rate", "Gulf studies", "Gulf share",
               "Size pct", "Momentum pct", "Readouts pct", "Execution pct", "Gulf pct", "Score", "Rank", "Tier",
               "Peers' studies (helper)"]
    ws_sc.set_row(6, 42)
    ws_sc.write_row(6, 0, headers, h)
    ws_sc.write("K6", "Weights (percent):", f(font_color=SLATE, align="right"))
    # weights for the five percentile columns sit above them (L..P = columns 11..15)
    for j, nm in enumerate(["w_size", "w_mom", "w_near", "w_exec", "w_gulf"]):
        ws_sc.write_formula(5, 11 + j, f"={nm}", f(bold=True, align="center", num_format="0"))
    for i, g in enumerate(GROUPS):
        r = FIRST + i
        ws_sc.write_string(r - 1, 0, g, f(bold=True, bottom=1, bottom_color=RULE))
        flt = 'd_area,AreaCrit,d_stage,StageCrit'
        ws_sc.write_formula(r - 1, 1, f'=COUNTIFS(d_grp,$A{r},{flt},d_active,ScopeCrit)', num0)
        y0 = "YEAR(AsOf)"
        ws_sc.write_formula(r - 1, 2, f'=COUNTIFS(d_grp,$A{r},{flt},d_real_start,"Yes",d_start_year,">="&({y0}-3),d_start_year,"<="&({y0}-1))', num0)
        ws_sc.write_formula(r - 1, 3, f'=COUNTIFS(d_grp,$A{r},{flt},d_real_start,"Yes",d_start_year,">="&({y0}-6),d_start_year,"<="&({y0}-4))', num0)
        ws_sc.write_formula(r - 1, 4, f"=C{r}/MAX(D{r},1)", num2)
        ws_sc.write_formula(r - 1, 5, f'=COUNTIFS(d_grp,$A{r},d_area,AreaCrit,d_stage,"Late",d_active,"Yes",d_pc_type,"ESTIMATED",d_pc_date,">="&MonthStart,d_pc_date,"<"&WindowEnd)', num0)
        ws_sc.write_formula(r - 1, 6, f'=COUNTIFS(d_grp,$A{r},{flt},d_status,"TERMINATED",d_end_year,">=2016",d_end_year,"<=2025")', num0)
        ws_sc.write_formula(r - 1, 7, f'=COUNTIFS(d_grp,$A{r},{flt},d_status,"COMPLETED",d_end_year,">=2016",d_end_year,"<=2025")', num0)
        ws_sc.write_formula(r - 1, 8, f'=IF(G{r}+H{r}<10,"n/a",G{r}/(G{r}+H{r}))', pct1)
        ws_sc.write_formula(r - 1, 9, f'=COUNTIFS(d_grp,$A{r},{flt},d_active,ScopeCrit,d_gcc,"Yes")', num0)
        ws_sc.write_formula(r - 1, 10, f"=IF(B{r}=0,0,J{r}/B{r})", pct1)
        rng = lambda col: f"{col}${FIRST}:{col}${LAST}"
        ws_sc.write_formula(r - 1, 11, f"=PERCENTRANK.INC({rng('B')},B{r},6)", num2)
        ws_sc.write_formula(r - 1, 12, f"=PERCENTRANK.INC({rng('E')},E{r},6)", num2)
        ws_sc.write_formula(r - 1, 13, f"=PERCENTRANK.INC({rng('F')},F{r},6)", num2)
        ws_sc.write_formula(r - 1, 14, f'=IF(I{r}="n/a",0.5,1-PERCENTRANK.INC({rng("I")},I{r},6))', num2)
        ws_sc.write_formula(r - 1, 15, f"=PERCENTRANK.INC({rng('K')},K{r},6)", num2)
        ws_sc.write_formula(r - 1, 16, f"=ROUND(SUMPRODUCT(L{r}:P{r},$L$6:$P$6)/SUM($L$6:$P$6),9)", f(num_format="0.000", bold=True, bottom=1, bottom_color=RULE))
        ws_sc.write_formula(r - 1, 17, f"=RANK.EQ(Q{r},{rng('Q')},0)+COUNTIF($Q${FIRST}:Q{r},Q{r})-1", calc_c)
        ws_sc.write_formula(r - 1, 18, f'=IF(R{r}<=4,"A",IF(R{r}<=8,"B","C"))', calc_c)
        ws_sc.write_formula(r - 1, 19, f'=IF(A{r}=FocusSponsor,"",B{r})', f(font_color=SLATE, num_format="#,##0", bottom=1, bottom_color=RULE))
    ws_sc.conditional_format(f"A{FIRST}:T{LAST}", {"type": "formula", "criteria": f"=$A{FIRST}=FocusSponsor",
                                                    "format": wb.add_format({"bg_color": FOCUS_FILL})})
    ws_sc.conditional_format(f"S{FIRST}:S{LAST}", {"type": "cell", "criteria": "==", "value": '"A"',
                                                    "format": wb.add_format({"font_color": TEAL, "bold": True})})
    ws_sc.conditional_format(f"Q{FIRST}:Q{LAST}", {"type": "data_bar", "bar_color": "#9CCFC7", "bar_solid": True})
    ws_sc.freeze_panes(FIRST - 1, 1)
    ws_sc.write(FIRST + 12, 0, "Reading it", bold)
    notes = [
        "Each of the five measures becomes a percentile among the 12 companies (0 = lowest, 1 = highest), so one very large company cannot swamp the rest.",
        "Score = weighted average of the five percentiles (rounded to 9 decimals so that equal scores are exactly equal); the weights are on the Inputs sheet. Rank 1 = best; ties keep the order of the list. Tier A = rank 1 to 4, B = 5 to 8, C = 9 to 12.",
        "Execution = 1 minus the percentile of the termination rate (completed or terminated with an end year 2016 to 2025). A company with fewer than 10 ended studies in the selection gets a neutral 0.5.",
        "Readouts always counts late-stage (Phase 3 or 2/3) active studies, whatever Stage is chosen: it answers 'what reads out soon'. Estimated dates slip and a primary completion is not a results announcement.",
        "Counts are studies the company itself leads, as registered; not programmes, not value. Sites are as registered. Read the Read me sheet for the limits.",
    ]
    for k, t in enumerate(notes):
        ws_sc.merge_range(FIRST + 13 + k, 0, FIRST + 13 + k, 15, t, note)
        ws_sc.set_row(FIRST + 13 + k, 28)

    # ------------------------------------------------------------------ Area matrix
    ws_mx.set_column(0, 0, 16)
    ws_mx.set_column(1, 18, 11)
    ws_mx.write("A1", "Area matrix: studies by company and therapeutic area", title)
    ws_mx.write_formula("A2", '="Stage: "&StageSel&"  |  Counting: "&ScopeSel&"  (area is shown by column; the area input does not apply here)"', sub)
    mx_areas = area_list[1:]
    ws_mx.set_row(3, 54)
    ws_mx.write("A4", "Company", h_left)
    for j, a in enumerate(mx_areas):
        ws_mx.write_string(3, 1 + j, a, h)
    ws_mx.write(3, 1 + len(mx_areas), "Total", h)
    for i, g in enumerate(GROUPS):
        r = 5 + i
        ws_mx.write_string(r - 1, 0, g, f(bold=True, bottom=1, bottom_color=RULE))
        for j, _ in enumerate(mx_areas):
            col = xlsxwriter.utility.xl_col_to_name(1 + j)
            ws_mx.write_formula(r - 1, 1 + j, f'=COUNTIFS(d_grp,$A{r},d_area,{col}$4,d_stage,StageCrit,d_active,ScopeCrit)', num0)
        lastc = xlsxwriter.utility.xl_col_to_name(len(mx_areas))
        ws_mx.write_formula(r - 1, 1 + len(mx_areas), f"=SUM(B{r}:{lastc}{r})", f(bold=True, num_format="#,##0", bottom=1, bottom_color=RULE))
    ws_mx.write(16, 0, "All 12", f(bold=True, top=2, top_color=INK))
    for j in range(len(mx_areas) + 1):
        col = xlsxwriter.utility.xl_col_to_name(1 + j)
        ws_mx.write_formula(16, 1 + j, f"=SUM({col}5:{col}16)", f(bold=True, top=2, top_color=INK, num_format="#,##0"))
    ws_mx.conditional_format(f"B5:{xlsxwriter.utility.xl_col_to_name(len(mx_areas))}16",
                             {"type": "3_color_scale", "min_color": "#FFFFFF", "mid_color": "#CFE8E3", "max_color": "#2F8F83"})
    ws_mx.write_formula("A19", '="Share of the focus company in each area is on the row for "&FocusSponsor&" above; the heat map is relative to the whole table."', sub)
    ws_mx.freeze_panes(4, 1)

    # ------------------------------------------------------------------ Expiring revenue
    ws_ex.set_column(0, 0, 16)
    ws_ex.set_column(1, 1, 30)
    ws_ex.set_column(2, 8, 14)
    ws_ex.write("A1", "Expiring revenue against the pipeline behind it", title)
    ws_ex.write("A2", "Merck products whose FDA Orange Book core protection ends by the horizon year, with 2025 US Medicaid pharmacy spend before rebates (a signal of scale, not company revenue).", sub)
    ws_ex.write("A4", "Horizon year", label)
    ws_ex.write_number("C4", 2028, inp_pct)
    ws_ex.data_validation("C4", {"validate": "list", "source": "=Lists!$M$2:$M$4"})
    wb.define_name("HorizonYear", "='Expiring revenue'!$C$4")
    ws_ex.write("A6", "Product", h_left)
    ws_ex.write_row("B6", ["Therapeutic area", "2025 Medicaid spend", "Core protection ends", "Counts at horizon"], h)
    for i, r in enumerate(expiring):
        rr = 7 + i
        ws_ex.write_string(rr - 1, 0, r["family"], f(bold=True, bottom=1, bottom_color=RULE))
        ws_ex.write_string(rr - 1, 1, r["area"], cell)
        ws_ex.write_number(rr - 1, 2, int(r["spend_2025"]), money)
        ws_ex.write_datetime(rr - 1, 3, datetime.fromisoformat(r["core_end"]), date_f)
        ws_ex.write_formula(rr - 1, 4, f'=IF(YEAR(D{rr})<=HorizonYear,"Yes","No")', cell_c)
    e_first, e_last = 7, 6 + len(expiring)
    ws_ex.write("A12", "Area", h_left)
    ws_ex.write_row("B12", ["Spend at risk by horizon", "MSD late-stage active studies", "Peer median late-stage active studies",
                            "MSD rank (1 = most studies)"], h)
    ws_ex.set_row(11, 44)
    ex_areas = sorted({r["area"] for r in expiring})
    # helper block: late-stage active studies per company for each area
    ws_ex.write("A22", "Helper: late-stage active studies by company and area", label)
    ws_ex.write("A23", "Company", h_left)
    for j, a in enumerate(ex_areas):
        ws_ex.write_string(22, 1 + j, a, h)
        ws_ex.write_string(22, 1 + len(ex_areas) + j, a + " (peers)", h)
    ws_ex.set_row(22, 44)
    for i, g in enumerate(GROUPS):
        rr = 24 + i
        ws_ex.write_string(rr - 1, 0, g, cell)
        for j, a in enumerate(ex_areas):
            col = xlsxwriter.utility.xl_col_to_name(1 + j)
            ws_ex.write_formula(rr - 1, 1 + j, f'=COUNTIFS(d_grp,$A{rr},d_area,{col}$23,d_stage,"Late",d_active,"Yes")', num0)
            pc = xlsxwriter.utility.xl_col_to_name(1 + len(ex_areas) + j)
            ws_ex.write_formula(rr - 1, 1 + len(ex_areas) + j, f'=IF($A{rr}="MSD","",{col}{rr})', f(font_color=SLATE, bottom=1, bottom_color=RULE))
    for k, a in enumerate(ex_areas):
        rr = 13 + k
        ws_ex.write_string(rr - 1, 0, a, f(bold=True, bottom=1, bottom_color=RULE))
        ws_ex.write_formula(rr - 1, 1, f'=SUMIFS($C${e_first}:$C${e_last},$B${e_first}:$B${e_last},$A{rr},$E${e_first}:$E${e_last},"Yes")', money)
        col = xlsxwriter.utility.xl_col_to_name(1 + k)
        pcol = xlsxwriter.utility.xl_col_to_name(1 + len(ex_areas) + k)
        ws_ex.write_formula(rr - 1, 2, f"={col}24", num0)  # MSD is the first company row
        ws_ex.write_formula(rr - 1, 3, f"=MEDIAN({pcol}24:{pcol}35)", f(num_format="0.0", bottom=1, bottom_color=RULE))
        ws_ex.write_formula(rr - 1, 4, f"=COUNTIF({col}25:{col}35,\">\"&C{rr})+1", cell_c)
    ws_ex.write("A18", "Reading it: where spend is at risk and MSD has few or no late-stage active studies in the same area, "
                       "the nearest pipeline cover is thin. A study count is not a probability of launch.", note)

    # ------------------------------------------------------------------ Checks
    ws_ck.set_column(0, 0, 4)
    ws_ck.set_column(1, 1, 62)
    ws_ck.set_column(2, 3, 16)
    ws_ck.set_column(4, 4, 10)
    ws_ck.write("B1", "Checks", title)
    ws_ck.write_row("B3", ["Check", "Expected", "Found", "Result"], h_left)
    checks = [
        ("Weights in use add up to 100", "100", "=SUM(Inputs!C17:G17)", '=IF(D5=100,"OK","CHECK")'),
        ("Data rows loaded (one per pipeline study)", str(n), "=COUNTA(d_nct_id)", f'=IF(D6={n},"OK","CHECK")'),
        ("The 12 companies' studies add up to every study matching the area, stage and status chosen",
         '=COUNTIFS(d_area,AreaCrit,d_stage,StageCrit,d_active,ScopeCrit)', f"=SUM(Scorecard!B{FIRST}:B{LAST})", '=IF(D7=C7,"OK","CHECK")'),
        ("The area matrix adds up to every study matching the stage and status chosen",
         '=COUNTIFS(d_stage,StageCrit,d_active,ScopeCrit)', "='Area matrix'!S17", '=IF(D8=C8,"OK","CHECK")'),
        ("Ranks are 1 to 12 with no gaps", "78", f"=SUM(Scorecard!R{FIRST}:R{LAST})", '=IF(D9=78,"OK","CHECK")'),
        ("Every study belongs to one of the 12 companies", "0", '=COUNTA(d_nct_id)-SUMPRODUCT(COUNTIF(d_grp,Lists!A2:A13))', '=IF(D10=0,"OK","CHECK")'),
    ]
    for k, (lab, exp, fx, res) in enumerate(checks):
        r = 5 + k
        ws_ck.write_string(r - 1, 1, lab, cell)
        if exp.startswith("="):
            ws_ck.write_formula(r - 1, 2, exp, num0)
        else:
            ws_ck.write_number(r - 1, 2, float(exp), num0)
        ws_ck.write_formula(r - 1, 3, fx, num0)
        ws_ck.write_formula(r - 1, 4, res, ok)
    ws_ck.write("B12", "Overall", bold)
    ws_ck.write_formula("E12", '=IF(COUNTIF(E5:E10,"OK")=6,"ALL OK","CHECK")', ok)
    ws_ck.conditional_format("E5:E12", {"type": "text", "criteria": "containing", "value": "CHECK",
                                         "format": wb.add_format({"font_color": "#B91C1C", "bold": True})})

    # ------------------------------------------------------------------ Read me
    ws_read.set_column(0, 0, 3)
    ws_read.set_column(1, 1, 110)
    ws_read.write("B1", "Pipeline Benchmark Model", title)
    ws_read.write("B2", "MSD and 11 peers on the public ClinicalTrials.gov registry (API data as of %s)" % as_of, sub)
    paras = [
        ("What this is", "A comparison tool built on one row per drug-development study (24,692 rows on the Data sheet): interventional drug, "
                         "biological, genetic or combination-product studies in Phase 1 to 3, led by one of 12 companies. Change the yellow cells on Inputs "
                         "and the Scorecard, Area matrix and Expiring revenue sheets recalculate."),
        ("How to use it", "1) Pick a focus company, an area, a stage and whether to count only active studies. 2) Pick a weighting preset, or choose Custom "
                          "and type your own weights. 3) Read the Scorecard: rank, tier and the gap to the median of the other 11. 4) Open Area matrix to see "
                          "where each company works, and Expiring revenue to set Merck's protection dates beside its late-stage pipeline."),
        ("The five measures", "Size: studies counted. Momentum: starts in the last 3 full years divided by the 3 before. Readouts: late-stage active studies whose "
                              "estimated primary completion falls in the window. Execution: 1 minus the percentile of the termination rate. Gulf: share of "
                              "counted studies with a site in the UAE, Saudi Arabia, Qatar, Kuwait, Bahrain or Oman."),
        ("Where the data comes from", "The ClinicalTrials.gov API v2, downloaded in 44 searches and harmonised by the Python pipeline in this repository: sponsor names "
                                      "rolled up to 12 companies, a therapeutic area for each study, molecule keys, dates with their precision. The 'Merck' search "
                                      "also returns Merck KGaA, a different company, which is kept out. Merck's product list and protection dates come from the "
                                      "sibling project Rx Market Pulse."),
        ("What it is not", "A registered study is not a launch plan, and counts are studies, not programmes or value. Estimated dates slip, and a primary completion "
                           "date is not a results announcement. Only studies the company itself leads are counted. Sites are as registered. Revenue figures are US "
                           "Medicaid pharmacy spend before rebates, not company revenue; protection dates are FDA Orange Book core dates (a biologic such as "
                           "Keytruda has none). Ownership is as of October 2026."),
        ("How it was checked", "Excel itself was driven through six input scenarios and every number on the Scorecard was compared, company by company, with a "
                               "separate Python calculation that shares no code with this workbook (tools/verify_workbook.py)."),
    ]
    row = 3
    for head, text in paras:
        ws_read.write(row, 1, head, bold)
        ws_read.write(row + 1, 1, text, note)
        ws_read.set_row(row + 1, 62)
        row += 3
    ws_in.activate()
    wb.close()
    return path


def main() -> int:
    p = build()
    print(f"wrote {p} ({p.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
