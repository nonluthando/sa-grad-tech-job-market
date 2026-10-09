# Phase 2b: New Provider Adapter Roadmap

**Status:** SmartRecruiters and Ashby adapters shipped. Freshteam, eRecruit and
Teamtailor deprioritized (25 Sep 2026) — blocked on live endpoint inspection this
sandbox can't perform; revisit if/when that information becomes available.
Follow-up research on eRecruit (8 Oct 2026) confirmed it's a larger multi-employer
platform than first scoped, but didn't change the ROI case or unblock the adapter.
A further pass (9 Oct 2026), routed through claude.ai for real browser/network
access, confirmed Freshteam (Peach Payments) is server-rendered HTML — technically
unblocked, but currently just 1 open role — and found 9 real open SA tech roles on
Yoco's Teamtailor page, making Teamtailor the highest-priority unbuilt adapter now.
Momentum Metropolitan's eRecruit page refused the automated fetch even from that
session, so it's still genuinely blocked on a human-driven browser.
**Date:** 25 September 2026 (updated 8-9 October 2026)

## Overview

Phase 2a activated 13 sources across existing adapters (Workday, SuccessFactors, Greenhouse, Lever, Oracle HCM, Breezy HR, Workable). Phase 2b identifies and prioritizes new provider adapters needed for remaining Phase 2 employers.

---

## Priority 1: High-ROI Adapters (3–4 employers each)

### SmartRecruiters — ✅ Shipped 25 Sep 2026
**Employers:** Standard Bank (primary), 2–3 others  
**Confidence:** High  
**SA Presence:** Standard Bank confirmed at `careers.smartrecruiters.com/StandardBankGroup`  
**Adapter Complexity:** Medium (list + per-job detail, same shape as Oracle HCM/Workday)  
**Projected Jobs:** 150–200  

**Delivered:** `src/ingestion/smartrecruiters.py`, `src/transformation/smartrecruiters.py`,
full config/collect/snapshot/dataset wiring, 18 tests. Standard Bank activated in
`config/sources.json` (`enabled: true`, `priority: experimental`) and its employer
registry `collection_status` flipped to `active`. Live collection not yet validated —
this sandbox's network proxy blocks outbound requests to career-site domains, so the
real endpoint has only been reached, not confirmed to return data. Needs a live run
via the GitHub Actions data-refresh workflow before promoting past `experimental`.

---

### Freshteam (by Freshworks) — 🟡 Partially confirmed, low priority now
**Employers:** Peach Payments (primary), 1–2 others  
**Confidence:** Medium  
**SA Presence:** Peach Payments confirmed at `peachpayments.freshteam.com/jobs`  
**Adapter Complexity:** Medium (REST API, Freshworks ecosystem)  
**Projected Jobs:** 30–50 (original estimate — see finding below)

