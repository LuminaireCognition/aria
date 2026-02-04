# Documentation & User Experience Review

**Reviewer:** Gemini 3 Pro
**Date:** 2026-01-31
**Scope:** `docs/`, `README.md`, `CLAUDE.md`, `personas/`, `dev/`

## Executive Summary

The documentation and user experience of ARIA are exceptional for an open-source project. The project provides a multi-layered documentation strategy (TLDR for quick info, README for overview, Architecture for deep dives) and a highly polished "Ship-Board AI" persona system that creates a unique and immersive user experience. The onboarding process is clear and assisted by a setup wizard.

The primary risks before public release are the **documentation density** (which may overwhelm users) and the **token overhead** of the extremely detailed `CLAUDE.md` file.

## Strengths (Brief)

*   **Exceptional Onboarding:** The `./aria-init` wizard combined with `FIRST_RUN.md` makes for a very low barrier to entry.
*   **Persona Immersiveness:** The persona system (`personas/`) is architecturally clean, well-documented, and provides high-quality cultural framing that enhances the EVE Online theme.
*   **Technical Depth:** `CLAUDE.md` and `docs/ARCHITECTURE.md` provide the AI and developers with precise instructions and a clear mental model of the system.
*   **Security Focus:** Clear guardrails for untrusted data and sensitive files are built directly into the AI's core instructions.

## Critical Findings & Recommendations

### 1. Documentation Overload
**Risk:** Medium
**Observation:** There are nearly 30 files in the `docs/` directory. While comprehensive, a new user may find it difficult to know which documents are essential vs. reference.
**Recommendation:**
*   **Consolidate Reference Docs:** Group lower-level technical docs (e.g., `DATA_VERIFICATION.md`, `CONTEXT_POLICY.md`) into a `docs/reference/` sub-directory.
*   **User vs. Dev Split:** Clearly separate user-facing guides from developer-focused design docs in the documentation index.

### 2. CLAUDE.md Token Efficiency
**Risk:** Medium
**Observation:** `CLAUDE.md` is a massive file containing complex instructions for tool usage, security, and persona loading. As this is the "system prompt" for the AI, it will consume a significant portion of the token window in every session.
**Recommendation:**
*   **Prune Redundancy:** Some instructions in `CLAUDE.md` repeat what is in the MCP tool docstrings. Audit for redundancy.
*   **Modularize Instructions:** Consider if some instructions (like PI production chains) can be moved to specific tool docstrings or external reference files that the AI only reads when needed.

### 3. Interface Disambiguation
**Risk:** Low
**Observation:** The documentation mentions both `aria-esi` (CLI) and MCP dispatchers. While `CLAUDE.md` has a "Fallback Behavior" section, a user might be confused about whether they should be using the CLI directly or talking to the AI.
**Recommendation:**
*   **Highlight "AI-First" Workflow:** The `README.md` should more strongly emphasize that talking to ARIA (via MCP) is the primary intended interface, with the CLI being a secondary tool for power users or scripts.

### 4. Missing Contribution Guidelines
**Risk:** Low
**Observation:** While the project is MIT licensed and encourages forking, there is no formal `CONTRIBUTING.md` or section on how to contribute new personas/skills back to the main project.
**Recommendation:**
*   **Create `CONTRIBUTING.md`:** Provide a template for new skills and personas to ensure they meet the project's quality and security standards.

### 5. "Draft" status of Dev Docs
**Risk:** Low
**Observation:** `dev/DESIGN.md` is titled "Implementation Proposal" and reads like an initial pitch. 
**Recommendation:**
*   **Finalize Design Docs:** Update `dev/DESIGN.md` to reflect the *actual* implemented state rather than a proposal.

## Action Plan
1.  **Reorganize `docs/`:** Move technical specifications to a `reference/` subfolder.
2.  **Optimize `CLAUDE.md`:** Review for token-saving opportunities without compromising safety or persona quality.
3.  **Finalize `CONTRIBUTING.md`:** Add guidelines for community contributions.
