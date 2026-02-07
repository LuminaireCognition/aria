# Phase 0 Execution Playbook
## Eve Workbench API Validation

**⛔ HISTORICAL DOCUMENT — EFFORT CANCELLED 2026-02-06**

This playbook was created for Eve Workbench API validation but became obsolete when Phase 0 revealed that Eve Workbench v2.0 requires developer authentication (not anonymous access). See `dev/evidence/phase0_workbench_validation.md` for details.

**Preserved as:** Example of Phase 0 API validation methodology. For a reusable template, see `dev/playbooks/phase0_api_validation_template.md`.

---

**Original Goal:** Produce evidence document at `dev/evidence/phase0_workbench_validation.md` with all gates evaluated.

**Prerequisites:**
- `curl` installed
- `jq` installed (for JSON parsing)
- Internet access to api.eveworkbench.com
- 30-60 minutes uninterrupted

---

## Quick Start (5 minutes)

```bash
cd /home/agent0/git/aria
mkdir -p dev/evidence

# Test 1: Anonymous access (G0-1)
curl -s -o /tmp/test_anon.json -w "%{http_code}" \
  "https://api.eveworkbench.com/latest/fits?typeId=626"
# Expected: 200
```

---

## Detailed Test Procedures

### G0-1: Anonymous Access

```bash
# Test unauthenticated request
curl -s -D /tmp/headers_anon.txt \
  "https://api.eveworkbench.com/latest/fits?typeId=626" \
  | jq '.' > /tmp/response_anon.json

# Capture evidence
echo "## G0-1: Anonymous Access" >> dev/evidence/phase0_workbench_validation.md
echo "```" >> dev/evidence/phase0_workbench_validation.md
cat /tmp/headers_anon.txt >> dev/evidence/phase0_workbench_validation.md
echo "```" >> dev/evidence/phase0_workbench_validation.md
echo "" >> dev/evidence/phase0_workbench_validation.md
echo "Response excerpt (first 3 fits):" >> dev/evidence/phase0_workbench_validation.md
echo "```json" >> dev/evidence/phase0_workbench_validation.md
jq '.fits[:3]' /tmp/response_anon.json >> dev/evidence/phase0_workbench_validation.md
echo "```" >> dev/evidence/phase0_workbench_validation.md
```

**Pass criteria:** HTTP 200, JSON response with fits array.

---

### G0-2: Inline Metadata

```bash
# Check what fields are returned in list endpoint
curl -s "https://api.eveworkbench.com/latest/fits?typeId=626" \
  | jq '.fits[0] | keys'

# Expected: guid, name, rating, votes, tags (or similar)
```

**Evidence to capture:** Annotated JSON showing field names and types.

---

### G0-3: Rate Limits

```bash
# Sequential test (20 requests, 1 per 3 seconds = ~1 min)
for i in {1..20}; do
  curl -s -o /dev/null -w "%{time_total},%{http_code},%{size_download}\n" \
    "https://api.eveworkbench.com/latest/fits?typeId=626" \
    >> /tmp/rate_sequential.csv
  sleep 3
done

# Burst test (10 rapid requests)
for i in {1..10}; do
  curl -s -o /dev/null -w "%{time_total},%{http_code}\n" \
    "https://api.eveworkbench.com/latest/fits?typeId=626" \
    >> /tmp/rate_burst.csv &
done
wait

# Check for rate limit headers
curl -s -D /tmp/rate_headers.txt \
  "https://api.eveworkbench.com/latest/fits?typeId=626"
grep -i "ratelimit\|x-ratelimit" /tmp/rate_headers.txt
```

**Pass criteria:** >=10 requests/minute sustained without 429 errors.

---

### G0-4: EFT Format Compatibility

```bash
# Fetch 20-30 diverse fits and test parse_eft()
# First, get list of fit GUIDs
curl -s "https://api.eveworkbench.com/latest/fits?typeId=626" \
  | jq -r '.fits[:30] | .[].guid' > /tmp/fit_guids.txt

