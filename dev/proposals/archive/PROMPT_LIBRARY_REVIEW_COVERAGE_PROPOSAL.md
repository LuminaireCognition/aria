# Prompt Library Review Coverage Proposal

> **Superseded** (2026-02-10). The CI automation pipeline described here (matcher, aggregator, orchestrator, waivers, 8-job workflow) was not adopted.

## What Was Retained

The standalone review prompts were kept as a developer toolkit in [`dev/prompts/`](../../prompts/README.md). They are invoked manually by contributors, not by CI.

## Why It Was Superseded

The automation layer added significant complexity (matcher DSL, waiver governance, multi-job orchestration) without clear ROI for the project's current scale. The prompts themselves proved valuable on their own.