**Update (9 Oct 2026):** A page fetch (not a full Network-tab capture, but a
direct page-content read via claude.ai, which has normal internet access
this sandbox doesn't) confirmed `peachpayments.freshteam.com/jobs` is
**server-rendered HTML**, not a client-side app pulling from a hidden JSON
endpoint — the one open role ("Finance Business Partner", Cape Town) came
back embedded directly in the page content, along with the filter-chip
markup (department, job type, location, remote). Job detail links follow
`https://peachpayments.freshteam.com/jobs/<id>/<slug>`, e.g.
`/jobs/Q46VDM_WFJRm/finance-business-partner`. A direct probe of the
common Freshteam widget endpoint `/hire/widgets/jobs.json` failed to
connect, so that's still unconfirmed either way — but it doesn't matter
for the adapter decision, since the page itself already has what's needed
for a CSS-selector scraper.

**This downgrades the blocker, but also downgrades the ROI**: Peach
Payments currently has **only 1 open role**, far below the 30-50 projected
in the original scoping. The technical blocker (confirm JSON vs. HTML) is
resolved — it's HTML — but building a scraper for one single role right
now isn't worth it until Peach Payments' hiring picks back up. Worth a
periodic re-check rather than immediate adapter work.

---

### eRecruit — ⛔ Still blocked, but now a multi-employer platform, not a one-off

**Follow-up research (8 Oct 2026):** `erecruit.co` turns out to be a live,
significant South African recruitment platform — one ranking placed it
**3rd among South African jobs/career websites by traffic in July 2026**,
behind Indeed and PNet — not the defunct product one third-party company
database (Tracxn) claimed. It hosts real, currently-open job boards for at
least ten named employers, each on its own subdomain with a consistent URL
shape (`<company>.erecruit.co/candidateapp/jobs/categories/...` or
`/candidateapp/jobs/browse`):

| Employer | Subdomain | Tech-role relevance |
|---|---|---|
| **Momentum Metropolitan** (original target) | `momentummetropolitan.erecruit.co` | **Best fit** — Software Developer, Data Scientist, Cyber Security Analyst roles already referenced (Part 1 research) |
| Exxaro | `exxaro.erecruit.co` | Low–unconfirmed (mining; categories seen were audit/admin/artisans, but Exxaro has a digital-mining push that might include IT roles — unconfirmed) |
| Coca-Cola Beverages Africa (CCBA) | `ccba.erecruit.co` | Low (manufacturing/ops categories seen; no IT category confirmed) |
| Isuzu Motors South Africa | `isuzu.erecruit.co` | Low (production/assembly categories seen) |
| Omnia | `omnia.erecruit.co` | Low (agri-sciences, marketing, mining categories seen) |
| Rand Water | `randwater.erecruit.co` | Unconfirmed, not a private tech employer |
| eThekwini Municipality | `durbangov.erecruit.co` | Out of scope — municipal government, not a private employer |
| CBH | `cbh.erecruit.co` | Low (agri/poultry/SHERQ categories seen) |
| Moore South Africa | `moore-southafrica.erecruit.co` | Low (accounting/audit/tax categories seen) |
| Group Five | via erecruit.co (construction) | Low — Careers24 shows no current openings |
| PwC — graduate programme | `pwcza-graduate.erecruit.co` | Notable: **separate from** the Workday tenant (`pwc.wd3.myworkdayjobs.com`) found in the Workday research — PwC appears to split graduate hiring (eRecruit) from experienced/global hiring (Workday) |

**Still blocked exactly as before:** direct fetch of any `*.erecruit.co`
subdomain is blocked by this sandbox's egress proxy (confirmed again this
session against `isuzu.erecruit.co` and `ccba.erecruit.co`), so it's still
not possible to determine whether the platform is JSON-backed or
server-rendered HTML from here. **Needs the same manual inspection as
Freshteam** — someone with a browser needs to open dev tools → Network tab
on `momentummetropolitan.erecruit.co` (the one employer actually worth
building this adapter for, given the tech-role scan above) and capture the
request shape.

**Update (9 Oct 2026):** Tried routing this through claude.ai, which has
normal internet access this sandbox doesn't — no luck. `momentummetropolitan.erecruit.co`
refused the automated fetch (site policy disallows automated access), so
even a tool with real network access couldn't get past this one without
an actual human-driven browser session. Still genuinely needs a person to
open the page and check the Network tab.

**What this pass changes:** it doesn't unblock the adapter, but it answers
"is eRecruit worth building for just one employer?" — the honest answer is
that **Momentum Metropolitan is still the only tech-relevant employer on
this platform**; the other nine are mining/agri/manufacturing/municipal/
accounting employers with little to no technology-role yield, so this
doesn't change the adapter's projected ROI (still ~20-40 jobs from one
employer) even though the platform itself is bigger than one company.

---

## Priority 2: Medium-ROI Adapters (1–2 employers each)

### Ashby — ✅ Adapter shipped 25 Sep 2026, employer not yet activated
**Employer:** Andela (South Africa-hiring contractor platform)  
**Confidence:** Medium  
**Adapter Complexity:** Low (single-response, no pagination — same shape as Greenhouse/Lever)  
**Projected Jobs:** 20–30  

**Delivered:** `src/ingestion/ashby.py`, `src/transformation/ashby.py`, full wiring,
14 tests. Ashby's public Job Board API (`api.ashbyhq.com/posting-api/job-board/{name}`)
is unauthenticated and well documented, so the adapter itself is done and tested.
**Not yet added to `config/sources.json`**: Andela's confidence is only "Medium" and
the roadmap never confirmed its actual Ashby job-board slug (unlike Standard Bank's
SmartRecruiters slug). Guessing one risks silently pointing at the wrong board or a
404. **Needs:** confirm Andela's real job-board name (visit their careers page, look
for a `jobs.ashbyhq.com/<slug>` link), then add one `config/sources.json` entry —
no further code changes required.

### Teamtailor — 🟢 Partially confirmed, now the highest-priority unbuilt adapter
**Employer:** Yoco (fintech)  
**Confidence:** Medium–High (public Teamtailor board: `yoco.teamtailor.com`)  
**Adapter Complexity:** Medium  
**Projected Jobs:** 15–25 (original estimate — real count below is higher)

