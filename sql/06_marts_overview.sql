-- Marts 1-3: where each company's pipeline stands. "Pipeline" and "active" are defined in sql/05_facts.sql
-- (study.is_pipeline, study.is_active). Counts are studies, not programmes or value.

create or replace table mart_group_summary as
with g as (
    select grp,
           count(*)                                                                as studies_in_scope,
           count(*) filter (where sponsor_kind = 'parent')                         as parent_studies,
           count(*) filter (where sponsor_kind = 'acquired')                       as acquired_studies,
           count(*) filter (where is_pipeline)                                     as pipeline_studies,
           count(*) filter (where is_pipeline and is_active)                       as active_pipeline,
           count(*) filter (where is_pipeline and is_active and phase_max = 1)     as active_p1,
           count(*) filter (where is_pipeline and is_active and phase_max = 2)     as active_p2,
           count(*) filter (where is_pipeline and is_active and phase_max = 3)     as active_late,
           count(*) filter (where is_pipeline and has_gcc_site)                    as pipeline_gcc_studies,
           count(*) filter (where is_pipeline and is_active and has_gcc_site)      as active_gcc_studies,
           count(*) filter (where is_pipeline and is_overdue)                      as overdue_active
    from study group by grp
)
select d.sort_order, g.*,
       rank() over (order by g.active_pipeline desc) as active_pipeline_rank,
       rank() over (order by g.active_late desc)     as active_late_rank
from g join dim_group d using (grp)
order by d.sort_order;

create or replace table mart_pipeline_phase as
select d.sort_order, d.grp, p.label as phase, p.rank as phase_rank, count(s.nct_id) as studies
from dim_group d
cross join (select label, rank from dim_phase where pipeline) p
left join study s on s.grp = d.grp and s.phase = p.label and s.is_pipeline and s.is_active
group by all
order by d.sort_order, p.rank;

create or replace table mart_area_mix as
with c as (
    select grp, area, count(*) as studies from study where is_pipeline and is_active group by grp, area
), t as (
    select grp, sum(studies) as total from c group by grp
)
select d.sort_order, d.grp, a.area, a.sort_order as area_order, coalesce(c.studies, 0) as studies,
       round(100.0 * coalesce(c.studies, 0) / t.total, 2) as share_pct
from dim_group d
cross join dim_area a
join t on t.grp = d.grp
left join c on c.grp = d.grp and c.area = a.area
order by d.sort_order, a.sort_order;

copy mart_group_summary to '{marts_dir}/mart_group_summary.csv' (header, delimiter ',');
copy mart_pipeline_phase to '{marts_dir}/mart_pipeline_phase.csv' (header, delimiter ',');
copy mart_area_mix to '{marts_dir}/mart_area_mix.csv' (header, delimiter ',');
