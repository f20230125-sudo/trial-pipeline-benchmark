-- Stage 2: the repeating parts of a study, one row per item, in the order the registry lists them.

create or replace table stg_condition as
select s.nct_id, t.i as ord, trim(t.x) as condition
from (select nct_id, from_json(j->'$.protocolSection.conditionsModule.conditions', '["VARCHAR"]') as arr
      from raw_study) s,
     unnest(s.arr) with ordinality as t(x, i)
where t.x is not null and trim(t.x) <> '';

-- MeSH terms the registry attached to the conditions: "mesh" are the matched terms, "ancestor" the tree above them.
-- Caution: the matching is automatic and sometimes wrong (a lung-cancer study that mentions PD-L1 is also tagged with a
-- Parkinson disease term), so area rules must not trust a single term; see sql/04 and tp.areas.
create or replace table stg_condition_mesh as
select nct_id, m.id as mesh_id, m.term, 'mesh' as kind
from (select nct_id, unnest(from_json(j->'$.derivedSection.conditionBrowseModule.meshes',
                                      '[{"id":"VARCHAR","term":"VARCHAR"}]')) as m from raw_study)
union all
select nct_id, m.id, m.term, 'ancestor'
from (select nct_id, unnest(from_json(j->'$.derivedSection.conditionBrowseModule.ancestors',
                                      '[{"id":"VARCHAR","term":"VARCHAR"}]')) as m from raw_study);

create or replace table stg_intervention as
select s.nct_id, t.i as ord,
       t.x->>'$.type' as type,
       trim(t.x->>'$.name') as name,
       coalesce(from_json(t.x->'$.otherNames', '["VARCHAR"]'), []::varchar[]) as other_names
from (select nct_id, from_json(j->'$.protocolSection.armsInterventionsModule.interventions', '["JSON"]') as arr
      from raw_study) s,
     unnest(s.arr) with ordinality as t(x, i);

create or replace table stg_intervention_mesh as
select nct_id, m.id as mesh_id, m.term, 'mesh' as kind
from (select nct_id, unnest(from_json(j->'$.derivedSection.interventionBrowseModule.meshes',
                                      '[{"id":"VARCHAR","term":"VARCHAR"}]')) as m from raw_study)
union all
select nct_id, m.id, m.term, 'ancestor'
from (select nct_id, unnest(from_json(j->'$.derivedSection.interventionBrowseModule.ancestors',
                                      '[{"id":"VARCHAR","term":"VARCHAR"}]')) as m from raw_study);

create or replace table stg_location as
select s.nct_id, t.i as ord,
       t.x->>'$.facility' as facility,
       t.x->>'$.city' as city,
       t.x->>'$.country' as country_raw,
       t.x->>'$.status' as status
from (select nct_id, from_json(j->'$.protocolSection.contactsLocationsModule.locations', '["JSON"]') as arr
      from raw_study) s,
     unnest(s.arr) with ordinality as t(x, i);

-- Countries a study once listed and later dropped (for example Saudi Arabia). Real signal for the Gulf view.
create or replace table stg_removed_country as
select nct_id, unnest(from_json(j->'$.derivedSection.miscInfoModule.removedCountries', '["VARCHAR"]')) as country_raw
from raw_study;

create or replace table stg_collaborator as
select nct_id, c.name as name, c."class" as class
from (select nct_id, unnest(from_json(j->'$.protocolSection.sponsorCollaboratorsModule.collaborators',
                                      '[{"name":"VARCHAR","class":"VARCHAR"}]')) as c from raw_study);
