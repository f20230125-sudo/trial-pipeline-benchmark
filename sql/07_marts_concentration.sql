-- Mart 4: how much of each company's late-stage pipeline rests on one molecule.
-- Chemotherapy backbones, steroids and generic comparators (data/ref/background_therapies.csv) are set aside first,
-- otherwise "carboplatin" would be the top molecule of several oncology pipelines. Brand names and development codes are
-- folded into one name by data/ref/molecule_aliases.csv. The base is active Phase 2 and 3 pipeline studies (phase_max >= 2).

create or replace table ref_background as
select * from read_csv('{ref_dir}/background_therapies.csv', header=true,
                       columns={'molecule': 'VARCHAR', 'reason': 'VARCHAR'});

create or replace table mart_top_molecules as
with base as (
    select s.grp, s.nct_id from study s where s.is_pipeline and s.is_active and s.phase_max >= 2
), tot as (
    select grp, count(*) as studies_p23 from base group by grp
), cnt as (
    select b.grp, m.molecule, count(distinct b.nct_id) as studies
    from base b join study_molecule m using (nct_id)
    where m.molecule not in (select molecule from ref_background)
    group by b.grp, m.molecule
), ranked as (
    select grp, molecule, studies, row_number() over (partition by grp order by studies desc, molecule) as rk from cnt
)
select d.sort_order, r.grp, r.rk as rank, r.molecule, r.studies, t.studies_p23,
       round(100.0 * r.studies / t.studies_p23, 1) as share_pct
from ranked r
join tot t using (grp)
join dim_group d on d.grp = r.grp
where r.rk <= 5
order by d.sort_order, r.rk;

create or replace table mart_concentration as
select t.sort_order, t.grp, t.molecule as top_molecule, t.studies as top_studies, t.studies_p23, t.share_pct,
       rank() over (order by t.share_pct desc) as concentration_rank
from mart_top_molecules t
where t.rank = 1
order by t.sort_order;

-- Pembrolizumab across the whole registry: who runs the active studies? Uses the extra "ecosystem" download of every
-- study that tests pembrolizumab, whatever the sponsor.
create or replace table mart_pembrolizumab_ecosystem as
with eco as (
    select s.nct_id, s.lead_class, m.grp, m.kind
    from stg_study s
    join study_query q on q.nct_id = s.nct_id and q.term_slug = 'ecosystem__pembrolizumab'
    left join map_sponsor m on s.lead_name is not distinct from m.lead_name
    where s.overall_status in ('RECRUITING', 'ACTIVE_NOT_RECRUITING', 'NOT_YET_RECRUITING', 'ENROLLING_BY_INVITATION')
)
select category, count(*) as studies, round(100.0 * count(*) / sum(count(*)) over (), 1) as share_pct
from (
    select case when kind in ('parent', 'acquired') and grp = 'MSD' then 'MSD'
                when kind in ('parent', 'acquired') then 'Other of the 11 peers'
                when lead_class = 'INDUSTRY' then 'Other industry'
                else 'Academic, hospital and other' end as category
    from eco
)
group by category
order by studies desc;

create or replace table mart_msd_franchise as
select f.family, f.franchise, f.area, f.spend_2025, f.status, f.core_end, f.last_end,
       count(distinct l.nct_id) as studies_all,
       count(distinct l.nct_id) filter (where s.is_pipeline and s.is_active) as active_pipeline,
       count(distinct l.nct_id) filter (where s.is_pipeline and s.is_active and s.phase_max = 3) as active_late
from rx_family f
left join study_rx_link l on l.family = f.family
left join study s on s.nct_id = l.nct_id
group by all
order by f.spend_2025 desc;

copy mart_top_molecules to '{marts_dir}/mart_top_molecules.csv' (header, delimiter ',');
copy mart_concentration to '{marts_dir}/mart_concentration.csv' (header, delimiter ',');
copy mart_pembrolizumab_ecosystem to '{marts_dir}/mart_pembrolizumab_ecosystem.csv' (header, delimiter ',');
copy mart_msd_franchise to '{marts_dir}/mart_msd_franchise.csv' (header, delimiter ',');
