import { z } from "zod";

// Every data file is validated when the site is built. If the pipeline changes a field, the build fails here, with the file
// and the field named, instead of the page quietly showing a wrong or missing number.

const num = z.number();
const str = z.string();
const maybeStr = z.string().nullable();

export const Group = z.object({ grp: str, short_name: str, is_focus: z.boolean(), sort_order: num });

export const Meta = z.object({
  built: str,
  asOf: str,
  dataTimestamp: str,
  api: str,
  groups: z.array(Group).length(12),
  areas: z.array(str).length(17),
  phases: z.array(str),
  sources: z.array(z.object({ name: str, by: str, use: str })),
});

export const Summary = z.object({
  sort_order: num,
  grp: str,
  studies_in_scope: num,
  parent_studies: num,
  acquired_studies: num,
  pipeline_studies: num,
  active_pipeline: num,
  active_p1: num,
  active_p2: num,
  active_late: num,
  pipeline_gcc_studies: num,
  active_gcc_studies: num,
  overdue_active: num,
  active_pipeline_rank: num,
  active_late_rank: num,
});
export const Overview = z.object({
  summary: z.array(Summary).length(12),
  phase: z.array(z.object({ grp: str, phase: str, phase_rank: num, studies: num })),
  area: z.array(z.object({ grp: str, area: str, area_order: num, studies: num, share_pct: num })),
});

export const Concentration = z.object({
  top: z.array(z.object({ grp: str, rank: num, molecule: str, studies: num, studies_p23: num, share_pct: num })),
  concentration: z.array(
    z.object({ grp: str, top_molecule: str, top_studies: num, studies_p23: num, share_pct: num, concentration_rank: num }),
  ),
  ecosystem: z.array(z.object({ category: str, studies: num, share_pct: num })),
});

export const Revenue = z.object({
  expiring: z.array(
    z.object({
      area: str,
      families: str,
      spend_2025_at_risk: num,
      earliest_core_end: str,
      msd_active_pipeline: num,
      msd_active_late: num,
      msd_molecules: num,
      peer_median_active_late: num,
      msd_rank_active_late: num,
    }),
  ),
  franchise: z.array(
    z.object({
      family: str,
      franchise: str,
      area: str,
      spend_2025: num,
      status: str,
      core_end: maybeStr,
      last_end: maybeStr,
      studies_all: num,
      active_pipeline: num,
      active_late: num,
    }),
  ),
});

export const Readouts = z.object({
  quarter: z.array(z.object({ grp: str, quarter: str, studies: num })),
  summary: z.array(z.object({ grp: str, readouts_24m: num, overdue_late: num, active_late: num })),
  msd: z.array(
    z.object({
      nct_id: str,
      title: str,
      area: str,
      phase: str,
      top_molecule: maybeStr,
      status: str,
      pc_date: str,
      pc_type: str,
      enrollment_count: num.nullable(),
      has_gcc_site: z.boolean(),
      merck_products: maybeStr,
    }),
  ),
});

export const Starts = z.object({
  byGroup: z.array(z.object({ grp: str, year: num, studies: num, partial_year: z.boolean() })),
  peerMedian: z.array(z.object({ year: num, median_studies: num, partial_year: z.boolean() })),
  termination: z.array(z.object({ grp: str, completed: num, terminated: num, termination_rate_pct: num })),
  stopThemes: z.array(z.object({ grp: str, theme: str, studies: num })),
  forecast: z.array(
    z.object({ segment: str, year: num, kind: z.enum(["actual", "forecast"]), studies: num, low: num.nullable(), high: num.nullable(), method: maybeStr }),
  ),
  backtest: z.array(z.object({ segment: str, method: str, mape_pct: num, beats_naive: z.boolean(), chosen: z.boolean() })),
});

export const Gulf = z.object({
  summary: z.array(
    z.object({
      grp: str,
      pipeline_studies: num,
      gcc_studies: num,
      gcc_active_studies: num,
      gcc_share_pct: num,
      removed_gcc_studies: num,
      mena_studies: num,
    }),
  ),
  country: z.array(z.object({ grp: str, iso3: str, country: str, studies: num, active_studies: num, sites: num })),
  removed: z.array(z.object({ grp: str, iso3: str, country: str, studies: num })),
});

