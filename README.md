# Trial Pipeline Benchmark

**Where MSD's clinical-trial pipeline stands against 11 peers, built from the public ClinicalTrials.gov registry.** 36,612 studies fetched through a paged REST API, 33,219 of them led by one of 12 companies, harmonised, quality-checked and compared on pipeline size, reliance on one molecule, expiring revenue, upcoming readouts, trial starts and stops, and Gulf footprint. Built as a commercial-analytics case study, and a sibling of [Rx Market Pulse](https://github.com/f20230125-sudo/rx-market-pulse): the two share the same 17 therapeutic areas, and this one reads Merck's product list and patent dates from it.

| | Output | What it is | Status |
|---|---|---|---|
| 1 | **Pipeline and data-quality pipeline** | Fetch, stage, harmonise, quarantine, 25-check scorecard, marts, 248 tests | built |
| 2 | **Excel model** | Live-formula scorecard that ranks the 12 companies on five measures, with dropdown inputs and weights you can change, checked against an independent calculation | built, verified in Excel |
| 3 | **Dashboard** | Eight-section report with a table view behind every chart | planned |
| 4 | **Power BI project** | Star schema and measures generated from the same marts | planned |

Every number below comes from [`dashboard/public/data/headline.json`](dashboard/public/data/headline.json), which is written by the pipeline, not typed.

## What the data says

"Pipeline" means interventional drug, biological, genetic or combination-product studies in Phase 1 to 3. "Active" means recruiting, not yet recruiting, enrolling by invitation or active but not recruiting. Counts are studies led by the company itself (collaborator-only studies are out), as registered on 14 October 2026.

- **MSD has the second-largest active pipeline of the 12: 238 studies**, behind AstraZeneca's 387, and the second-largest late-stage one (106 in Phase 3 or 2/3).
- **It is the most concentrated: 35.3% of MSD's active studies that reach Phase 2 or 3 (71 of 201, counting Phase 1/2) involve pembrolizumab (Keytruda)**, against 26.3% for Novo Nordisk's semaglutide and 19.4% for AstraZeneca's durvalumab. Across the whole registry there are 1,363 active pembrolizumab studies; MSD leads 86 of them (6.3%), universities, hospitals and other non-industry sponsors lead 63%.
- **The revenue that loses protection first has no late-stage trial behind it.** Januvia and Janumet, whose core protection ends in November 2026, were $416.8M of 2025 US Medicaid spend (before rebates, from Rx Market Pulse). MSD has no active late-stage diabetes study; the median peer has one. The other two Merck products with protection ending by 2028 (Dificid, Bridion) are $39.5M together.
- **31 MSD late-stage studies are due to reach primary completion in the next 24 months** (to September 2028); AstraZeneca has 67. One MSD study is overdue: still active, but its estimated completion month has passed.
- **MSD started 86 pipeline studies in 2025** against a peer median of 52. A forecast has to beat "same as last year" to be worth using, and none did (the best was "same as last year", with an average miss of 6.4%), so next year is shown as 86 with a range of 76 to 96.
- **12.7% of MSD's pipeline studies that ended in 2016 to 2025 were terminated**, against a peer median of 15.9%.
- **MSD has the smallest Gulf footprint: 5 pipeline studies with a site in the UAE, Saudi Arabia, Qatar, Kuwait, Bahrain or Oman (0.23% of its pipeline).** AstraZeneca has 31, Roche 27, Novartis 45. MSD's sites are Saudi Arabia (4 studies) and the UAE (2). Ten MSD studies once listed a Gulf country and later removed it.

## The data-quality findings that shaped the build

Found by profiling, then turned into rules, checks and tests:

- **The search is full-text, so most of what it returns is not the company.** Asking for "Bristol" returns the University of Bristol, "Roche" returns people named Roche, "Johnson & Johnson" returns Mead Johnson. The download is deliberately wide (44 searches, 1,304 distinct lead-sponsor names) and an ordered rule list decides who is who; a check fails the build if any name that mentions a company falls through.
- **"Merck" is two companies.** Merck KGaA of Darmstadt owns the name outside the US and Canada. 348 of its studies (and SpringWorks and EMD Serono, which it owns) are set aside, with a check that none reaches the MSD group.
- **Acquired companies are named only in the sponsor field.** "Cubist ... a subsidiary of Merck & Co.", Acceleron, Verona and others add **267 studies (11%) to MSD** under their owner as of October 2026. The same roll-up adds 35% to AbbVie (Allergan, Pharmacyclics) and 28% to BMS (Celgene, Juno). Divested or spun-off units (Organon, Alcon, Sandoz) are excluded, not reassigned.
- **The registry's own MeSH tags are wrong often enough to matter.** A lung-cancer study that mentions PD-L1 is also tagged with a Parkinson disease term; multiple sclerosis inherits "Autoimmune Diseases"; atopic dermatitis inherits "Genetic skin diseases". Letting the typed condition text decide first, then the MeSH terms, cut disagreements from 6.5% to 1.6% of pipeline studies and gave 97% of the active pipeline a therapeutic area. The rest is mostly healthy-volunteer Phase 1 studies and stays Unclassified.
- **Dates come in three precisions.** 799 of MSD's 2,189 start dates are a month with no day. They are stored as the first of the month and flagged, never given a made-up day.
- **Not every big enrollment number is an error.** 98 studies list more than 100,000 participants; they are observational database studies (one covers 188 million people), not pipeline.
- **Stop reasons are free text.** About a third of stopped pipeline studies say "see detailed description" or fit no theme, so the themes are shown as indicative.
- **The counts are checked against the live API.** The 2,189 studies whose lead name contains "Merck Sharp & Dohme" equal a fresh API count on the same data date.

