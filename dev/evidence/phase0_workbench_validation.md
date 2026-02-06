# Phase 0 Evidence: Eve Workbench API Validation

**Date:** 2026-02-06T20:26:00Z  
**Tester:** Automated (agent0)  
**API Endpoint:** https://eveworkbench.com/api/latest/  

---

## Summary

**Overall Result: NO-GO**  

The Eve Workbench API endpoints documented at https://devblog.eveworkbench.com/docs/api/available-endpoints/fit/ do not function as specified. All API calls return HTML (SPA web app) instead of JSON responses.

**Root Cause Identified:** Eve Workbench 2.0 launched in April 2025 with a completely rebuilt backend API. The documented endpoints are from the old system and are no longer valid. See: https://devblog.eveworkbench.com/changelog/eve-workbench-2-0-live/

---

## Test Results by Gate

### G0-1: Anonymous Access

**Status:** ⚠️ PARTIAL — Endpoint responds but returns wrong format  
**Test:** `curl -s https://eveworkbench.com/api/latest/fits?typeId=626`  
**Result:** HTTP 200, but returns HTML instead of JSON  

**Response Headers:**
```
HTTP/2 200
date: Fri, 06 Feb 2026 20:25:37 GMT
server: Kestrel
content-type: text/html; charset=utf-8
```

**Response Body:** HTML (Angular SPA, not JSON)

**Finding:** The endpoint `/api/latest/fits` returns the web application instead of API data. The documented API at `https://api.eveworkbench.com/latest/fits` returns HTTP 404.

---

### G0-2: Inline Metadata

**Status:** ❌ BLOCKED  
**Finding:** Cannot verify response structure — API returns HTML instead of JSON. No `fits` array, no `rating`, `votes`, or `tags` fields observable.

---

### G0-3: Rate Limits

**Status:** ❌ BLOCKED  
**Finding:** Cannot test rate limits without functional JSON endpoint. No `X-RateLimit-*` headers observed in HTML responses.

---

### G0-4: EFT Format Compatible

**Status:** ❌ BLOCKED  
**Finding:** Cannot fetch EFT exports — `/api/latest/fits/{guid}/eft` returns HTML instead of EFT format.

---

### G0-5: Sufficient Volume

**Status:** ❌ BLOCKED  
**Finding:** Cannot assess fit volume without working API.

---

### G0-5b: Quality Distribution

**Status:** ❌ BLOCKED  
**Finding:** Cannot assess quality distribution without working API.

---

### G0-6: ToS Compliance

**Status:** ⏸️ NOT TESTED  
**Finding:** ToS review deferred pending functional API verification.

---

### G0-7: Error Response Handling

**Status:** ⚠️ PARTIAL  
**Observed Errors:**
- `https://api.eveworkbench.com/latest/fits` → HTTP 404 (Not Found)
- `https://eveworkbench.com/api/latest/fits` → HTTP 200 (but returns HTML SPA, not JSON)

---

## Critical Findings

1. **API Base URL Incorrect in Proposal:** The proposal documents `https://api.eveworkbench.com/latest/` but this returns 404.

2. **Alternate Base URL Returns HTML:** `https://eveworkbench.com/api/latest/` returns the Angular SPA, not JSON API responses.

3. **Possible Causes:**
   - API requires authentication header (not documented)
   - API endpoints have changed (documentation outdated)
   - API is deprecated or temporarily disabled
   - CORS/API key requirements not documented

## Authentication Requirements (Documented)

Per the API documentation at https://devblog.eveworkbench.com/docs/api/:

> "To get access you will have to request developer access which allows you to create an application to retrieve the Client ID and API Key."

**This is a significant change from the proposal assumptions:**
- The proposal assumed anonymous access would work (G0-1)
- The new system requires registered developer access with Client ID and API Key
- No documentation on how to request developer access or what the new API endpoints are

## Recommendations

1. **Contact Eve Workbench team** via their Discord (https://discord.gg/dA3kHUv) to:
   - Request developer access for ARIA
   - Obtain new API documentation for v2.0
   - Understand rate limits and terms of service for the new API

2. **Revise Proposal** significantly:
   - Update all API endpoints
   - Add authentication flow (Client ID/API Key)
   - Re-evaluate Phase 0 gates given auth requirements
   - Assess if the integration is still viable with auth barriers

3. **Decision:** **NO-GO for Phase B/C** until:
   - Developer access is obtained
   - New API documentation is available
   - Authentication flow is implemented and tested

---

## Appendix: Test Commands

```bash
# Documented endpoint (404)
curl -s "https://api.eveworkbench.com/latest/fits?typeId=626"

# Alternate endpoint (returns HTML)
curl -s "https://eveworkbench.com/api/latest/fits?typeId=626"

# API documentation (accessible)
curl -s "https://devblog.eveworkbench.com/docs/api/available-endpoints/fit/"
```
