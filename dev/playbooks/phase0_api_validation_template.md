# Phase 0 API Validation Playbook (Generic Template)

**Purpose:** Validate third-party API capabilities before committing to integration.

**Use this template for:** Any external API integration where Phase 0 go/no-go gates are required.

---

## Overview

Phase 0 produces an evidence document that gates Phase B/C implementation. Each gate must be evaluated with documented proof before proceeding.

**Output:** `dev/evidence/phase0_<api_name>_validation.md`

---

## Prerequisites

- [ ] API documentation URL identified
- [ ] Test credentials obtained (if auth required)
- [ ] `curl` installed
- [ ] `jq` installed (for JSON APIs)
- [ ] 30-60 minutes uninterrupted

---

## Standard Go/No-Go Gates

### G0-1: Anonymous Access (or Auth Model)

**Question:** Can the API be accessed? What auth is required?

```bash
# Test 1: Anonymous access
curl -s -D /tmp/headers_anon.txt \
  -w "%{http_code}" \
  "https://api.example.com/endpoint"

# Test 2: With auth header (if applicable)
curl -s -H "Authorization: Bearer $TOKEN" \
  -D /tmp/headers_auth.txt \
  -w "%{http_code}" \
  "https://api.example.com/endpoint"
```

**Pass criteria:** HTTP 200, expected response format.

**Fail modes:**
- 401/403 → Auth required but not obtained
- 404 → Endpoint doesn't exist
- HTML instead of JSON → Wrong URL or API deprecated

---

### G0-2: Response Schema

**Question:** Does the response contain the fields we need?

```bash
# List all fields in response
curl -s "https://api.example.com/endpoint" | jq 'keys'

# Check specific field exists
curl -s "https://api.example.com/endpoint" | jq '.required_field // "MISSING"'

# Sample first N items
curl -s "https://api.example.com/endpoint" | jq '.items[:3]'
```

**Evidence to capture:** Annotated JSON showing field names, types, sample values.

---

### G0-3: Rate Limits

**Question:** Can we sustain required request volume?

```bash
# Sequential test (sustained load)
for i in {1..20}; do
  curl -s -o /dev/null \
    -w "%{time_total},%{http_code}\n" \
    "https://api.example.com/endpoint" \
    >> /tmp/rate_sequential.csv
  sleep 3  # Adjust based on expected rate limit
done

# Burst test (peak load)
for i in {1..10}; do
  curl -s -o /dev/null \
    -w "%{time_total},%{http_code}\n" \
    "https://api.example.com/endpoint" \
    >> /tmp/rate_burst.csv &
done
wait

# Check rate limit headers
curl -s -D /tmp/rate_headers.txt \
  "https://api.example.com/endpoint"
grep -i "ratelimit\|x-ratelimit" /tmp/rate_headers.txt || echo "No rate limit headers"
```

**Pass criteria:** Required request rate sustained without 429 errors.

---

### G0-4: Data Quality

**Question:** Is the data usable for our purposes?

```bash
# Volume test - how many results?
curl -s "https://api.example.com/endpoint" | jq '.items | length'

# Quality distribution - range of values?
curl -s "https://api.example.com/endpoint" \
  | jq -r '.items[] | .score_field' \
  | sort -n | uniq -c

# Null/missing data check
curl -s "https://api.example.com/endpoint" \
  | jq '[.items[] | select(.required_field == null)] | length'
```

**Pass criteria:** Sufficient volume, expected value ranges, minimal nulls.

---

### G0-5: Error Handling

**Question:** How does the API handle errors?

```bash
# Invalid parameter
curl -s -w "%{http_code}\n" \
  "https://api.example.com/endpoint?invalid=param"

# Invalid ID
curl -s -w "%{http_code}\n" \
  "https://api.example.com/items/invalid-id"

# Timeout test
curl -s --max-time 5 \
  -w "%{http_code},%{time_total}\n" \
  "https://api.example.com/endpoint"
```

**Evidence needed:** HTTP status codes, error response bodies, timeout behavior.