export const Quality = z.object({
  checks: z.array(
    z.object({
      id: str,
      dimension: str,
      name: str,
      result: z.union([str, num]),
      rule: z.union([str, num]).nullable(),
      status: z.enum(["pass", "warn", "fail", "info"]),
      studies: num.nullable(),
      note: maybeStr,
    }),
  ),
  waterfall: z.array(z.object({ stage: str, studies: num })),
  gain: z.array(z.object({ grp: str, parent_studies: num, acquired_studies: num, gain_pct: num })),
});

export const ActiveStudy = z.object({
  nct_id: z.string().regex(/^NCT\d{8}$/),
  title: str,
  area: str,
  phase: str,
  phase_max: num,
  status: str,
  start_date: maybeStr,
  pc_date: maybeStr,
  pc_type: str,
  top_molecule: maybeStr,
  enrollment_count: num.nullable(),
  has_gcc_site: z.boolean(),
  is_late: z.boolean(),
  is_overdue: z.boolean(),
  counts_toward_top_molecule: z.boolean(),
  merck_products: maybeStr,
});
export const MsdActive = z.array(ActiveStudy);

export const Headline = z.object({
  snapshot: z.object({
    api_data_timestamp: str,
    as_of: str,
    searches: num,
    api_rows: num,
    distinct_studies_fetched: num,
    studies_in_scope: num,
    studies_quarantined: num,
    distinct_sponsor_names: num,
    groups: num,
    peers: num,
  }),
  quality: z.object({ checks: num, pass: num, warn: num, fail: num, info: num, tests: num.nullable() }),
  harmonisation: z.object({
    msd_in_scope: num,
    msd_acquired_studies: num,
    msd_acquired_pct: num,
    merck_kgaa_set_aside: num,
    biggest_roll_up_gain: str,
    biggest_roll_up_gain_pct: num,
  }),
  pipeline: z.object({
    msd_active_pipeline: num,
    msd_active_pipeline_rank: num,
    msd_active_late: num,
    msd_active_late_rank: num,
    largest_active_pipeline_group: maybeStr,
    largest_active_pipeline: num,
  }),
  concentration: z.object({
    msd_top_molecule: str,
    msd_top_molecule_studies: num,
    msd_studies_p23: num,
    msd_share_pct: num,
    msd_concentration_rank: num,
    second_group: str,
    second_molecule: str,
    second_share_pct: num,
    msd_top3: z.array(z.object({ molecule: str, studies: num, share_pct: num })),
    pembrolizumab_active_studies_all_sponsors: num,
    pembrolizumab_msd_led: num,
    pembrolizumab_msd_led_pct: num,
    msd_keytruda_linked_active_pipeline: num,
    merck_families_matched: num,
  }),
  expiring_revenue: z.object({
    top_area: str,
    top_families: str,
    top_spend_2025: num,
    top_msd_active_late: num,
    top_peer_median_active_late: num,
    total_spend_at_risk_2026_28: num,
  }),
  readouts: z.object({
    window: str,
    msd_readouts_24m: num,
    azn_readouts_24m: num,
    max_readouts_24m_group: str,
    msd_overdue_late: num,
    overdue_active_all_groups: num,
  }),
  starts: z.object({
    msd_starts_2025: num,
    msd_starts_2026_ytd: num,
    peer_median_starts_2025: num,
    msd_termination_rate_pct: num,
    peer_median_termination_rate_pct: num,
    forecast_method: maybeStr,
    forecast_mape_pct: num.nullable(),
    msd_forecast_2026: num,
    msd_forecast_2026_low: num,
    msd_forecast_2026_high: num,
  }),
  gulf: z.object({
    msd_gcc_pipeline_studies: num,
    msd_gcc_share_pct: num,
    msd_gcc_rank_lowest_share: num,
    msd_removed_gcc_studies: num,
    azn_gcc_pipeline_studies: num,
    max_gcc_group: str,
    max_gcc_studies: num,
    by_group: z.record(str, num),
  }),
});

export type Dataset = {
  meta: z.infer<typeof Meta>;
  overview: z.infer<typeof Overview>;
  concentration: z.infer<typeof Concentration>;
  revenue: z.infer<typeof Revenue>;
  readouts: z.infer<typeof Readouts>;
  starts: z.infer<typeof Starts>;
  gulf: z.infer<typeof Gulf>;
  quality: z.infer<typeof Quality>;
  msdActive: z.infer<typeof MsdActive>;
  headline: z.infer<typeof Headline>;
};
export type ActiveStudyT = z.infer<typeof ActiveStudy>;
