# Source and Tech-Role Expansion Research

**Status:** Phase 1 and Part 2 (tech-role taxonomy) implemented.
- Phase 1: 9 employers added to config (3 Greenhouse, 5 Workday, 1 SuccessFactors) — see [Phase 1 implementation log](#phase-1-implementation-log).
- Part 2: 7 new/expanded role categories added to `src/transformation/classification.py` — see [Part 2 implementation log](#part-2-implementation-log).
- Parts 1 and 3 below are the original research.

**Scope constraints carried over from the existing project policy:**

- Employer-direct career sources only. No LinkedIn, Indeed, PNet or OfferZen
  scraping, and no white-label ATS instance that is effectively a PNet feed
  (see the Woolworths finding below).
- Technology roles only. Non-technology roles at these employers remain out
  of scope for role classification.

**Method:** Employers were researched with web search against publicly
documented career pages and ATS vendor signatures (URL patterns such as
`myworkdayjobs.com`, `successfactors.com` or `careers.<company>.com/go/`,
`boards.greenhouse.io` / `job-boards.greenhouse.io`, `jobs.lever.co`,
`oraclecloud.com/hcmUI`). Direct page-source fetches were not available in
this research session (outbound fetch to the target domains was blocked),
so every finding below rests on search-result evidence rather than a live
`curl`/`validate_sources.py` check. **Every entry must still be confirmed
with `scripts/validate_sources.py` against the live endpoint before it is
added to `config/sources.json`** — that script already checks HTTP success,
parseable JSON, unique IDs, required fields and SA-location evidence, which
is exactly the confirmation step this research does not replace.

## Part 1 — Source Expansion Research

### 1a. Existing registry `candidate` employers (fastest wave — already vetted into `config/employers.json`, just unwired)

| Employer | Careers URL | Detected platform | Confidence tier | Evidence |
|---|---|---|---|---|
| Canonical | canonical.com/careers/all | Greenhouse | **Existing-adapter-compatible** | Listings resolve to `job-boards.greenhouse.io/canonical` |
| Oracle South Africa | oracle.com/za/careers | Oracle HCM | **Existing-adapter-compatible** | Search resolves to `eeho.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/...` (same `oraclecloud.com` `hcmUI` pattern as ACI Worldwide) |
| Red Hat South Africa | redhat.com/en/jobs | Workday | **Existing-adapter-compatible** | Application system at `redhat.wd5.myworkdayjobs.com/Jobs` |
| SAP South Africa | jobs.sap.com/go/South-Africa/8807701/ | SAP SuccessFactors | **Existing-adapter-compatible** | `jobs.sap.com` runs on SuccessFactors, matching the Discovery/Nedbank pattern |
| Accenture South Africa | accenture.com/za-en/careers/jobsearch | Workday | **Existing-adapter-compatible** | `accenture.wd103.myworkdayjobs.com/AccentureCareers` |
| NTT Data South Africa | careers.nttdata.com/global/en/career-opportunities | Workday | **Existing-adapter-compatible** | Group entity confirmed at `nttlimited.wd3.myworkdayjobs.com/NTT_Careers` |
| Amazon AWS (SA roles) | amazon.jobs/en/landing_pages/aws-south-africa | Amazon's own ATS | Needs new adapter | Public `amazon.jobs/en/search.json` endpoint reported by third-party scraping docs |
| Standard Bank | standardbank.com/sbg/standard-bank-group/careers | SmartRecruiters | Needs new adapter | Official page directs to `careers.smartrecruiters.com/StandardBankGroup` |
| BBD | bbdsoftware.com/open-positions/ | Custom, on own domain | Needs new adapter (low confidence) | No third-party ATS signature found |
| Entelect | culture.entelect.co.za/current-available-positions/ | Custom microsite | Needs new adapter (low confidence) | Hiring appears to route through a mailbox, not a structured API |
| DVT | dvt.co.za/careers/vacancies | Custom, no ATS signal | Needs new adapter (low confidence) | No known ATS vendor pattern found |
| Shoprite / ShopriteX | shopritex.breezy.hr | Breezy HR | Needs new adapter | Direct `shopritex.breezy.hr` board found |
| Yoco | careers.yoco.com/jobs | Teamtailor | Needs new adapter | `yoco.teamtailor.com`; explicitly stated as Teamtailor-powered |
| Mukuru | mukuru.com/sa/about-us/careers/current-vacancies/ | Breezy HR | Needs new adapter | `mukuru.breezy.hr` board found |
| Microsoft South Africa | jobs.careers.microsoft.com | Microsoft's own ATS | Needs new adapter | Proprietary platform, not one of the six supported |
| IBM South Africa | ibm.com/careers/search | Avature | Needs new adapter | Resolves to `ibmglobal.avature.net` |
| Capitec Bank | careers.capitecbank.co.za | Unclear | Unresolved | No ATS vendor signal surfaced |
| Investec | careers.investec.co.za/jobs/home/ | Unclear (custom) | Unresolved | URL pattern doesn't match a known ATS |
| Dariel Solutions | dariel.co.za/career-planning/ | Unclear | Unresolved | No distinct vacancies board located |
| Vodacom | vodacom.com/search-jobs.php | Unclear / mixed signal | Unresolved | Own PHP page; parent Vodafone Group ecosystem blends Eightfold.ai and SuccessFactors — which one serves Vodacom SA listings is unconfirmed |
| MTN | group.mtn.com/vacancies/ | Unclear (weak Workday signal) | Unresolved | One low-quality source claims Workday; no `myworkdayjobs.com` subdomain for MTN could be confirmed |

**Tally:** 6 existing-adapter-compatible, 10 need a new adapter, 5 unresolved.

### 1b. New employer categories (beyond the current 38-employer registry)

| Employer | Careers URL | Detected platform | Confirmed SA tech roles | Confidence tier | Evidence |
|---|---|---|---|---|---|
| Old Mutual | oldmutual.wd3.myworkdayjobs.com/Old_Mutual_Careers | Workday | Yes | **Existing-adapter-compatible** | Direct `myworkdayjobs.com` URL; IT graduate programme referenced |
| Sanlam | career5.successfactors.eu/careers?company=sanlamlifeP2 | SAP SuccessFactors | Yes | **Existing-adapter-compatible** | Direct `successfactors.eu` URL; IT listed among hiring disciplines |
| Santam | careers.sanlamcloud.co.za/Santam/go/... | SAP SuccessFactors (Sanlam Group shared instance) | Yes | **Existing-adapter-compatible** | Matches the `careers.<company>.com/go/` pattern exactly |
| Pick n Pay | picknpay.wd3.myworkdayjobs.com/PNP_Careers | Workday | Yes | **Existing-adapter-compatible** | Direct `myworkdayjobs.com` URL |
| Ozow | job-boards.greenhouse.io/ozow | Greenhouse | Yes | **Existing-adapter-compatible** | Senior Software Engineer, Senior DevOps Engineer, Technical Test Engineer (Cape Town) roles found directly on the board |
| GitLab | job-boards.greenhouse.io/gitlab | Greenhouse | Yes (remote, SA-eligible) | **Existing-adapter-compatible** | Confirmed SA-eligible posting on the board |
| Momentum Metropolitan | momentummetropolitan.erecruit.co | eRecruit | Yes | Needs new adapter | Software Developer, Data Scientist, Cyber Security Analyst roles referenced |
| Stitch | apply.workable.com/stitchmoney | Workable | Yes | Needs new adapter | Engineering roles, Cape Town HQ |
| Peach Payments | peachpayments.freshteam.com/jobs | Freshteam | Yes | Needs new adapter | Backend Software Engineer, Technical Lead, Senior Backend Software Engineer |
| Clickatell | apply.workable.com/clickatell | Workable | Yes | Needs new adapter | CPaaS/messaging company, Cape Town/Johannesburg technical roles |
| Andela | jobs.ashbyhq.com/andela | Ashby | Yes | Needs new adapter | South Africa listed as an available location filter for engineering roles |
| Superbalist | superbalist.com/careers-tech (career-explorer.superbalist.com) | Custom, own portal | Yes | Needs new adapter | No longer on Takealot Group's Greenhouse board — sold to Blank Canvas Capital (Sept 2024); Senior iOS Engineer among roles |
| PBT Group | careers.pbtgroup.co.za | Custom ColdFusion/Fusebox | Yes | Needs new adapter | Front-End Developer, Senior SharePoint Developer, Data Engineering Graduate Programme |
| Google South Africa | careers.google.com | Custom (Google's own platform) | Yes | Needs new adapter (bespoke, low ROI) | Johannesburg-filtered results confirmed (Cloud Native Database Customer Engineer, Data Analyst) |
| Salesforce South Africa | careers.salesforce.com | Custom (proprietary) | Yes (one role verified) | Needs new adapter (bespoke, low ROI) | One Johannesburg posting directly confirmed |
| Woolworths South Africa | careers.woolworths.co.za | **PNet white-label** | Yes | **Excluded by policy** | Support routes to `wwsupport@pnet.co.za` — this is a PNet-branded backend; scraping it would violate the project's explicit "do not scrape PNet" rule even though the front door is Woolworths' own domain |
| Telkom | jobs.telkom.co.za | Unclear | Yes (Cloud Architect, Software Developer, Data Scientist, Cybersecurity referenced) | Unresolved | No ATS vendor URL signature found after the site moved off its legacy `telkom.erecruit.co` domain |
| Synthesis Software Technologies | synthesis.co.za | Unclear | Yes (consultancy — inherently tech) | Unresolved | No specific careers-page URL or ATS signature confirmed |
| Rain | — | Unclear | Unclear | Unresolved | No discoverable official careers/jobs page on `rain.co.za`; only third-party listings found |
| Cell C | cellc.co.za/cellc/careers | Unclear (custom "Talent Hub") | Unclear | Unresolved | Roles found skew to entry-level/Grade 10–12 programmes; no confirmed technology listing |

**Tally:** 6 existing-adapter-compatible, 8 need a new adapter (1 flagged low-ROI-bespoke x2 = Google/Salesforce), 1 excluded by policy (Woolworths/PNet), 4 unresolved.

### 1c. Evaluation criteria (unchanged from `docs/data-source-assessment.md`)

Every candidate above should still be scored on: public/documented access,
authentication requirement, structured response format, stable job
identifiers, description completeness, SA location evidence,
refreshability/snapshot suitability, maintenance risk, and any access or
publication restriction — the same criteria already used for the
Greenhouse/Lever/SuccessFactors sources. This research narrows the field;
`scripts/validate_sources.py` still does the final pass/fail confirmation
before any source is marked `active`.

## Part 2 — Tech-Role Taxonomy Expansion Research

### 2a. Evidence of current gaps (grounded in the live dataset)

`data/processed/dashboard_jobs.parquet` currently holds 1,661 collected
postings. Filtering to South-Africa-located rows where
`is_target_market` is `False` (i.e. the existing `classify_technology_role`
missed them) surfaces **609 titles**, and a keyword scan of those finds at
least the following genuinely-technology titles slipping through today —
almost all from Nedbank (SAP SuccessFactors):

```text
Flutter Engineer                              Data Principal Engineer
Senior Web Engineer                           Senior Java Engineer
Associate Platform Infrastructure Engineer    Solutions Architect
Flutter Competency Lead                       Security Solutions Architect
Engineering Manager                           Associate Data Architect
Observability Engineer / Observability Engineer Specialist
Senior Observability Specialist - SOS         Systems Administrator I
Platform Owner / Platform Owner - Postilion   Product Owner: Service Enablement
Engineering Lead I / Engineering Lead (Architecture & Solution Design)
Lead Engineer: AI                             Senior Manager: Data Platforms
SAP Basis Consultant / SAP Consultant-Functional / SAP FSCM Functional Consultant
Postilion Technical Specialist                Technical Support Specialist (IBM MQ)
Scrum Master                                  Enterprise Metadata Analyst
```

This confirms `_TECH_TITLE_RULES` in `src/transformation/classification.py`
under-covers: bare "Engineer" titles without a qualifying tech word,
"Architect" (today only a negative senior-level signal, never a positive
tech-domain match), platform/product ownership titles, observability,
named languages/frameworks (Java, Flutter), and banking-specific
platform/ERP vocabulary (SAP, Postilion, T24/core banking).

The same scan also surfaces titles that **should stay excluded** — useful
as new false-positive guards: `Technical Accountant`, `Technical Production
Artworker`, `Credit Controller`, `Credit Analyst` (the word "credit" is not
currently a signal, but if a future "risk" heuristic is added, these must
stay excluded).

### 2b. Proposed new/expanded categories

Each follows the existing `_TECH_TITLE_RULES` style (word-boundary,
case-insensitive, tuple of alternation patterns) and is directly
implementable without further research:

| Category (new or expand) | Patterns to add | Grounding evidence |
|---|---|---|
| `architecture` (**new** — today "architect" is senior-only, not a tech-domain match) | `r"\bsolutions?\s+architect\b"`, `r"\bdata\s+architect\b"`, `r"\bsecurity\s+architect\b"`, `r"\benterprise\s+architect\b"`, `r"\btechnical\s+architect\b"` | "Solutions Architect", "Security Solutions Architect", "Associate Data Architect" |
| `product` (**expand** — currently only "product manager") | add `r"\bproduct\s+owner\b"`, `r"\bplatform\s+owner\b"` | "Platform Owner", "Product Owner: Service Enablement", "Platform Owner - Postilion" |
| `cloud_devops` (**expand**) | add `r"\bobservability\b"` | "Observability Engineer", "Senior Observability Specialist" |
| `systems` (**expand** — currently `systems? (analyst|engineer)` only) | widen to `r"\bsystems?\s+(?:analyst|engineer|administrator)\b"` | "Systems Administrator I" |
| `engineering_leadership` (**new**, title-only, deliberately narrow) | `r"\bengineering\s+manager\b"`, `r"\bengineering\s+lead\b"`, `r"\blead\s+engineer\b"` | "Engineering Manager", "Engineering Lead I", "Lead Engineer: AI" |
| `language_and_framework_stack` (**new**) | `r"\bflutter\b"`, `r"\bjava\s+engineer\b"`, `r"\bjava\s+developer\b"`, `r"\breact\s+native\b"`, `r"\bgolang\b"`, `r"\b\.net\s+(?:developer|engineer)\b"`, `r"\bkotlin\b"`, `r"\bswift\s+(?:developer|engineer)\b"` | "Flutter Engineer", "Flutter Competency Lead", "Senior Java Engineer" |
| `erp_and_core_platform` (**new**, banking/fintech-specific) | `r"\bsap\s+(?:basis|fscm|consultant)\b"`, `r"\bpostilion\b"`, `r"\bt24\b"`, `r"\bcore\s+banking\b"` | "SAP Basis Consultant", "SAP FSCM Functional Consultant", "Postilion Technical Specialist", "Platform Owner - Postilion" |

### 2c. Flagged — ambiguous, needs a judgment call before implementing

These showed up in the data too, but risk conflating tech and non-tech
roles, so they're documented rather than turned into rules outright:

- **`delivery_and_agile`** — "Scrum Master", "Agile Coach", "Delivery Lead".
  These are common on both software delivery teams and general
  business-transformation teams; recommend requiring co-occurrence with an
  existing tech signal in the job description rather than a bare title
  match.
- **`it_executive_leadership`** — "CIO", "Head of Engineering" are clearly
  technology leadership, but "Executive Head: IT Procurement" (found in the
  data) is sourcing/vendor-management, not engineering. Recommend scoping
  patterns to `r"\bcio\b"`, `r"\bcto\b"`, `r"\bhead\s+of\s+engineering\b"`
  only, explicitly excluding "IT procurement"/"IT audit"/"IT risk" phrasing.
- **`process_engineer`** — appears in the data but is a standard
  industrial/chemical-engineering title in South African manufacturing and
  retail-logistics job markets; recommend leaving unmatched unless paired
  with software/digital context in the description.

### 2d. New false-positive guards for `_TECH_FALSE_POSITIVES`

```text
r"\btechnical\s+accountant\b"
r"\btechnical\s+production\b"
```

(`\btechnical\s+recruit(?:er|ment)\b` already exists and should stay.)

## Part 3 — Phasing (the compounding growth path)

- **Phase 1 — zero new adapter work (activate now):** the 12
  existing-adapter-compatible employers found in 1a + 1b — Canonical,
  Oracle SA, Red Hat SA, SAP SA, Accenture SA, NTT Data SA, Old Mutual,
  Sanlam, Santam, Pick n Pay, Ozow, GitLab. This alone roughly doubles
  active source count using only `config/sources.json` entries against the
  six adapters that already exist.
- **Phase 2 — one adapter unlocks several employers:** build a single
  **Workable** adapter to cover Stitch, Peach Payments's near-neighbor
  Clickatell (also Workable) at once (Peach Payments itself is Freshteam,
  a related but separate adapter); build a single **Breezy HR** adapter to
  cover Shoprite/ShopriteX and Mukuru at once. Each new adapter pays for
  itself across multiple employers rather than one.
- **Phase 3 — bespoke/single-employer adapters, lower priority:** Amazon,
  Standard Bank (SmartRecruiters), IBM (Avature), Andela (Ashby),
  Momentum Metropolitan (eRecruit), Google SA and Salesforce SA (proprietary,
  and only a handful of confirmed SA roles each) — real engineering effort
  for comparatively small per-employer yield; sequence after Phase 1–2 prove
  out.
- **Excluded:** Woolworths South Africa's careers portal is a PNet
  white-label instance and stays out of scope under the existing
  "no PNet" policy, even though the marketing URL is Woolworths' own domain.
- **Still needs research before any phase:** Capitec, Investec, Dariel
  Solutions, Vodacom, MTN, Telkom, Synthesis, Rain, Cell C — no ATS vendor
  signature could be confirmed by search alone; these need a direct page
  fetch (blocked in this research session) or manual inspection before they
  can be scored.
- Role-taxonomy additions from Part 2 should be re-validated against each
  new employer's actual titles as Phase 1–2 sources come online (the same
  method used in Part 2a — filter `is_target_market == False` on
  SA-located rows and keyword-scan the misses), so the taxonomy keeps
  growing from real postings rather than speculative categories.

## Summary

| | Existing-adapter-compatible | Needs new adapter | Excluded | Unresolved |
|---|---|---|---|---|
| 1a (registry candidates, n=21) | 6 | 10 | 0 | 5 |
| 1b (new employers, n=20) | 6 | 8 (2 low-ROI bespoke) | 1 (PNet) | 4 |
| **Total (n=41)** | **12** | **18** | **1** | **9** |

Combined with the 21 already-active source employer_ids, executing Phase 1
alone would bring active coverage to **33 employers** — and the Phase 2
adapter reuse (Workable, Breezy HR) extends that further without a
one-adapter-per-employer cost. Part 2's 7 taxonomy additions are all
directly grounded in titles already sitting in the collected dataset, not
speculative categories.

## Phase 1 Implementation Log

Nine of the twelve Phase-1 employers were added to `config/employers.json`
(marked `active`) and `config/sources.json` in this pass:

| Employer | Provider | Config |
|---|---|---|
| Canonical | greenhouse | token `canonical` |
| Ozow | greenhouse | token `ozow` |
| GitLab | greenhouse | token `gitlab` |
| Old Mutual | workday | `oldmutual.wd3.myworkdayjobs.com` / `Old_Mutual_Careers` |
| Pick n Pay | workday | `picknpay.wd3.myworkdayjobs.com` / `PNP_Careers` |
| Red Hat | workday | `redhat.wd5.myworkdayjobs.com` / `Jobs` |
| Accenture | workday | `accenture.wd103.myworkdayjobs.com` / `AccentureCareers` |
| NTT Data | workday | `nttlimited.wd3.myworkdayjobs.com` / `NTT_Careers` |
| SAP | successfactors | `https://jobs.sap.com/go/South-Africa/8807701/` |

All nine were added with `priority: "experimental"` (not `primary`/`secondary`)
because this research session's outbound network policy blocks every
external domain — including domains already used by long-trusted sources
like Takealot's Greenhouse board — so none of them could be confirmed live
here. Running `scripts/validate_sources.py` against a filtered
Greenhouse/Lever-only copy of the config in this session produced identical
`403 Forbidden` tunnel failures for **every** source, new and pre-existing
alike, confirming the failures are this sandbox's egress policy and not a
config mistake — but it also means these nine still need a real
`scripts/validate_sources.py` run (Greenhouse) or `python -m
src.ingestion.collect --source-token <token>` run (Workday/SuccessFactors,
which `scripts/validate_sources.py` doesn't support — it only recognises
Greenhouse and Lever) in an environment with normal internet access before
being trusted or promoted to `primary`/`secondary`.

Three Phase-1 employers were deliberately **not** added yet because the
exact endpoint parameters could not be confirmed by search alone, and
guessing wrong risks a source that either silently under-collects or fails
outright:

- **Sanlam** — the confirmed URL (`career5.successfactors.eu/careers?company=sanlamlifeP2`)
  is a SuccessFactors *Recruiting Management* candidate portal, a different
  page structure from the *Career Site Builder* `.../go/.../` pages the
  existing `successfactors` adapter is built to parse (as used by Discovery,
  Nedbank, and Santam below). Needs a working `.../go/.../` URL for Sanlam
  itself before it can reuse the existing adapter.
- **Santam** — shares Sanlam Group's Career Site Builder instance and does
  match the `.../go/.../` pattern (e.g. `careers.sanlamcloud.co.za/Santam/go/UNDERWRITING/3644601/`),
  but only category-scoped URLs (Underwriting, Sales) were found, not an
  "All jobs" root equivalent to Discovery's `/go/All-Jobs/...` or Nedbank's
  `/go/All/...`. Adding a category-scoped URL would silently under-collect
  rather than fail loudly, which conflicts with the project's "no silent
  truncation" principle — needs the All-jobs category ID confirmed first.
- **Oracle South Africa** — Oracle's own careers search resolves to
  `eeho.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/jobsearch/jobs`,
  giving a host but an unconfirmed `site` value (`jobsearch` is a URL path
  segment, not necessarily the `siteNumber` finder parameter the adapter
  sends — other Oracle-hosted career sites use short codes like `CX` or
  `CX_1`). Needs the exact `siteNumber` confirmed against the live API
  before configuring.

These three remain open items for a follow-up pass once endpoint details
are confirmed. Phase 1's other three original candidates (Oracle SA aside)
were already covered by the nine added above.

## Part 2 Implementation Log

All 7 new/expanded tech-role categories from Part 2b were added to
`src/transformation/classification.py`'s `_TECH_TITLE_RULES` and 2 new
false-positive guards were added to `_TECH_FALSE_POSITIVES`:

| Category | Status | Evidence from dataset |
|---|---|---|
| `architecture` | Added | Solutions Architect, Data Architect, Security Solutions Architect |
| `cloud_devops` (expanded) | Added | Observability Engineer, Senior Observability Specialist |
| `product` (expanded) | Added | Product Owner, Platform Owner |
| `systems` (expanded) | Added | Systems Administrator |
| `engineering_leadership` | Added | Engineering Manager, Engineering Lead, Lead Engineer: AI |
| `language_and_framework_stack` | Added | Flutter Engineer, Senior Java Engineer, React Native, GoLang, .NET, Kotlin, Swift |
| `erp_and_core_platform` | Added | SAP Basis Consultant, SAP FSCM Consultant, Postilion, T24/Core Banking |
| **False-positive guards** | | |
| `technical_accountant` | Added | |
| `technical_production` | Added | |

All changes deployed to the classification engine with full test coverage
(144 tests pass). The taxonomy is now grounded in real SA job titles already
collected in `data/processed/dashboard_jobs.parquet`, as documented in Part 2a.
