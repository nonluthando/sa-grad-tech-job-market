# Phase 2b: New Provider Adapter Roadmap

**Status:** Assessment and planning  
**Date:** 25 September 2026

## Overview

Phase 2a activated 13 sources across existing adapters (Workday, SuccessFactors, Greenhouse, Lever, Oracle HCM, Breezy HR, Workable). Phase 2b identifies and prioritizes new provider adapters needed for remaining Phase 2 employers.

---

## Priority 1: High-ROI Adapters (3–4 employers each)

### SmartRecruiters
**Employers:** Standard Bank (primary), 2–3 others  
**Confidence:** High  
**SA Presence:** Standard Bank confirmed at `careers.smartrecruiters.com/StandardBankGroup`  
**Adapter Complexity:** Medium (similar pagination/structure to Lever)  
**Projected Jobs:** 150–200  
**Implementation Effort:** 30–40 hours (new client, transformer, tests)

**Next Steps:**
1. Reverse-engineer SmartRecruiters public API (likely `api.smartrecruiters.com/v1/`)
2. Implement `src/ingestion/smartrecruiters.py` with job list endpoint
3. Implement `src/transformation/smartrecruiters.py` field mapper
4. Add 5–10 tests for pagination, error handling, response validation
5. Add configuration to `src/ingestion/config.py`

---

### Freshteam (by Freshworks)
**Employers:** Peach Payments (primary), 1–2 others  
**Confidence:** Medium  
**SA Presence:** Peach Payments confirmed at `peachpayments.freshteam.com/jobs`  
**Adapter Complexity:** Medium (REST API, Freshworks ecosystem)  
**Projected Jobs:** 30–50  
**Implementation Effort:** 25–35 hours

**Next Steps:**
1. Inspect Peach Payments Freshteam careers API (likely `api.freshteam.com/api/`)
2. Implement `src/ingestion/freshteam.py`
3. Implement transformer
4. Add tests (pagination, field mapping)
5. Update configuration

---

### eRecruit
**Employers:** Momentum Metropolitan (primary)  
**Confidence:** Low–Medium  
**SA Presence:** Momentum Metropolitan at `momentummetropolitan.erecruit.co`  
**Adapter Complexity:** Medium–High (custom ATS, potentially HTML scraping)  
**Projected Jobs:** 20–40  
**Implementation Effort:** 40–60 hours (may require HTML parsing if no JSON API)

**Next Steps:**
1. Inspect Momentum career page for API or HTML structure
2. Determine if eRecruit exposes a public JSON API or requires parsing
3. If API: implement REST client (similar to other adapters)
4. If HTML: implement targeted CSS selector extraction
5. Add 10+ tests for edge cases

---

## Priority 2: Medium-ROI Adapters (1–2 employers each)

### Ashby
**Employer:** Andela (South Africa-hiring contractor platform)  
**Confidence:** Medium  
**Adapter Complexity:** Medium  
**Projected Jobs:** 20–30  
**Effort:** 25–35 hours

### Teamtailor
**Employer:** Yoco (fintech)  
**Confidence:** Medium–High (public Teamtailor board: `yoco.teamtailor.com`)  
**Adapter Complexity:** Medium  
**Projected Jobs:** 15–25  
**Effort:** 25–35 hours

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

1. **Week 1:** SmartRecruiters (highest ROI, clear endpoint)
2. **Week 2:** Freshteam (medium effort, clear endpoint)
3. **Week 3:** eRecruit (higher complexity, good ROI)
4. **Week 4+:** Ashby, Teamtailor, others as resources allow

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

