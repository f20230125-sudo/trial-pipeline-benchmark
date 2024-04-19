import re

import pytest

from tp import areas, molecules, rx_link


@pytest.mark.parametrize(
    "raw,key",
    [
        ("Pembrolizumab", "pembrolizumab"),
        ("Pembrolizumab 200 mg IV", "pembrolizumab"),
        ("pembrolizumab 400 mg every 6 weeks", "pembrolizumab"),
        ("MK-3475", "mk-3475"),
        ("MK 3475", "mk-3475"),
        ("MK-3475A", "mk-3475"),
        ("mk3475", "mk-3475"),
        ("KEYTRUDA®", "keytruda"),
        ("Sitagliptin 100 mg tablet", "sitagliptin"),
        ("Metformin (extended release) 1000mg", "metformin"),
        ("Insulin glargine U-100 SC injection", "insulin glargine u-100"),
        ("Carboplatin and Paclitaxel", "carboplatin paclitaxel"),
        ("Placebo", None),
        ("Matching placebo to MK-1439", None),
        ("Saline solution", None),
        ("Standard of care", None),
        ("Best Supportive Care", None),
        ("Investigator's choice chemotherapy", None),
        ("Rescue medication", None),
        ("Physician’s choice", None),
        ("Investigator’s Choice", None),
        ("Physicians' Choice", None),
        ("Physician's-Choice", None),
        ("Investigator's Treatment of Choice", None),
        ("Ivonescimab + investigator-choice platinum doublet", "ivonescimab + investigator-choice platinum doublet"),
        ("Rescue Therapy (Paracetamol)", None),
        ("", None),
        (None, None),
        ("   ", None),
        ("10 mg", None),
    ],
)
def test_normalise(raw, key):
    assert molecules.normalise(raw) == key


def test_is_comparator():
    assert molecules.is_comparator("Placebos")  # the registry's MeSH term for placebo
    assert not molecules.is_comparator("Pembrolizumab")


@pytest.mark.parametrize(
    "text,area",
    [
        ("HIV Infections", "HIV"),
        ("Carcinoma, Non-Small-Cell Lung", "Oncology"),
        ("Neoplasms by Site", "Oncology"),
        ("Diabetes Mellitus, Type 2", "Diabetes & obesity"),
        ("Hypertension, Pulmonary", "Cardiovascular"),  # PAH is Cardiovascular in Rx Market Pulse too (Winrevair)
        ("Arthritis, Rheumatoid", "Immunology & inflammation"),
        ("Asthma", "Respiratory & allergy"),
        ("Migraine Disorders", "Neurology & psychiatry"),
        ("Parkinson Disease", "Neurology & psychiatry"),
        ("Pain, Postoperative", "Pain, addiction & anesthesia"),
        ("Hepatitis B", "Infectious disease (non-HIV)"),
        ("Crohn Disease", "Immunology & inflammation"),
        ("Osteoporosis", "Endocrine & women's health"),
        ("Chronic Kidney Disease", "Urology & renal"),
        ("Macular Degeneration", "Eye & skin"),
        ("Hemophilia A", "Hematology"),
        # British spellings (the registry has both); "aemia" inside "dyslipidaemia" must not read as anaemia
        ("Dyslipidaemia", "Cardiovascular"),
        ("Hypercholesterolaemia", "Cardiovascular"),
        ("Haemophilia B With Inhibitors", "Hematology"),
        ("Anaemia", "Hematology"),
        ("Chemotherapy Induced Anemia", "Hematology"),
        ("Dermatitis Atopic", "Immunology & inflammation"),
        ("Atopic Dermatitis", "Immunology & inflammation"),
        ("Moderate to Severe Ulcerative Colitis", "Immunology & inflammation"),
        ("Glabellar Lines", "Eye & skin"),
        ("Dental Caries", "Other (vitamins, fluids, diagnostics)"),
        ("Healthy", None),
        ("", None),
        (None, None),
    ],
)
def test_area_rules(text, area):
    rules = areas.load_rules()
    got = areas.area_for(text, rules)
    assert (got[0] if got else None) == area


def test_a_specific_rule_beats_a_general_one():
    rules = areas.load_rules()
    # a lung cancer study carries both "Neoplasms" and "Respiratory Tract Diseases": the specific, lower number wins
    assert areas.area_for("Respiratory Tract Neoplasms", rules)[0] == "Oncology"
    assert areas.area_for("HIV Infections", rules)[0] == "HIV"  # not "Infection"
    assert areas.area_for("Lung Diseases", rules)[0] == "Respiratory & allergy"


def test_area_rules_use_only_the_seventeen_areas():
    assert len(areas.AREAS) == 17 and len(set(areas.AREAS)) == 17
    assert {r.area for r in areas.load_rules()} <= set(areas.AREAS)
    assert "Pain, addiction & anesthesia" in areas.AREAS  # spelling shared with Rx Market Pulse so the joins hold


def test_priorities_are_unique_per_rule():
    p = [r.priority for r in areas.load_rules()]
    assert p == sorted(p) and len(set(p)) == len(p)


def test_every_merck_family_has_a_franchise_regex_that_matches_its_own_name():
    rows = rx_link.load()
    assert len(rows) == 14
    for r in rows:
        rx = re.compile(r["molecule_regex"])
        assert rx.search(r["family"].lower()), r["family"]
        assert rx.search(r["franchise"]), r["family"]
    assert {r["family"] for r in rows} == set(rx_link.FRANCHISES)


def test_januvia_and_janumet_share_one_franchise():
    f = {r["family"]: r["franchise"] for r in rx_link.load()}
    assert f["JANUVIA"] == f["JANUMET"] == "sitagliptin"
    assert f["PIFELTRO"] == f["DELSTRIGO"] == "doravirine"


def test_aliases_fold_brands_and_codes_into_one_molecule():
    a = molecules.load_aliases()
    assert molecules.canonical(molecules.normalise("KEYTRUDA®"), a) == "pembrolizumab"
    assert molecules.canonical(molecules.normalise("MK-3475A"), a) == "pembrolizumab"
    assert molecules.canonical("sac-tmt", a) == "sacituzumab tirumotecan"
    assert molecules.canonical("some new drug", a) == "some new drug"
    assert molecules.canonical(None, a) is None
    assert all(v == v.lower() for v in a.values())


def test_background_therapies_are_never_aliases_and_are_lower_case():
    import csv

    from tp import sources as S

    with (S.REF / "background_therapies.csv").open(encoding="utf-8") as fh:
        bg = [r["molecule"] for r in csv.DictReader(fh)]
    assert bg and all(m == m.lower() for m in bg) and len(set(bg)) == len(bg)
    assert not set(bg) & set(molecules.load_aliases().values())