**Blocker (25 Sep 2026):** Teamtailor's general REST API requires a per-company API
token for all endpoints, including reading job listings — that's a structural
mismatch with this project's public/employer-direct/unauthenticated-sources rule, not
something a code fix works around. Individual Teamtailor-hosted career pages (like
`yoco.teamtailor.com`) may separately expose job data via `JobPosting` structured
data (schema.org JSON-LD) embedded in the page HTML for SEO, which this project
already knows how to parse (see the WP Job Manager adapter). But confirming that
requires loading the real page, which this sandbox can't do.

**Update (9 Oct 2026):** Routed through claude.ai (normal internet access).
A page-content fetch of `yoco.teamtailor.com` came back with **9 real,
current open roles, all in South Africa** (Cape Town or Johannesburg) —
and they're a strong tech-role match: Senior Frontend Engineer, Analytics
Engineer, Staff Backend Engineer, Security Analyst, Senior Product
Manager, among others. That's meaningfully better than the original
15-25 projection suggested and the best per-employer yield of anything in
this whole roadmap pass.

**Still not fully confirmed**: the fetch returned extracted page text, not
raw HTML, so it couldn't show link `href`s or confirm whether the 9 roles
come from embedded `JobPosting` JSON-LD, a different inline JSON blob, or
plain rendered markup — the one open question left. A direct probe of
Teamtailor's common `/jobs.rss` endpoint also failed to connect from that
session, so that's untested too, not ruled out. **Needs:** one more pass —
view-source (not just extracted text) on `yoco.teamtailor.com`, specifically
searching for a `<script type="application/ld+json">` block — to pick
between a JSON-LD scraper (generic, reusable across Teamtailor and
possibly Freshteam/eRecruit too) and a plain CSS-selector scraper. Given 9
real SA tech roles are sitting right there, this is now the best next
adapter to build once that's confirmed — ahead of eRecruit and Freshteam.

---

## Priority 3: Low-ROI / Deferred

### Custom/Proprietary Platforms
- **Google (proprietary ATS):** Only 5–10 confirmed SA roles; high effort for limited ROI
- **Salesforce (proprietary):** Similar low ROI
- **Amazon (proprietary ATS):** High effort, medium ROI

### Unclear/Unresolved Platforms
- **Capitec, Investec, Vodacom, MTN:** Already added as Workday candidates; will validate live endpoints first
- **Rain, Cell C, Others:** Insufficient public information; defer until direct contact or further research

---

## Recommended Sequencing

1. **Week 1:** SmartRecruiters (highest ROI, clear endpoint) — ✅ done
2. **Week 2:** Freshteam (medium effort, clear endpoint) — ⛔ blocked, needs live page inspection
3. **Week 3:** eRecruit (higher complexity, good ROI) — ⛔ blocked, needs live page inspection
4. **Week 4+:** Ashby (adapter done, employer slug unconfirmed), Teamtailor (blocked, needs API
   token or JSON-LD confirmation), others as resources allow

## Blockers requiring a live browser (25 Sep 2026)

Three items above are stalled on the same root cause: they need someone to actually
load a real careers page in a browser and inspect it, which this sandboxed environment
cannot do (no outbound network to career-site domains, no browser session against the
live internet). Unblocking any of these takes one of:

- Open the page, open dev tools → Network tab, reload, and share what JSON request (if
  any) loads the job list — the URL and one example response is enough to build the
  real adapter confidently instead of guessing.
- Or share view-source / "Copy as cURL" output for the same page.
- Or confirm there's no JSON API and it's server-rendered HTML — a CSS-selector or
  JSON-LD scraper is the right tool then, not a REST client.

Once any of Freshteam, eRecruit, or Teamtailor has that confirmed, the adapter itself
is normally a same-day build following the patterns already in this codebase.

---

## Risk Mitigation

- Each adapter follows existing architecture (Client → Response → Transformer → Snapshot)
- Unit tests use fake responses (no network dependency)
- All adapters marked "experimental" until live validation
- Graceful error handling for API changes or downtime

---

## Success Criteria

- ✓ Each adapter has 10+ comprehensive unit tests
- ✓ All tests passing (100% pass rate maintained)
- ✓ Response validation before field access
- ✓ Proper error handling (JSON, network, API errors)
- ✓ Code follows existing patterns (no new abstractions)

