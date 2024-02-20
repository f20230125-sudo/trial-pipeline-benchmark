-- Facts: one clean row per in-scope study, and its countries. {as_of} is the API's data date, not the build date.

create or replace table study_country as
select l.nct_id, c.iso3, any_value(c.name) as country, bool_or(c.is_gcc) as is_gcc, bool_or(c.is_mena) as is_mena,
       count(*) as n_sites
from stg_location l
join dim_country c on c.raw = l.country_raw
group by l.nct_id, c.iso3;

-- Countries a study listed once and dropped (Saudi Arabia, UAE ...): real signal for the Gulf view.
create or replace table study_removed_country as
select distinct r.nct_id, c.iso3, c.name as country, c.is_gcc
from stg_removed_country r
join dim_country c on c.raw = r.country_raw;

create or replace table study_base as
with iv as (
    select nct_id,
           count(*) as n_interventions,
           coalesce(bool_or(type in ('DRUG', 'BIOLOGICAL', 'GENETIC', 'COMBINATION_PRODUCT')), false) as has_drug
    from stg_intervention group by nct_id
), sites as (
    select nct_id, sum(n_sites) as n_sites, count(*) as n_countries,
           coalesce(bool_or(is_gcc), false) as has_gcc_site, coalesce(bool_or(is_mena), false) as has_mena_site
    from study_country group by nct_id
), removed as (
    select nct_id, bool_or(is_gcc) as removed_gcc from study_removed_country group by nct_id
)
select
    s.nct_id,
    m.grp,
    m.kind                                  as sponsor_kind,
    s.lead_name,
    s.lead_class,
    s.brief_title,
    s.acronym,
    s.org_study_id,
    s.overall_status                        as status,
    case when s.overall_status in ('RECRUITING', 'ACTIVE_NOT_RECRUITING', 'NOT_YET_RECRUITING',
                                   'ENROLLING_BY_INVITATION') then 'active'
         when s.overall_status = 'SUSPENDED'  then 'paused'
         when s.overall_status = 'UNKNOWN'    then 'lapsed'
         when s.overall_status = 'COMPLETED'  then 'completed'
         when s.overall_status in ('TERMINATED', 'WITHDRAWN') then 'stopped'
         else 'other' end                   as status_class,
    s.study_type,
    coalesce(p.label, 'Not stated')         as phase,
    p.phase_max,
    coalesce(p.rank, 90)                    as phase_rank,
    coalesce(p.pipeline, false)             as phase_is_pipeline,
    d1.d                                    as start_date,
    coalesce(d1.precision, 'missing')       as start_precision,
    case when s.start_type_raw in ('ACTUAL', 'ESTIMATED') then s.start_type_raw else 'NOT STATED' end as start_type,
    d2.d                                    as pc_date,
    coalesce(d2.precision, 'missing')       as pc_precision,
    case when s.pc_type_raw in ('ACTUAL', 'ESTIMATED') then s.pc_type_raw else 'NOT STATED' end as pc_type,
    d3.d                                    as completion_date,
    coalesce(d3.precision, 'missing')       as completion_precision,
    case when s.completion_type_raw in ('ACTUAL', 'ESTIMATED') then s.completion_type_raw else 'NOT STATED' end
                                            as completion_type,
    d4.d                                    as verified_date,
    s.enrollment_count,
    s.enrollment_type,
    s.primary_purpose,
    s.has_results,
    s.why_stopped,
    case when s.overall_status in ('TERMINATED', 'WITHDRAWN', 'SUSPENDED') then coalesce(w.theme, 'Not stated') end
                                            as stop_theme,
    coalesce(iv.n_interventions, 0)         as n_interventions,
    coalesce(iv.has_drug, false)            as has_drug_intervention,
    coalesce(sites.n_sites, 0)              as n_sites,
    coalesce(sites.n_countries, 0)          as n_countries,
    coalesce(sites.has_gcc_site, false)     as has_gcc_site,
    coalesce(sites.has_mena_site, false)    as has_mena_site,
    coalesce(removed.removed_gcc, false)    as removed_gcc,
    -- pipeline = drug-development studies: interventional, phase 1 to 3, with a drug, biological, genetic or combination
    (s.study_type = 'INTERVENTIONAL' and coalesce(p.pipeline, false) and coalesce(iv.has_drug, false)) as is_pipeline,
    (s.overall_status in ('RECRUITING', 'ACTIVE_NOT_RECRUITING', 'NOT_YET_RECRUITING', 'ENROLLING_BY_INVITATION'))
                                            as is_active,
    coalesce(p.phase_max = 3, false)        as is_late,
    -- an active study whose ESTIMATED primary completion month has already passed: the forecast was not updated
    (s.overall_status in ('RECRUITING', 'ACTIVE_NOT_RECRUITING', 'NOT_YET_RECRUITING', 'ENROLLING_BY_INVITATION')
        and s.pc_type_raw = 'ESTIMATED' and d2.d < date_trunc('month', date '{as_of}')) as is_overdue,
    -- both dates ACTUAL but start after primary completion: kept, flagged, left out of timing measures
    (s.start_type_raw = 'ACTUAL' and s.pc_type_raw = 'ACTUAL' and d1.d > d2.d) as dates_inconsistent
from stg_study s
join map_sponsor m on s.lead_name is not distinct from m.lead_name and m.kind in ('parent', 'acquired')
left join map_phase p on p.phases_raw = s.phases_raw
left join map_date d1 on d1.raw = s.start_raw
left join map_date d2 on d2.raw = s.pc_raw
left join map_date d3 on d3.raw = s.completion_raw
left join map_date d4 on d4.raw = s.status_verified_raw
left join map_stop w on w.why_stopped = s.why_stopped
left join iv on iv.nct_id = s.nct_id
left join sites on sites.nct_id = s.nct_id
left join removed on removed.nct_id = s.nct_id
where regexp_matches(coalesce(s.nct_id, ''), '^NCT[0-9]{8}$');
