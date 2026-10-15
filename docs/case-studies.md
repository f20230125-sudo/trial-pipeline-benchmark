# Case study, in interview order

The question, what I did, what I found, what went wrong, and what I would do next. Numbers are from the built data (`dashboard/public/data/headline.json`) and are re-checked by tests; if you rebuild from a newer snapshot they will move.

## 30-second pitch

I pulled every clinical trial that MSD and eleven peer companies lead from the public ClinicalTrials.gov API, 36,612 studies after de-duplication, and compared their pipelines. The charts are the easy part. The work is that the registry's sponsor field is free text: the search for "Merck" returns a different company (Merck KGaA), acquired firms appear only as "a subsidiary of Merck & Co.", and the registry's own disease tags are sometimes wrong. I turned each of those into a rule, a test, and a check that fails the build, and I tied the counts back to the API's own totals, including a fresh call that matches MSD's 2,189 studies exactly.

## The project, Trial Pipeline Benchmark

**Question.** How does MSD's late-stage pipeline compare with its peers, how much of it rests on one molecule, is there pipeline behind the revenue whose protection ends soon, what reads out in the next two years, and how present is MSD in the Gulf, where I would work?

**What I did.**
1. A fetcher that pages through the API (1,000 studies a page), waits between requests, retries on 429 and 5xx answers honouring Retry-After, saves every page as received so a run can resume, and refuses a snapshot the API refreshed while it ran. 44 searches, 37,564 rows, 178 MB.
2. Staging: each study kept once as published, with conditions, interventions and sites as child tables. Nothing removed.
3. Quarantine: 3,393 studies set aside, each with the reason, so fetched studies always equal in-scope plus quarantined.
4. Harmonisation: an ordered sponsor rule list (who is MSD, who is Pfizer, who is a university that matched a search word), a therapeutic area for each study in the same 17 areas as my Rx Market Pulse project, one key per molecule with brand names and development codes folded together, dates with their precision, phases as a list, countries as ISO codes, and stop reasons as themes.
5. A 25-check data-quality scorecard, eight marts, a backtested forecast, and a JSON export. Merck's product list and patent dates come from the sibling project, so the revenue view and the pipeline view share one set of facts.

**What the first profile found.**
1. **1,304 distinct lead-sponsor names** came back from 44 searches, because the search is full-text. "Bristol" returned the University of Bristol and three Bristol hospital trusts; "Roche" returned people named Roche; "Johnson & Johnson" returned Mead Johnson.
2. **Merck KGaA is not MSD.** 348 studies carry its name or its subsidiaries' (EMD Serono, SpringWorks). A check fails the build if one reaches the MSD group.
3. **267 of MSD's 2,433 studies (11%) sit under acquired companies' names.** The same roll-up adds 35% to AbbVie and 28% to BMS, so comparing raw sponsor names would have understated eight of the twelve by more than 10%.
4. **The disease tags are noisy.** A lung-cancer study that mentions PD-L1 carries a Parkinson disease tag.
5. **Dates are not uniform.** About 800 of MSD's 2,189 start dates are a month with no day.
6. **98 studies list more than 100,000 participants.** I looked before deciding: they are observational database studies (one covers 188 million people), so the enrollment rule applies to pipeline studies only, and the note says why.

**Things I got wrong and fixed.**
- My first sizing of MSD's Gulf presence and total came from the API's "any sponsor" count, 4,305 studies. That includes 2,148 studies where MSD is only a collaborator. I changed the definition to studies MSD leads (2,189) and said so in the README.
- I let the registry's MeSH tags decide the therapeutic area first. Multiple sclerosis landed in immunology (it inherits "Autoimmune Diseases"), atopic dermatitis in rare disease, Alzheimer's in rare disease through "Amyloid". Reading the 14 largest disagreements showed the typed condition text was the better signal. Text first, MeSH second, then the molecule's usual area: disagreements fell from 6.5% to 1.6% and coverage of the active pipeline went to 97%.
- A pattern meant for anaemia matched "dyslipidaemia" (the letters "aemia"). Reading the text-versus-MeSH disagreements caught it, and the British spellings are now in the tests.
- A rule file stored a regex with a quantifier like `{0,60}` in an unquoted CSV field. The comma split it and the pattern was silently truncated, so "see detailed description" was classed as "Other". Every pattern field is now quoted.
- DuckDB ran out of memory (12 GB) because I set the maximum JSON object size to 200 MB, a buffer reserved per thread. The largest page is 7.4 MB; 32 MB works and the build takes about a minute.
- A data test showed 36,612 study-search pairs where the manifest said 37,564. DuckDB returns Windows file paths with backslashes when it globs, so my regex for the search name matched nothing and every study looked like it came from one search. I accept either separator now.
- Loading rule results into the database one row at a time took 52 seconds; as one JSON-lines file it takes a second. The first bulk version used CSV and broke on condition texts with quotes and line breaks.

**Be ready for.**
- *"Why only studies the company leads?"* Collaborator-only studies are other people's studies; counting them doubles MSD and every peer. The cost is that partner-led and investigator-led studies are missed, and the README says so.
- *"How do you know the sponsor roll-up is right?"* About 80 sponsor tests, one for each alias and each trap, plus a census that lists every distinct fetched name with the rule that decided it. The known gap is an acquisition registered under a name that none of the 44 searches would find.
- *"Why is MSD's Gulf footprint so small, and is that a finding or an artefact?"* Both are possible. The data say 5 of MSD's 2,146 pipeline studies list a Gulf site, against 31 of AstraZeneca's 2,787. A registered site is not an enrolled one, MSD may run Gulf trials through partners, and the count excludes studies other sponsors run for MSD. I would not claim more than the count.
- *"Is 35% on Keytruda a risk?"* It is a share of studies, not of revenue, and an oncology-heavy pipeline is a choice. What it does show is that MSD is the most concentrated of the twelve and that its next molecules (sacituzumab tirumotecan, belzutifan) are 14% and 9%.
- *"What is the revenue claim?"* Januvia and Janumet are $416.8M of 2025 US Medicaid pharmacy spend before rebates, and their core protection ends in November 2026. That is scale, not company revenue, and the patent date is when protection ends, not when a generic launches.
- *"What would you do with MSD's own data?"* Replace the public registry with the internal trial and portfolio systems and keep the same checks: every count tied to a source total, every excluded record kept with its reason, every rule readable without code.

**Next.** Add collaborator and partner-led studies as a separate, labelled view. Use the arm roles in the registry to identify comparators instead of name patterns. Add the EU clinical trials register for Europe. Track the snapshot over time so "overdue" and "dropped a Gulf country" become trends instead of one reading.

## Things to verify yourself before relying on them

- The sponsor rules and the list of acquisitions are mine, built from names in the data and public knowledge; spot-check two or three you will be asked about in `data/ref/sponsor_rules.csv`.
- The area rules are keyword rules; open `data/ref/area_rules.csv` and read what each one says.
- The Merck product matching uses the molecule, MK development code and brand name; run `python -m tp.rx_link` to see the 14 families and look at one in the warehouse.
- Check one number from the live registry yourself: search clinicaltrials.gov for "Merck Sharp & Dohme" as lead sponsor and compare the count to the scorecard's C14.
