"""Where every input comes from and where every output goes. One place, so the README and the code cannot drift apart.

The only data source is the ClinicalTrials.gov REST API v2 (https://clinicaltrials.gov/data-api/api). It is free, needs
no key, and answers from the UAE (checked 15 Oct 2026). Open Payments and Medicare Part D, the usual commercial-operations
datasets, return HTTP 403 from the UAE, so they are not used.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "ctgov"
SNAPSHOT = ROOT / "data" / "snapshot"
MANIFEST = SNAPSHOT / "manifest.json"
WAREHOUSE = ROOT / "data" / "warehouse" / "tp.duckdb"
MARTS = ROOT / "data" / "marts"
REF = ROOT / "data" / "ref"
SQL = ROOT / "sql"
DOCS = ROOT / "docs"

API = "https://clinicaltrials.gov/api/v2"
STUDIES_URL = f"{API}/studies"
VERSION_URL = f"{API}/version"

USER_AGENT = "trial-pipeline-benchmark/1.0 (public portfolio project; https://github.com/f20230125-sudo/trial-pipeline-benchmark)"

# Asked for together on purpose: requesting StartDate alone drops StartDateType.
FIELDS = ",".join(
    [
        "NCTId", "BriefTitle", "Acronym", "OrgStudyId", "SecondaryId",
        "OverallStatus", "WhyStopped", "StatusVerifiedDate",
        "StartDate", "StartDateType", "PrimaryCompletionDate", "PrimaryCompletionDateType",
        "CompletionDate", "CompletionDateType", "StudyFirstPostDate", "LastUpdatePostDate",
        "LeadSponsorName", "LeadSponsorClass", "CollaboratorName", "CollaboratorClass",
        "StudyType", "Phase", "EnrollmentCount", "EnrollmentType",
        "DesignPrimaryPurpose", "DesignAllocation",
        "Condition", "InterventionType", "InterventionName", "InterventionOtherName",
        "LocationFacility", "LocationCity", "LocationCountry", "LocationStatus", "HasResults",
        "derivedSection.conditionBrowseModule", "derivedSection.interventionBrowseModule",
        "derivedSection.miscInfoModule",
    ]
)
