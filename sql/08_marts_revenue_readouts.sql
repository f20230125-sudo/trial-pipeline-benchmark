-- Mart 5: Merck revenue whose protection ends soon, set beside the late-stage pipeline in the same area.
-- Revenue is 2025 US Medicaid pharmacy spend BEFORE rebates, from the sibling project Rx Market Pulse: it is a signal of
-- scale, not company revenue. Protection dates are the FDA Orange Book core date (see rx-analytics); a biologic such as
-- Keytruda has no Orange Book date, so it is shown separately in mart_msd_franchise and never given a made-up one.
-- The window is the three calendar years after the data date: 2026, 2027 and 2028.

create or replace table mart_expiring_revenue as
with risk as (
    select area, sum(spend_2025) as spend_2025_at_risk, min(core_end) as earliest_core_end,
           string_agg(family || ' (' || strftime(core_end, '%b %Y') || ')', ', ' order by core_end) as families
    from rx_family
    where core_end between date '2026-01-01' and date '2028-12-31'
    group by area
), pipe as (
    select s.grp, s.area, count(*) as active_pipeline, count(*) filter (where s.phase_max = 3) as active_late
    from study s where s.is_pipeline and s.is_active group by s.grp, s.area
), mol as (
    select s.grp, s.area, count(distinct m.molecule) as molecules
    from study s join study_molecule m using (nct_id)
    where s.is_pipeline and s.is_active and m.molecule not in (select molecule from ref_background)
    group by s.grp, s.area
), grid as (
    select r.area, d.grp, coalesce(p.active_pipeline, 0) as active_pipeline, coalesce(p.active_late, 0) as active_late,
           coalesce(m.molecules, 0) as molecules
    from risk r cross join dim_group d
    left join pipe p on p.grp = d.grp and p.area = r.area
    left join mol m on m.grp = d.grp and m.area = r.area
)
select r.area, r.families, r.spend_2025_at_risk, r.earliest_core_end,
       msd.active_pipeline as msd_active_pipeline, msd.active_late as msd_active_late, msd.molecules as msd_molecules,
       (select median(active_late) from grid g where g.area = r.area and g.grp <> 'MSD') as peer_median_active_late,
       (select count(*) + 1 from grid g where g.area = r.area and g.grp <> 'MSD' and g.active_late > msd.active_late)
           as msd_rank_active_late
from risk r
join grid msd on msd.area = r.area and msd.grp = 'MSD'
order by r.spend_2025_at_risk desc;

-- Mart 6: readouts due. Active late-stage (Phase 3 or 2/3) pipeline studies whose ESTIMATED primary completion falls in
-- the 24 months from the data month. A primary completion date is when the last participant is examined for the main
-- outcome: it is not the date results are announced, and estimated dates slip. "Overdue" = still active but the
-- estimated month has passed.

create or replace table mart_readouts_quarter as
select d.sort_order, d.grp, year(s.pc_date) || '-Q' || quarter(s.pc_date) as quarter, count(*) as studies
from study s join dim_group d using (grp)
where s.is_pipeline and s.is_active and s.is_late and s.pc_date is not null
  and s.pc_date >= date_trunc('month', date '{as_of}')
  and s.pc_date < date_trunc('month', date '{as_of}') + interval 24 month
group by all
order by d.sort_order, quarter;

create or replace table mart_readouts_summary as
select d.sort_order, d.grp,
       count(s.nct_id) filter (where s.is_pipeline and s.is_active and s.is_late and s.pc_date >= date_trunc('month', date '{as_of}')
           and s.pc_date < date_trunc('month', date '{as_of}') + interval 24 month) as readouts_24m,
       count(s.nct_id) filter (where s.is_pipeline and s.is_active and s.is_late and s.is_overdue) as overdue_late,
       count(s.nct_id) filter (where s.is_pipeline and s.is_active and s.is_late) as active_late
from dim_group d left join study s on s.grp = d.grp
group by all
order by d.sort_order;

create or replace table mart_readouts_msd as
select s.nct_id, s.brief_title as title, s.area, s.phase, s.top_molecule, s.status, s.pc_date, s.pc_type,
       s.enrollment_count, s.has_gcc_site,
       (select string_agg(distinct l.family, ', ') from study_rx_link l where l.nct_id = s.nct_id) as merck_products
from study s
where s.grp = 'MSD' and s.is_pipeline and s.is_active and s.is_late and s.pc_date is not null
  and s.pc_date >= date_trunc('month', date '{as_of}')
  and s.pc_date < date_trunc('month', date '{as_of}') + interval 24 month
order by s.pc_date, s.nct_id;

copy mart_expiring_revenue to '{marts_dir}/mart_expiring_revenue.csv' (header, delimiter ',');
copy mart_readouts_quarter to '{marts_dir}/mart_readouts_quarter.csv' (header, delimiter ',');
copy mart_readouts_summary to '{marts_dir}/mart_readouts_summary.csv' (header, delimiter ',');
copy mart_readouts_msd to '{marts_dir}/mart_readouts_msd.csv' (header, delimiter ',');