---

### G0-6: Terms of Service

**Question:** Are our use cases permitted?

```bash
# Fetch ToS
curl -s "https://example.com/terms" -o /tmp/tos.html

# Fetch API policy
curl -s "https://example.com/api-policy" -o /tmp/api_policy.html
```

**Evidence needed:** Quoted excerpts on:
- Caching permitted?
- Rate limits enforced?
- Attribution required?
- Commercial use allowed?

---

## Evidence Document Template

Create `dev/evidence/phase0_<api_name>_validation.md`:

```markdown
# Phase 0 Evidence: [API Name] Validation

**Date:** YYYY-MM-DD
**Tester:** [name]
**API Base URL:** https://api.example.com/
**Documentation:** https://docs.example.com/

## G0-1: Access / Auth

**Test:** `curl https://api.example.com/endpoint`
**Result:** PASS / FAIL
**HTTP Status:** 200 / 401 / 403 / 404
**Response Format:** JSON / XML / HTML / Error

**Evidence:**
```
[response headers]
```

```json
[sample response body]
```

## G0-2: Schema

**Required Fields:**
| Field | Type | Present | Notes |
|-------|------|---------|-------|
| id | string | ✓ | UUID format |
| name | string | ✓ | |
| score | number | ✓ | Range 0-100 |

## G0-3: Rate Limits

**Test:** 20 sequential requests, 10 burst requests
**Result:** PASS / FAIL
**Observed Limit:** X requests/minute
**Headers Present:** Yes / No

## G0-4: Data Quality

**Volume:** N items per query
**Quality Range:** Min X, Max Y, Distribution: [histogram]
**Null Rate:** Z%

## G0-5: Error Handling

| Scenario | Status Code | Response Body |
|----------|-------------|---------------|
| Invalid param | 400 | `{"error": "..."}` |
| Not found | 404 | `{"error": "..."}` |
| Timeout | 000 | (no response) |

## G0-6: ToS Compliance

**Caching:** Allowed / Not Allowed / Ambiguous
**Attribution:** Required / Not Required
**Commercial Use:** Allowed / Not Allowed

**Quotes:**
> "[Relevant ToS excerpt]"

## Summary

| Gate | Status | Blocker? |
|------|--------|----------|
| G0-1 | PASS/FAIL | Yes/No |
| G0-2 | PASS/FAIL | Yes/No |
| G0-3 | PASS/FAIL | Yes/No |
| G0-4 | PASS/FAIL | Yes/No |
| G0-5 | PASS/FAIL | Yes/No |
| G0-6 | PASS/FAIL | Yes/No |

**Overall Decision:** GO / NO-GO

**If NO-GO:**
- Blockers:
- Mitigation options:
- Recommendation:
```

---

## Decision Matrix

| Gate | If FAIL | Action |
|------|---------|--------|
| G0-1 (Access) | Auth model incompatible | Cancel or redesign |
| G0-2 (Schema) | Missing required fields | Revise data model |
| G0-3 (Rate Limits) | Too restrictive | Reduce feature scope |
| G0-4 (Data Quality) | Insufficient/buggy data | Cancel or find alternative source |
| G0-5 (Errors) | Inconsistent handling | Add defensive code |
| G0-6 (ToS) | Use case prohibited | Cancel immediately |

---

## Historical Examples

| API | Date | Result | Reason |
|-----|------|--------|--------|
| Eve Workbench | 2026-02-06 | NO-GO | v2.0 requires developer auth (not user OAuth) |
| [Your API here] | | | |

---

## Next Steps (if GO)

1. Update proposal with validated API details
2. Revise architecture if assumptions changed
3. Proceed to Phase A (protocol/foundation)
4. Schedule Phase B after Phase A complete

## Next Steps (if NO-GO)

1. Document blockers in evidence file
2. Update proposal (mark blocked/cancelled)
3. Consider alternatives:
   - Different API source
   - User-provided data imports
   - Reduced scope (skip this source)
