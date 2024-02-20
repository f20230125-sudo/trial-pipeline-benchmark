-- Stage 1: the raw API pages as published, one row per study.
-- A study fetched by several search terms (Merck and MSD both find the same record) is kept once in raw_study;
-- which terms found it is kept in study_query.
-- maximum_object_size reserves a buffer of that size per thread: the largest page is 7.4 MB, so 32 MB is plenty,
-- and the 200 MB first tried ran the machine out of memory.

create or replace table raw_page as
-- DuckDB reports globbed files with the operating system's separator (backslashes on Windows), so accept both.
select regexp_extract(filename, 'ctgov[/\\]([^/\\]+)[/\\]page_', 1) as term_slug,
       j->>'$.protocolSection.identificationModule.nctId' as nct_id,
       j
from (select filename, unnest(studies) as j
      from read_json('{raw_glob}', columns={studies: 'JSON[]'}, maximum_object_size=33554432, filename=true));

create or replace table study_query as
select distinct nct_id, term_slug from raw_page;

create or replace table raw_study as
select nct_id, j
from raw_page
qualify row_number() over (partition by nct_id order by term_slug) = 1;

drop table raw_page;

-- One typed row per study. Dates stay as the registry's text here; tp.dates turns them into dates.
-- (Parentheses around a -> path matter: without them "is not null" binds to the path, not the value.)
create or replace table stg_study as
select
    nct_id,
    j->>'$.protocolSection.identificationModule.briefTitle'                         as brief_title,
    j->>'$.protocolSection.identificationModule.acronym'                            as acronym,
    j->>'$.protocolSection.identificationModule.orgStudyIdInfo.id'                  as org_study_id,
    j->>'$.protocolSection.statusModule.overallStatus'                              as overall_status,
    j->>'$.protocolSection.statusModule.whyStopped'                                 as why_stopped,
    j->>'$.protocolSection.statusModule.statusVerifiedDate'                         as status_verified_raw,
    j->>'$.protocolSection.statusModule.startDateStruct.date'                       as start_raw,
    j->>'$.protocolSection.statusModule.startDateStruct.type'                       as start_type_raw,
    j->>'$.protocolSection.statusModule.primaryCompletionDateStruct.date'           as pc_raw,
    j->>'$.protocolSection.statusModule.primaryCompletionDateStruct.type'           as pc_type_raw,
    j->>'$.protocolSection.statusModule.completionDateStruct.date'                  as completion_raw,
    j->>'$.protocolSection.statusModule.completionDateStruct.type'                  as completion_type_raw,
    j->>'$.protocolSection.statusModule.studyFirstPostDateStruct.date'              as first_post_raw,
    j->>'$.protocolSection.statusModule.lastUpdatePostDateStruct.date'              as last_update_raw,
    j->>'$.protocolSection.sponsorCollaboratorsModule.leadSponsor.name'             as lead_name,
    j->>'$.protocolSection.sponsorCollaboratorsModule.leadSponsor.class'            as lead_class,
    j->>'$.protocolSection.designModule.studyType'                                  as study_type,
    array_to_string(from_json(j->'$.protocolSection.designModule.phases', '["VARCHAR"]'), ',') as phases_raw,
    try_cast(j->>'$.protocolSection.designModule.enrollmentInfo.count' as integer)  as enrollment_count,
    j->>'$.protocolSection.designModule.enrollmentInfo.type'                        as enrollment_type,
    j->>'$.protocolSection.designModule.designInfo.primaryPurpose'                  as primary_purpose,
    j->>'$.protocolSection.designModule.designInfo.allocation'                      as allocation,
    try_cast(j->>'$.hasResults' as boolean)                                         as has_results,
    j->>'$.derivedSection.miscInfoModule.versionHolder'                             as version_holder
from raw_study;