See [`docs/data-quality-scorecard.md`](docs/data-quality-scorecard.md) (generated, not hand-written).

## Run it

```bash
pip install -r requirements.txt
python -m tp.fetch            # about 75 requests, 178 MB, resumable; skip it to use the committed manifest only
python -m tp.sponsors --census   # classify every fetched sponsor name; exit 1 if one mentioning a company is unmapped
python -m tp.build            # stage, model and marts into DuckDB (about 70 seconds)
python -m tp.dq               # data-quality scorecard (add --offline to skip the live API check)
python -m tp.forecast         # backtested forecast of trial starts
python -m tp.export_json      # JSON for the dashboard and headline.json
pytest                        # unit tests plus data tests against the built warehouse
python -m tp.workbook         # excel/Pipeline-Benchmark-Model.xlsx
```

To re-verify the Excel model (needs Excel on Windows): `powershell tools/excel_probe.ps1 -Path excel/Pipeline-Benchmark-Model.xlsx -Out probe.json`, then `python tools/verify_workbook.py probe.json`.

The raw pages are not committed (178 MB); `data/snapshot/manifest.json` records exactly what was fetched, and the pipeline refuses a snapshot the API refreshed during the download.

## How it fits together

```
 ClinicalTrials.gov API v2   44 searches by lead sponsor, plus every pembrolizumab study
        │                     tp.fetch: paged, retried, resumable, totals checked against the API
        ▼
   stage ── 36,612 studies as published, one typed row each, plus conditions, interventions, sites
        │
        ├── quarantine ── 3,393 studies set aside, each with the reason (not one of the 12 groups, ...)
        ▼
   harmonise ── sponsor roll-up · therapeutic area (text, then MeSH) · molecule keys · dates · phases · countries
        │
   study (33,219, one row each) · study_molecule · study_country · study_rx_link (Merck products, from Rx Market Pulse)
        ▼
   marts: pipeline · concentration · expiring revenue · readouts · starts and stops · Gulf · forecast
        │                    │                      │
   dashboard (JSON)     Excel model            Power BI project            data-quality scorecard
```

SQL lives in [`sql/`](sql) (numbered, one purpose each); Python in [`src/tp/`](src/tp). Rules a reviewer can edit without code: [`data/ref/`](data/ref) (sponsors, areas, molecules, stop reasons, countries).

## Verification

- **248 tests.** Unit tests for the fetcher (pagination, retry with Retry-After, resume, a refresh mid-run), the sponsor rules (every alias and every trap above), dates, phases, stop themes, molecule keys and area rules. Data tests on the built warehouse: fetched studies equal in-scope plus quarantined, one row per study, Merck KGaA never in the MSD group, every country mapped, marts add back to the study table, the exported JSON matches the warehouse.
- **25 data-quality checks** across completeness, validity, uniqueness, reconciliation, coverage, harmonisation and timeliness: 20 pass, 0 fail, 5 reported for information.
- **The Excel model was verified by driving Excel itself.** Six input scenarios (different focus company, area, stage, status scope, window, weighting preset and data date) are evaluated by Excel's own formulas through COM, and every number on the Scorecard (counts, percentiles, scores, ranks, tiers), the area matrix and the expiring-revenue sheet is compared with a Python recalculation that shares no code with the workbook (`tools/verify_workbook.py`). The first run found two real faults: a check that pointed at the wrong column, and a rank formula that gave two companies the same rank when their scores were equal on paper but differed by 5 x 10^-17 in floating point. Both are fixed and the six scenarios now match exactly.
- **A reconciliation against the source.** Per-search counts equal the totals the API announced, the data date is unchanged from the start to the end of the download, and the MSD count equals a fresh call to the live API.

## What this is not

A registered study is not a launch plan, and counts are studies, not programmes or value. Estimated dates slip, and primary completion is when the last participant is examined for the main outcome, not when results are announced. The registry lags: 90 of the 2,416 active pipeline studies were last verified more than 12 months ago. Only studies the company itself leads are counted, so partner-led and investigator-led studies are missed. Sites are as registered; a registered site may never have enrolled. Acquisitions registered under names outside the 44 searches are missed. The revenue figures are US Medicaid pharmacy spend before rebates, a signal of scale and not company revenue, and protection dates are the FDA Orange Book core dates (a biologic such as Keytruda has none). Ownership is as of October 2026.

## Layout

```
src/tp/        fetch, sponsors, build, dq, forecast, export_json, and the tested harmonisation modules
sql/           01-02 staging · 03 quarantine · 04 dimensions · 05 facts · 06-10 marts
data/ref/      editable rule files (sponsors, areas, molecules, stop reasons, countries, Merck products)
data/marts/    the small analysis tables, committed
data/snapshot/ manifest of exactly what was fetched
excel/         the workbook
dashboard/     exported JSON (the dashboard itself is planned)
docs/          data-quality scorecard, case studies (interview order)
tests/  tools/ pytest suite; the Excel verification harness; helper that builds the country list
```
