-- Studies set aside from the analysis, each with the reason. Nothing is silently dropped:
-- every fetched study is either in `study` or here, and the data-quality scorecard checks that the two add up.
-- The twelve groups are decided by tp.sponsors; the search is deliberately wide (full-text), so most of what lands
-- here is a university, a hospital, a person or another company that shared a search word.

create or replace table quarantine as
with candidates as (
    select s.nct_id, 1 as prio, 'malformed NCT ID' as reason, s.lead_name as detail
    from stg_study s
    where not regexp_matches(coalesce(s.nct_id, ''), '^NCT[0-9]{8}$')
    union all
    select s.nct_id, 2, 'lead sponsor not in the twelve groups: ' || m.grp, s.lead_name
    from stg_study s
    join map_sponsor m on s.lead_name is not distinct from m.lead_name
    where m.kind = 'excluded'
)
select nct_id, reason, detail
from candidates
qualify row_number() over (partition by nct_id order by prio) = 1;
