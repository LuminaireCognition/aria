# Data Architecture Review
**Date:** 2026-01-31
**Reviewer:** Gemini 3 Pro
**Scope:** `reference/`, `userdata/`, `cache/`, `templates/`, and associated data handling logic.

## Executive Summary
The project maintains a clear separation between application code, static reference data, and user-specific data. The `userdata/` directory structure is well-defined and documented. However, significant risks exist due to the lack of formal schema validation for the central `userdata/config.json` file and the reliance on unstructured Markdown for some reference data. Inconsistencies in cache locations also need addressing before a public release.

## Critical Issues (Must Fix)

### 1. Missing Schema for `userdata/config.json`
The `userdata/config.json` file acts as the central persistent configuration for the application (active pilot, feature flags, context topology).
*   **Problem:** There is no centralized Pydantic model or JSON schema defining this file. It is read ad-hoc across multiple services (e.g., `src/aria_esi/services/redisq/notifications/persona.py`, `src/aria_esi/services/redisq/interest/config.py`).
*   **Risk:** Users can easily misconfigure the application without feedback. Code changes might silently break compatibility with existing config files.
*   **Recommendation:** Implement a `UserConfig` Pydantic model in `src/aria_esi/core/config.py` (or similar) that strictly defines the structure of `userdata/config.json`. Load and validate this file centrally, similar to how `AriaSettings` handles environment variables.

### 2. Inconsistent Cache Location (`reference/pve-intel/cache/`)
While most ephemeral data resides in `cache/` (e.g., `aria.db`, `eos-data/`), the PvE intel module uses a nested cache directory at `reference/pve-intel/cache/`.
*   **Problem:** This mixes source-controlled reference data with ephemeral cache files, complicating `.gitignore` rules and confusing the clear separation of "immutable reference" vs "mutable cache".
*   **Risk:** Users might accidentally commit cache files, or clean routines might miss this directory.
*   **Recommendation:** Move this cache to `{instance_root}/cache/pve-intel/`. Update `src/aria_esi/core/config.py` to expose this path as a standard setting.

## Improvements (Should Fix)

### 1. Unstructured Reference Data (`reference/ships/`)
The project relies on Markdown files in `reference/ships/` for ship progression and some fitting data.
*   **Problem:** Parsing structured data (like fittings or ship stats) from Markdown is brittle and error-prone. Tests (e.g., `tests/test_skill_preflight.py`) reference these files as data sources, suggesting programmatic reliance on this format.
*   **Recommendation:** Accelerate the migration of "legacy fits" to a structured format (YAML/JSON) as proposed in `dev/proposals/ARCHETYPE_FITTINGS_LIBRARY.md`. Treat Markdown files strictly as documentation, not data sources.

### 2. Standardize Validation Logic
Notification profiles use a custom `validate()` method and manual checks in `ProfileLoader`.
*   **Problem:** Custom validation logic is harder to maintain and document than declarative schemas.
*   **Recommendation:** Refactor `NotificationProfile` to fully utilize Pydantic's validation capabilities. This ensures consistency with the proposed `UserConfig` model and allows for automatic generation of schema documentation for users.

### 3. Data Integrity Verification
While `reference/data-sources.json` lists SHA256 hashes for some external resources, there is no evident mechanism to verify the integrity of the internal `reference/` data itself.
*   **Recommendation:** Consider adding a checksum manifest for critical static data files to ensure they haven't been corrupted or tampered with, especially if they are distributed as part of the package.

## Strengths
*   **Clear Data Separation:** The `userdata/` directory clearly isolates user data from application code and reference data.
*   **Migration Path:** The existence of migration logic (legacy `~/.aria/` to `userdata/`) demonstrates foresight for user upgrades.
*   **Environment Configuration:** `AriaSettings` provides a robust, type-safe interface for environment variable configuration.
