-- The study table the marts read. Area and molecule are added here (step M4); until then every study is Unclassified.
create or replace table study as
select b.*,
       'Unclassified'::varchar as area,
       'none'::varchar         as area_source,
       null::varchar           as top_molecule
from study_base b;
