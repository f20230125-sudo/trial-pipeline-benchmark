"""Every alias and every trap found in the real ClinicalTrials.gov lead-sponsor names (15 Oct 2026 snapshot)."""

from __future__ import annotations

import pytest

from tp import sponsors
from tp import sources as S

RULES = sponsors.load_rules()


def c(name):
    m = sponsors.classify(name, RULES)
    return m.group, m.kind


@pytest.mark.parametrize(
    "name,group,kind",
    [
        # MSD: the company's own entities
        ("Merck Sharp & Dohme LLC", "MSD", "parent"),
        ("Merck Sharp & Dohme Corp.", "MSD", "parent"),
        ("MSD Italia S.r.l.", "MSD", "parent"),
        ("MSD R&D (China) Co., Ltd.", "MSD", "parent"),
        ("MSD Pharmaceuticals LLC", "MSD", "parent"),
        ("MSD Korea Ltd.", "MSD", "parent"),
        # MSD: acquired firms, named as subsidiaries of Merck & Co.
        ("Cubist Pharmaceuticals LLC, a subsidiary of Merck & Co., Inc. (Rahway, New Jersey USA)", "MSD", "acquired"),
        ("Acceleron Pharma, Inc., a wholly-owned subsidiary of Merck & Co., Inc., Rahway, NJ USA", "MSD", "acquired"),
        ("Verona Pharma, Inc., a subsidiary of Merck & Co., Inc. (Rahway, New Jersey USA", "MSD", "acquired"),
        ("Prometheus Biosciences, Inc., a subsidiary of Merck & Co., Inc. (Rahway, New Jersey USA)", "MSD", "acquired"),
        ("ArQule, Inc., a subsidiary of Merck Sharp & Dohme LLC, a subsidiary of Merck & Co., Inc. (Rahway, NJ USA)",
         "MSD", "acquired"),
        ("Schering-Plough", "MSD", "acquired"),
        ("Themis Bioscience GmbH", "MSD", "acquired"),
        # The trap: Merck KGaA is a different company and must never count as MSD
        ("Merck KGaA, Darmstadt, Germany", "Merck KGaA and affiliates (not MSD)", "excluded"),
        ("Merck Healthcare KGaA, Darmstadt, Germany, an affiliate of Merck KGaA, Darmstadt, Germany",
         "Merck KGaA and affiliates (not MSD)", "excluded"),
        ("EMD Serono Research & Development Institute, Inc.", "Merck KGaA and affiliates (not MSD)", "excluded"),
        ("SpringWorks Therapeutics, Inc., a healthcare company of Merck KGaA, Darmstadt, Germany",
         "Merck KGaA and affiliates (not MSD)", "excluded"),
        ("Merck Medication Familiale", "Merck KGaA and affiliates (not MSD)", "excluded"),
        ("Dupont Merck", "Historic joint venture (not MSD)", "excluded"),
        ("MSD Wellcome Trust Hilleman Laboratories Pvt. Ltd.", "Joint venture (not wholly MSD)", "excluded"),
        ("Organon and Co", "Spun off (Organon)", "excluded"),
        # Peers: own entities and acquired firms
        ("Pfizer", "Pfizer", "parent"),
        ("Wyeth is now a wholly owned subsidiary of Pfizer", "Pfizer", "acquired"),
        ("Seagen Inc.", "Pfizer", "acquired"),
        ("Arena Pharmaceuticals", "Pfizer", "acquired"),
        ("AstraZeneca", "AstraZeneca", "parent"),
        ("MedImmune LLC", "AstraZeneca", "acquired"),
        ("Alexion Pharmaceuticals, Inc.", "AstraZeneca", "acquired"),
        ("Novartis Pharmaceuticals", "Novartis", "parent"),
        ("Tourmaline Bio, Inc., a Novartis Company", "Novartis", "acquired"),
        ("Hoffmann-La Roche", "Roche", "parent"),
        ("Genentech, Inc.", "Roche", "acquired"),
        ("Spark Therapeutics, Inc.", "Roche", "acquired"),
        ("Bristol-Myers Squibb", "BMS", "parent"),
        ("Celgene Corporation", "BMS", "acquired"),
        ("Juno Therapeutics, a Subsidiary of Celgene", "BMS", "acquired"),
        ("Karuna Therapeutics, Inc., a Bristol Myers Squibb company", "BMS", "acquired"),
        ("Turning Point Therapeutics, Inc.", "BMS", "acquired"),
        ("Eli Lilly and Company", "Lilly", "parent"),
        ("DICE Therapeutics, Inc., a wholly owned subsidiary of Eli Lilly and Company", "Lilly", "acquired"),
        ("Loxo Oncology, Inc.", "Lilly", "acquired"),
        ("Novo Nordisk A/S", "Novo Nordisk", "parent"),
        ("Dicerna Pharmaceuticals, Inc., a Novo Nordisk company", "Novo Nordisk", "acquired"),
        ("AbbVie", "AbbVie", "parent"),
        ("AbbVie (prior sponsor, Abbott)", "AbbVie", "parent"),
        ("Allergan", "AbbVie", "acquired"),
        ("Naurex, Inc, an affiliate of Allergan plc", "AbbVie", "acquired"),
        ("Pharmacyclics LLC.", "AbbVie", "acquired"),
        ("GlaxoSmithKline", "GSK", "parent"),
        ("ViiV Healthcare", "GSK", "acquired"),
        ("Stiefel, a GSK Company", "GSK", "acquired"),
        ("Sanofi", "Sanofi", "parent"),
        ("Sanofi Pasteur, a Sanofi Company", "Sanofi", "parent"),
        ("Genzyme, a Sanofi Company", "Sanofi", "acquired"),
        ("Janssen Research & Development, LLC", "J&J", "parent"),
        ("Johnson & Johnson Pharmaceutical Research & Development, L.L.C.", "J&J", "parent"),
        ("Ortho-McNeil Janssen Scientific Affairs, LLC", "J&J", "parent"),  # McNeil here is pharma, not consumer
        ("Xian-Janssen Pharmaceutical Ltd.", "J&J", "parent"),
        ("Actelion", "J&J", "acquired"),
        ("Intra-Cellular Therapies, Inc.", "J&J", "acquired"),
        # Divested or spun-off units are excluded, not reassigned
        ("Alcon, a Novartis Company", "Divested or spun off", "excluded"),
        ("Novartis Vaccines", "Divested or spun off", "excluded"),
        ("Johnson & Johnson Consumer Inc. (J&JCI)", "Divested or spun off", "excluded"),
        ("Johnson & Johnson Consumer and Personal Products Worldwide", "Divested or spun off", "excluded"),
        ("Opella Healthcare Group SAS, a Sanofi Company", "Divested or spun off", "excluded"),
        # Search-word traps: full-text matches that are not the company
        ("University of Bristol", "Academic, hospital or charity", "excluded"),
        ("University Hospitals Bristol and Weston NHS Foundation Trust", "Academic, hospital or charity", "excluded"),
        ("The Novo Nordisk Foundation Center for Basic Metabolic Research", "Academic, hospital or charity",
         "excluded"),
        ("University of Rochester", "Academic, hospital or charity", "excluded"),
        ("Anne Roche, MA", "Individual (not a company)", "excluded"),
        ("William Janssen, MD", "Individual (not a company)", "excluded"),
        ("Turning Point", "Other company with the same word", "excluded"),
        ("Mead Johnson Nutrition", "Other sponsor", "excluded"),
        ("M.D. Anderson Cancer Center", "Other sponsor", "excluded"),
        ("Regeneron Pharmaceuticals", "Other sponsor", "excluded"),
    ],
)
def test_classify(name, group, kind):
    assert c(name) == (group, kind)


