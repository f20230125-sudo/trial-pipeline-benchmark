"""Study phases. The API gives a list of codes: ["PHASE1", "PHASE2"] is one Phase 1/2 study, not two studies.

phase_max is the most advanced phase the study contains; "late stage" means phase_max 3 (Phase 2/3 or Phase 3).
Phase 4 (after approval) and "not applicable" (devices, behavioural) are real studies but not drug-development pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Phase:
    label: str
    phase_max: int | None  # None when the study has no drug-development phase
    rank: int  # display order, early to late
    pipeline: bool  # counts as drug-development pipeline


# Display order of every label this module can return.
LABELS = ["Early Phase 1", "Phase 1", "Phase 1/2", "Phase 2", "Phase 2/3", "Phase 3", "Phase 4", "Not applicable",
          "Not stated"]

_ORDER = ["EARLY_PHASE1", "PHASE1", "PHASE2", "PHASE3", "PHASE4"]
_NAMES = {"EARLY_PHASE1": "Early Phase 1", "PHASE1": "Phase 1", "PHASE2": "Phase 2", "PHASE3": "Phase 3",
          "PHASE4": "Phase 4"}
_MAX = {"EARLY_PHASE1": 1, "PHASE1": 1, "PHASE2": 2, "PHASE3": 3, "PHASE4": 4}

NOT_STATED = Phase("Not stated", None, LABELS.index("Not stated"), False)
NOT_APPLICABLE = Phase("Not applicable", None, LABELS.index("Not applicable"), False)


def parse(codes: list[str] | str | None) -> Phase:
    """Accepts the API's list, or a joined string such as "PHASE1,PHASE2" or "PHASE1/PHASE2"."""
    if codes is None:
        return NOT_STATED
    if isinstance(codes, str):
        codes = codes.replace("/", ",").replace("|", ",").split(",")
    cleaned = {c.strip().upper() for c in codes if c and c.strip()}
    if cleaned == {"NA"}:
        return NOT_APPLICABLE
    known = sorted((c for c in cleaned if c in _MAX), key=_ORDER.index)
    if not known:
        return NOT_STATED
    if known == ["PHASE1", "PHASE2"]:
        label = "Phase 1/2"
    elif known == ["PHASE2", "PHASE3"]:
        label = "Phase 2/3"
    else:
        label = _NAMES[known[-1]]  # a single phase; odd combinations are reported as their most advanced phase
    top = known[-1]
    return Phase(label, _MAX[top], LABELS.index(label), top != "PHASE4")
