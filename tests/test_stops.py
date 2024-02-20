import pytest

from tp import stops

RULES = stops.load_rules()


@pytest.mark.parametrize(
    "text,expected",
    [
        ("See termination reason in detailed description.", "Not stated"),
        ("see detailed description", "Not stated"),
        (None, "Not stated"),
        ("", "Not stated"),
        ("Sponsor decision", "Business or strategic"),
        ("Business objectives have changed", "Business or strategic"),
        ("strategic considerations", "Business or strategic"),
        ("Study closed due to portfolio prioritization", "Business or strategic"),
        ("The development program has been terminated", "Business or strategic"),
        # negated safety must not become a safety stop
        ("Sponsor decision, the decision is not related to any safety concern.", "Business or strategic"),
        ("Strategic decision unrelated to safety or efficacy", "Business or strategic"),
        ("Early discontinuation based on strategic sponsor decision not driven by any safety concerns",
         "Business or strategic"),
        ("Study was cancelled before enrolment for reasons not related to vaccine safety or efficacy.",
         "Business or strategic"),
        ("Safety issue: the trial was prematurely terminated due to safety concerns", "Safety"),
        ("The overall benefit-risk profile does not support continued development", "Safety"),
        ("Lack of efficacy", "Efficacy or futility"),
        ("The study met futility criteria at pre-planned interim analysis", "Efficacy or futility"),
        ("Stopped for futility. Phase 3 studies not likely to meet primary endpoints.", "Efficacy or futility"),
        ("Insufficient enrollment", "Enrolment"),
        ("Slow recruitment", "Enrolment"),
        ("Poor accrual", "Enrolment"),
        ("Study stopped due to COVID-19 pandemic", "COVID-19"),
        ("Logistic reasons associated with the FDA-imposed clinical hold.", "Supply, regulatory or operational"),
        ("Company decision taken in light of demands by certain national health authorities",
         "Supply, regulatory or operational"),
        ("Drug supply problems", "Supply, regulatory or operational"),
        ("The principal investigator moved", "Supply, regulatory or operational"),
        ("blue", "Other"),
    ],
)
def test_theme(text, expected):
    assert stops.theme(text, RULES) == expected


def test_every_theme_a_rule_can_return_is_a_known_theme():
    assert {r.theme for r in RULES} <= set(stops.THEMES)
    assert set(stops.THEMES) >= {"Not stated", "Other", "Safety"}
