# Phase 2b: New Provider Adapter Roadmap

**Status:** SmartRecruiters and Ashby adapters shipped. Freshteam, eRecruit and
Teamtailor deprioritized (25 Sep 2026) — blocked on live endpoint inspection this
sandbox can't perform; revisit if/when that information becomes available.  
**Date:** 25 September 2026

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

### Freshteam (by Freshworks) — ⛔ Blocked, not started
**Employers:** Peach Payments (primary), 1–2 others  
**Confidence:** Medium  
**SA Presence:** Peach Payments confirmed at `peachpayments.freshteam.com/jobs`  
**Adapter Complexity:** Medium (REST API, Freshworks ecosystem)  
**Projected Jobs:** 30–50  

**Blocker (25 Sep 2026):** Freshteam's authenticated recruitment API
(`developers.freshteam.com`) is documented, but it's for internal HR management, not
public candidate-facing career sites, and requires an API key we don't have. Whether
Peach Payments' public careers page is backed by an unauthenticated JSON endpoint is
unconfirmed — this has to be discovered by loading the real page and inspecting its
network requests, which needs live browser access this environment doesn't have.
Building a client against a guessed endpoint shape risks silently shipping wrong or
broken parsing. **Needs:** someone with a browser to open
`peachpayments.freshteam.com/jobs`, open dev tools → Network tab, and capture the
request URL + response shape the page uses to load its job list, or confirm there is
none (i.e., it's server-rendered HTML, in which case a CSS-selector scraper is the
right approach instead).

---

### eRecruit — ⛔ Blocked, not started
**Employers:** Momentum Metropolitan (primary)  
**Confidence:** Low–Medium  
**SA Presence:** Momentum Metropolitan at `momentummetropolitan.erecruit.co`  
**Adapter Complexity:** Medium–High (custom ATS, potentially HTML scraping)  
**Projected Jobs:** 20–40  

**Blocker (25 Sep 2026):** eRecruit is a smaller, custom ATS with no publicly
documented API. Same constraint as Freshteam — this needs live inspection of
`momentummetropolitan.erecruit.co` to determine whether it's JSON-backed or requires
HTML parsing, which this sandboxed environment cannot do (no live browser/network
access to the real site). **Needs:** the same manual inspection as Freshteam above.

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

### Teamtailor — ⛔ Blocked, not started
**Employer:** Yoco (fintech)  
**Confidence:** Medium–High (public Teamtailor board: `yoco.teamtailor.com`)  
**Adapter Complexity:** Medium  
**Projected Jobs:** 15–25  

**Blocker (25 Sep 2026):** Teamtailor's general REST API requires a per-company API
token for all endpoints, including reading job listings — that's a structural
mismatch with this project's public/employer-direct/unauthenticated-sources rule, not
something a code fix works around. Individual Teamtailor-hosted career pages (like
`yoco.teamtailor.com`) may separately expose job data via `JobPosting` structured
data (schema.org JSON-LD) embedded in the page HTML for SEO, which this project
already knows how to parse (see the WP Job Manager adapter). But confirming that
requires loading the real page, which this sandbox can't do. **Needs:** either (a) an
API token from Yoco (out of scope for a public-sources project), or (b) live
confirmation that the career page embeds `JobPosting` JSON-LD, in which case a
generic JSON-LD scraper — reusable across Teamtailor, and possibly Freshteam/eRecruit
too — becomes the highest-leverage next adapter to build.

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

