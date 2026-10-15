-- Dimensions: the small, clean lookup tables the facts and marts join to.

create or replace table dim_group as
select * from (values
    ('MSD',          'MSD',          true,   1),
    ('AbbVie',       'AbbVie',       false,  2),
    ('AstraZeneca',  'AstraZeneca',  false,  3),
    ('BMS',          'BMS',          false,  4),
    ('GSK',          'GSK',          false,  5),
    ('J&J',          'J&J',          false,  6),
    ('Lilly',        'Lilly',        false,  7),
    ('Novartis',     'Novartis',     false,  8),
    ('Novo Nordisk', 'Novo Nordisk', false,  9),
    ('Pfizer',       'Pfizer',       false, 10),
    ('Roche',        'Roche',        false, 11),
    ('Sanofi',       'Sanofi',       false, 12)
) as t(grp, short_name, is_focus, sort_order);

create or replace table dim_phase as
select distinct label, phase_max, rank, pipeline from map_phase
union
select * from (values ('Not stated', null::integer, 90, false), ('Not applicable', null::integer, 91, false))
       as t(label, phase_max, rank, pipeline);

create or replace table dim_country as
select * from read_csv('{ref_dir}/countries.csv', header=true,
                       columns={'raw': 'VARCHAR', 'iso3': 'VARCHAR', 'name': 'VARCHAR',
                                'is_gcc': 'BOOLEAN', 'is_mena': 'BOOLEAN'});

-- Every lead-sponsor name seen, the group the rules gave it, and how many studies carry it.
create or replace table dim_sponsor_name as
select m.lead_name, m.grp, m.kind, m.rule_order, m.note, count(s.nct_id) as n_studies
from map_sponsor m
left join stg_study s on s.lead_name is not distinct from m.lead_name
group by all;