def test_missing_name_belongs_to_nobody():
    assert c(None) == ("Other sponsor", "excluded")
    assert c("   ") == ("Other sponsor", "excluded")


def test_a_bare_merck_is_not_assumed_to_be_msd():
    # There is deliberately no generic "Merck" rule: the name is ambiguous, so it must be decided by hand.
    assert c("Merck") == ("Other sponsor", "excluded")
    assert sponsors.suspicious("Merck", sponsors.classify("Merck", RULES), sponsors.search_terms())


def test_suspicious_flags_a_company_name_that_matched_no_rule():
    terms = sponsors.search_terms()
    m = sponsors.classify("Pfizer-adjacent Newco", RULES)  # starts with Pfizer? no: ^Pfizer needs a leading match
    assert m.group in ("Pfizer", "Other sponsor")
    odd = sponsors.classify("The Lilly Institute for Nothing", RULES)
    assert odd.kind == "excluded"
    unmatched = sponsors.classify("Lilly Newco Labs", RULES)  # no 'Eli Lilly', not a rule: falls through
    assert unmatched.group == "Other sponsor"
    assert sponsors.suspicious("Lilly Newco Labs", unmatched, terms)
    assert sponsors.suspicious("Mead Johnson Nutrition", sponsors.classify("Mead Johnson Nutrition", RULES), terms) is None
    assert sponsors.suspicious("University of Rochester", sponsors.classify("University of Rochester", RULES), terms) is None


def test_rule_file_structure():
    orders = [r.order for r in RULES]
    assert orders == sorted(set(orders))
    assert RULES[-1].group == "Other sponsor" and RULES[-1].pattern.pattern == ".*"
    # Exclusions must run before any company rule, or a namesake would be claimed by the company
    first_company = next(i for i, r in enumerate(RULES) if r.in_scope)
    assert all(r.kind == "excluded" for r in RULES[:first_company])
    assert {r.group for r in RULES if r.in_scope} == set(sponsors.GROUPS)


def test_every_group_has_a_parent_rule():
    for g in sponsors.GROUPS:
        assert any(r.group == g and r.kind == "parent" for r in RULES), g


def test_search_terms_cover_every_group():
    terms = sponsors.search_terms()
    assert set(terms) == set(sponsors.GROUPS)


@pytest.mark.skipif(not S.RAW.exists(), reason="snapshot not downloaded")
def test_every_fetched_name_is_decided():
    census = sponsors.lead_name_census()
    terms = sponsors.search_terms()
    problems = [sponsors.suspicious(n or "", sponsors.classify(n, RULES), terms) for n, _ in census]
    assert [p for p in problems if p] == []
    msd_in_scope = sum(k for n, k in census if (m := sponsors.classify(n, RULES)).group == "MSD" and m.in_scope)
    assert 2350 <= msd_in_scope <= 2550
    kgaa = [n for n, _ in census if sponsors.classify(n, RULES).group == "MSD" and "KGaA" in (n or "")]
    assert kgaa == []
