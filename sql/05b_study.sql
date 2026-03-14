-- The study table the marts read: study_base plus therapeutic area, molecules and the link to Merck's products.
-- The area cascade is documented in src/tp/areas.py: override, then MeSH, then condition text, then molecule, then none.

-- Molecules: the registry's own MeSH intervention terms plus the normalised drug names. A name beats a MeSH term when
-- both give the same key. Placebo, saline, standard of care and similar comparators are dropped (key is null).
create or replace table study_molecule as
with names as (
    select i.nct_id, m.key as molecule, min(i.ord) as ord, 'name' as source
    from stg_intervention i
    join map_molecule m on m.raw = i.name
    where i.type in ('DRUG', 'BIOLOGICAL', 'GENETIC', 'COMBINATION_PRODUCT') and m.key is not null
      and i.nct_id in (select nct_id from study_base)
    group by i.nct_id, m.key
), meshes as (
    select s.nct_id, m.key as molecule, 1000 as ord, 'mesh' as source
    from stg_intervention_mesh s
    join map_molecule m on m.raw = s.term
    where s.kind = 'mesh' and m.key is not null and s.nct_id in (select nct_id from study_base)
)
select nct_id, molecule, min(ord) as ord, arg_min(source, ord) as source
from (select * from names union all select * from meshes)
group by nct_id, molecule;

-- Why the text comes before MeSH: the registry's MeSH ancestors are generic and often point the wrong way (multiple
-- sclerosis inherits "Autoimmune Diseases", atopic dermatitis "Skin Diseases, Genetic", Alzheimer's "Amyloid"), while the
-- condition name a person typed is specific. MeSH is used when the text matches no rule: first the directly matched
-- terms, then their ancestors.
create or replace table study_area_steps as
with mesh_direct as (
    select m.nct_id, arg_min(t.area, t.priority) as area
    from stg_condition_mesh m join map_area_term t on t.term = m.term
    where m.kind = 'mesh' and m.nct_id in (select nct_id from study_base)
    group by m.nct_id
), mesh_all as (
    select m.nct_id, arg_min(t.area, t.priority) as area
    from stg_condition_mesh m join map_area_term t on t.term = m.term
    where m.nct_id in (select nct_id from study_base)
    group by m.nct_id
), txt as (
    select c.nct_id, arg_min(t.area, t.priority) as area
    from stg_condition c join map_area_term t on t.term = c.condition
    where c.nct_id in (select nct_id from study_base)
    group by c.nct_id
)
select b.nct_id, o.area as override_area, txt.area as text_area,
       coalesce(md.area, ma.area) as mesh_area, md.area as mesh_direct_area
from study_base b
left join map_area_override o on o.nct_id = b.nct_id
left join txt on txt.nct_id = b.nct_id
left join mesh_direct md on md.nct_id = b.nct_id
left join mesh_all ma on ma.nct_id = b.nct_id;

-- Molecule fallback: a molecule's usual area, taken only where it is well supported (3 or more studies, 60% or more
-- agreeing) among studies whose area came from the MeSH terms or the condition text.
create or replace table molecule_area as
with known as (
    select sm.molecule, coalesce(a.text_area, a.mesh_area) as area, count(*) as n
    from study_molecule sm
    join study_area_steps a using (nct_id)
    where a.override_area is null and coalesce(a.text_area, a.mesh_area) is not null
    group by sm.molecule, coalesce(a.text_area, a.mesh_area)
), ranked as (
    select molecule, arg_max(area, n) as area, max(n) as top_n, sum(n) as total from known group by molecule
)
select molecule, area, top_n, total from ranked where top_n >= 3 and top_n * 1.0 / total >= 0.6;

create or replace table study_molecule_area as
select sm.nct_id, arg_max(ma.area, ma.top_n) as area
from study_molecule sm join molecule_area ma using (molecule)
group by sm.nct_id;

create or replace table study as
select b.*,
       coalesce(a.override_area, a.text_area, a.mesh_area, sma.area, 'Unclassified') as area,
       case when a.override_area is not null then 'override'
            when a.text_area is not null then 'text'
            when a.mesh_area is not null then 'mesh'
            when sma.area is not null then 'molecule'
            else 'none' end as area_source,
       -- text and the directly matched MeSH terms both gave an area and they differ: counted by the scorecard
       (a.text_area is not null and a.mesh_direct_area is not null and a.text_area <> a.mesh_direct_area) as area_conflict,
       tm.top_molecule
from study_base b
left join study_area_steps a using (nct_id)
left join study_molecule_area sma using (nct_id)
left join (select nct_id, arg_min(molecule, ord) as top_molecule from study_molecule group by nct_id) tm using (nct_id);

-- Merck's products, matched to MSD-led studies by molecule name, development code or brand name.
create or replace table rx_family as
select * from read_csv('{ref_dir}/rx_merck_families.csv', header=true,
                       columns={'family': 'VARCHAR', 'franchise': 'VARCHAR', 'area': 'VARCHAR', 'spend_2025': 'BIGINT',
                                'status': 'VARCHAR', 'core_end': 'DATE', 'substance_end': 'DATE', 'last_end': 'DATE',
                                'molecule_regex': 'VARCHAR'}, nullstr='');

create or replace table study_rx_link as
with names as (
    select nct_id, string_agg(coalesce(name, '') || ' ' || array_to_string(other_names, ' '), ' ') as txt
    from stg_intervention group by nct_id
), blob as (
    select s.nct_id, lower(coalesce(s.brief_title, '') || ' ' || coalesce(n.txt, '')) as txt
    from study_base s left join names n using (nct_id)
    where s.grp = 'MSD'
)
select b.nct_id, f.family, f.franchise
from blob b join rx_family f on regexp_matches(b.txt, f.molecule_regex);
