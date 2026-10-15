-- Mart 8: the Gulf footprint. A study "has a Gulf site" when the registry lists at least one site in the UAE, Saudi Arabia,
-- Qatar, Kuwait, Bahrain or Oman. Sites are as registered (a registered site may never have enrolled). Counts are for
-- pipeline studies led by the company itself, any status unless the column says active.

create or replace table mart_gulf_summary as
select d.sort_order, d.grp,
       count(s.nct_id) filter (where s.is_pipeline)                                        as pipeline_studies,
       count(s.nct_id) filter (where s.is_pipeline and s.has_gcc_site)                     as gcc_studies,
       count(s.nct_id) filter (where s.is_pipeline and s.is_active and s.has_gcc_site)     as gcc_active_studies,
       round(100.0 * count(s.nct_id) filter (where s.is_pipeline and s.has_gcc_site)
             / nullif(count(s.nct_id) filter (where s.is_pipeline), 0), 2)                 as gcc_share_pct,
       count(s.nct_id) filter (where s.is_pipeline and s.removed_gcc)                      as removed_gcc_studies,
       count(s.nct_id) filter (where s.is_pipeline and s.has_mena_site)                    as mena_studies
from dim_group d left join study s on s.grp = d.grp
group by all
order by d.sort_order;

create or replace table mart_gulf_country as
select d.sort_order, d.grp, c.iso3, c.country,
       count(distinct s.nct_id) as studies,
       count(distinct s.nct_id) filter (where s.is_active) as active_studies,
       sum(c.n_sites) as sites
from study_country c
join study s using (nct_id)
join dim_group d on d.grp = s.grp
where s.is_pipeline and c.is_gcc
group by all
order by d.sort_order, studies desc;

-- Studies that listed a Gulf country and later removed it (registry removedCountries), pipeline only.
create or replace table mart_gulf_removed as
select d.sort_order, d.grp, r.iso3, r.country, count(distinct s.nct_id) as studies
from study_removed_country r
join study s using (nct_id)
join dim_group d on d.grp = s.grp
where s.is_pipeline and r.is_gcc
group by all
order by d.sort_order, studies desc;

-- Roll-up impact: how many studies each company gains from the names of the companies it bought.
create or replace table mart_harmonisation_gain as
select d.sort_order, d.grp,
       count(*) filter (where s.sponsor_kind = 'parent') as parent_studies,
       count(*) filter (where s.sponsor_kind = 'acquired') as acquired_studies,
       round(100.0 * count(*) filter (where s.sponsor_kind = 'acquired') / count(*), 1) as gain_pct
from dim_group d join study s on s.grp = d.grp
group by all
order by d.sort_order;

-- Lists for the workbook and the dashboard.
create or replace table mart_msd_active as
select s.nct_id, s.brief_title as title, s.area, s.phase, s.phase_max, s.status, s.start_date, s.pc_date, s.pc_type,
       s.top_molecule, s.enrollment_count, s.has_gcc_site, s.is_late, s.is_overdue,
       (select string_agg(distinct l.family, ', ') from study_rx_link l where l.nct_id = s.nct_id) as merck_products
from study s
where s.grp = 'MSD' and s.is_pipeline and s.is_active
order by s.phase_max desc, s.pc_date, s.nct_id;

-- One row per pipeline study since 2010 (and every active one): the data sheet of the Excel model.
create or replace table mart_study_export as
select s.nct_id, s.grp, s.area, s.phase, s.phase_max,
       case s.phase_max when 3 then 'Late' when 2 then 'Mid' else 'Early' end as stage,
       s.is_active, s.status_class, s.status,
       year(s.start_date) as start_year, s.start_type, s.pc_date, s.pc_type, s.has_gcc_site, s.top_molecule
from study s
where s.is_pipeline and (s.is_active or year(s.start_date) >= 2010)
order by s.grp, s.nct_id;

copy mart_gulf_summary to '{marts_dir}/mart_gulf_summary.csv' (header, delimiter ',');
copy mart_gulf_country to '{marts_dir}/mart_gulf_country.csv' (header, delimiter ',');
copy mart_gulf_removed to '{marts_dir}/mart_gulf_removed.csv' (header, delimiter ',');
copy mart_harmonisation_gain to '{marts_dir}/mart_harmonisation_gain.csv' (header, delimiter ',');
copy mart_msd_active to '{marts_dir}/mart_msd_active.csv' (header, delimiter ',');
copy mart_study_export to '{marts_dir}/mart_study_export.csv' (header, delimiter ',');