# Fetch EFT for each and test parsing
mkdir -p /tmp/eft_test
for guid in $(cat /tmp/fit_guids.txt); do
  curl -s "https://api.eveworkbench.com/latest/fits/${guid}/eft" \
    > "/tmp/eft_test/${guid}.eft"
  
  # TODO: Run through parse_eft() and capture result
  # echo "${guid}: PASS/FAIL" >> /tmp/eft_parse_results.txt
done

# Count results
ls /tmp/eft_test/*.eft | wc -l
```

**Pass criteria:** 20-30 EFTs fetched, parse_eft() passes on majority.

---

### G0-5 & G0-5b: Volume & Quality Distribution

```bash
# Test multiple hulls
for type_id in 626 620 626 620 626; do  # Vexor, Drake samples
  curl -s "https://api.eveworkbench.com/latest/fits?typeId=${type_id}" \
    | jq ".fits | length" >> /tmp/volume_counts.txt
done

# Quality distribution (assuming rating field exists)
curl -s "https://api.eveworkbench.com/latest/fits?typeId=626" \
  | jq -r '.fits[] | .rating' | sort -n | uniq -c > /tmp/quality_dist.txt
```

**Pass criteria:** >=3 rated fits per hull, quality spans spectrum (not all 5-star).

---

### G0-6: ToS Compliance

```bash
# Fetch and review Eve Workbench ToS
curl -s "https://eveworkbench.com/terms" -o /tmp/eveworkbench_tos.html
# Or check API documentation for usage policy
curl -s "https://devblog.eveworkbench.com/docs/api/" -o /tmp/eveworkbench_api_docs.html
```

**Evidence needed:** Quoted ToS excerpts on caching, redistribution, attribution.

---

### G0-7: Error Response Handling

```bash
# Test timeout behavior
curl -s --max-time 1 "https://api.eveworkbench.com/latest/fits?typeId=626" \
  -o /tmp/timeout_test.json -w "%{http_code},%{time_total}\n" > /tmp/timeout_result.txt

# Note: 5xx simulation requires either:
# - Waiting for actual server errors (unreliable)
# - Using a proxy/mock server
# - Documenting observed 5xx from normal usage

# Test with invalid GUID for 404
curl -s -w "%{http_code}\n" \
  "https://api.eveworkbench.com/latest/fits/invalid-guid-12345" \
  > /tmp/invalid_guid_test.txt
```

**Evidence needed:** Documented error responses for 5xx, timeout, 404/410.

---

## Evidence Document Template

Create `dev/evidence/phase0_workbench_validation.md`:

```markdown
# Phase 0 Evidence: Eve Workbench API Validation

**Date:** 2026-02-XX
**Tester:** [name]
**API Endpoint:** https://api.eveworkbench.com/latest

## G0-1: Anonymous Access

**Test:** `curl https://api.eveworkbench.com/latest/fits?typeId=626`
**Result:** PASS / FAIL
**Evidence:**
```
[response headers]
```

## G0-2: Inline Metadata
...

## Summary

| Gate | Status | Notes |
|------|--------|-------|
| G0-1 | PASS/FAIL | |
| G0-2 | PASS/FAIL | |
| ... | ... | |

**Overall:** GO / NO-GO
```

---

## Cancellation Reason

**2026-02-06:** Phase 0 execution revealed Eve Workbench v2.0 requires developer registration and API Key authentication. This is incompatible with ARIA's CLI tool distribution model where users expect low-friction setup (like ESI OAuth). The integration effort was cancelled.

**References:**
- Evidence: `dev/evidence/phase0_workbench_validation.md`
- Proposal (marked blocked): `dev/proposals/UNIFIED_FIT_SOURCES_PROPOSAL.md`
- API docs: https://devblog.eveworkbench.com/docs/api/
- v2.0 changelog: https://devblog.eveworkbench.com/changelog/eve-workbench-2-0-live/

---

## Next Steps (Historical)

~~1. Run the tests above~~
~~2. Fill in the evidence document~~
~~3. Make go/no-go decision based on gate results~~
~~4. If GO → proceed to Phase A implementation~~
~~5. If NO-GO → revise proposal based on findings~~

**Estimated time:** ~~2-4 hours for complete validation~~ **N/A — Effort cancelled**
