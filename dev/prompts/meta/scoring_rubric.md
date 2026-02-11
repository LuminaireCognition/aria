---
type: reference
category: meta
description: Shared severity and confidence scoring definitions used by all review prompts.
when_to_use: Reference this rubric when calibrating severity and confidence levels across reviews.
related_prompts: []
---

# Shared Severity and Confidence Scoring Rubric

This document defines the canonical severity and confidence scales used by all review prompts, ensuring consistent grading across the prompt library.

## Severity Definitions

### Critical

An issue that, if shipped, would cause data loss, security breach, or service unavailability with no workaround. Requires immediate remediation before merge.

### High

An issue that meaningfully degrades correctness, security posture, or reliability. A workaround may exist but the defect should not ship without an active waiver and follow-up issue.

### Medium

An issue that represents a maintainability risk, a deviation from project standards, or a minor correctness concern. Should be addressed in the current cycle but is not merge-blocking.

### Low

A minor style, naming, or documentation issue. Address opportunistically.

### Info

An observation or suggestion with no immediate action required. Useful for tracking patterns or informing future work.

## Confidence Definitions

### High

The finding is supported by direct evidence from the repository (file paths, line references, test output, schema validation). False-positive probability is low.

### Medium

The finding is supported by indirect evidence or pattern matching. Manual verification is recommended before acting.

### Low

The finding is based on heuristic or structural inference. Further investigation is required to confirm.
