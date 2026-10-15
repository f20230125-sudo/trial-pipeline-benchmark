-- Mart 7: how many pipeline studies each company starts per year, and how many it stops.
-- A start counts when the registry gives a start date that is not an ESTIMATE and is not after the data date; old
-- records have a month and no type, and they are historical starts. Withdrawn studies never started and are not counted.
-- 2026 is a partial year (to the data date) and is labelled so in the dashboard; the forecast leaves it out.

create or replace table mart_starts_year as
with y as (select range as year from range(2014, 2027))
select d.sort_order, d.grp, y.year, count(s.nct_id) as studies, (y.year = 2026) as partial_year
from dim_group d
cross join y
left join study s on s.grp = d.grp and s.is_pipeline and s.start_date is not null and s.start_type <> 'ESTIMATED'
                  and s.start_date <= date '{as_of}' and year(s.start_date) = y.year
group by all
order by d.sort_order, y.year;

create or replace table mart_starts_peer_median as
select year, median(studies) as median_studies, partial_year
from mart_starts_year
where grp <> 'MSD'
group by year, partial_year
order by year;

-- Termination rate: of the pipeline studies that ended (completed or terminated) with a completion date in 2016 to 2025,
-- the share that were terminated. Withdrawn and suspended studies are left out: they never ran or have not ended.
create or replace table mart_termination as
select d.sort_order, d.grp,
       count(s.nct_id) filter (where s.status = 'COMPLETED')  as completed,
       count(s.nct_id) filter (where s.status = 'TERMINATED') as terminated,
       round(100.0 * count(s.nct_id) filter (where s.status = 'TERMINATED')
             / nullif(count(s.nct_id) filter (where s.status in ('COMPLETED', 'TERMINATED')), 0), 1) as termination_rate_pct
from dim_group d
left join study s on s.grp = d.grp and s.is_pipeline and s.status in ('COMPLETED', 'TERMINATED')
                  and year(coalesce(s.completion_date, s.pc_date)) between 2016 and 2025
group by all
order by d.sort_order;

create or replace table mart_stop_themes as
select d.sort_order, d.grp, s.stop_theme as theme, count(*) as studies
from study s join dim_group d using (grp)
where s.is_pipeline and s.status in ('TERMINATED', 'WITHDRAWN') and s.stop_theme is not null
group by all
order by d.sort_order, studies desc;

copy mart_starts_year to '{marts_dir}/mart_starts_year.csv' (header, delimiter ',');
copy mart_starts_peer_median to '{marts_dir}/mart_starts_peer_median.csv' (header, delimiter ',');
copy mart_termination to '{marts_dir}/mart_termination.csv' (header, delimiter ',');
copy mart_stop_themes to '{marts_dir}/mart_stop_themes.csv' (header, delimiter ',');
