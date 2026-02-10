# Prompt Review Calibration Report

**Status:** Pending — blocked until v1 prompts are merged to `main`
**Parent proposal:** `dev/proposals/PROMPT_LIBRARY_REVIEW_COVERAGE_PROPOSAL.md`

## Purpose

The Definition of Done for BLK-015 requires calibration evidence demonstrating that
the prompt review pipeline produces actionable, accurate results at acceptable
false-positive/negative rates. This report will be populated after the v1 prompt
library is live on `main` and real CI runs generate sufficient sample data.

## Pending Deliverables

### 1. Calibration Sample

- [ ] Collect 10+ real PR review runs across varied change types
- [ ] Record prompt selections, tier assignments, and gate decisions
- [ ] Annotate each with ground-truth expected outcome

### 2. Gate Output Validation

- [ ] Verify aggregate gate decisions match human reviewer consensus
- [ ] Confirm orchestrator coverage checks detect real gaps
- [ ] Validate waiver flow correctly suppresses acknowledged issues

### 3. Severity Threshold Alignment

- [ ] Review severity distribution across sample runs
- [ ] Confirm `critical`/`high` thresholds align with merge-blocking intent
- [ ] Adjust scoring rubric weights if needed

### 4. False Positive / Negative Analysis

- [ ] Measure false positive rate (findings that are not real issues)
- [ ] Measure false negative rate (real issues missed by prompts)
- [ ] Document acceptable thresholds and current performance

## Methodology

Once unblocked:

1. Merge `feature/prompt-library-review` to `main`
2. Run prompt review pipeline on 10+ subsequent PRs
3. Manually review each pipeline output against human assessment
4. Populate sections above with quantitative results
5. If thresholds are not met, iterate on prompt content and re-calibrate

## Timeline

Calibration begins after v1 merge. Target completion: 4 weeks post-merge.
