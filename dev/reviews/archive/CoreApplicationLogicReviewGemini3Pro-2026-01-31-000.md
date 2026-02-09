# Core Application Logic Review

**Reviewer:** Gemini 3 Pro
**Date:** 2026-02-01
**Scope:** `src/aria_esi/` (Services, Commands, Core, Fitting, Archetypes)

## Summary

The core application logic demonstrates a mature understanding of Python patterns, utilizing `dataclasses` for data modeling and decorators for cross-cutting concerns like retries. The architecture is modular, though some areas (fitting/skills) exhibit tight coupling to data sources. Error handling is robust, particularly in the network layer.

## 1. Code Quality

*   **Strengths:**
    *   **Data Modeling:** Extensive use of `dataclasses` in `src/aria_esi/archetypes/models.py` provides clear, typed structures for complex game data (fittings, hulls, stats).
    *   **Conventions:** Consistent naming and structure across modules. Use of `TYPE_CHECKING` blocks prevents circular import runtime errors while supporting static analysis.
*   **Improvements Needed:**
    *   **Complexity:** As noted in previous reviews, `ArbitrageEngine._find_scope_opportunities` is overly complex and ripe for decomposition.
    *   **Boilerplate:** The `to_dict` methods in `models.py` are repetitive.
        *   *Recommendation:* Since `pydantic` is a project dependency, migrating these data models to `pydantic.BaseModel` would automate serialization/validation and reduce boilerplate significantly.

## 2. Error Handling

*   **Strengths:**
    *   **Resilience:** `src/aria_esi/core/retry.py` implements a sophisticated retry mechanism with support for `Retry-After` headers and exponential backoff.
    *   **Fallback:** The retry module gracefully degrades if `tenacity` is not installed, ensuring the core functionality works (albeit less resiliently) in minimal environments.
    *   **Classification:** `classify_http_error` correctly distinguishes between transient (retryable) and permanent (non-retryable) errors.
*   **Improvements Needed:**
    *   **Silent Failures:** As noted in the Client review, some `*_safe` methods swallow exceptions too aggressively. Ensure these are only used where data is truly optional.

## 3. Architecture

*   **Strengths:**
    *   **Separation of Concerns:** `src/aria_esi/fitting/skills.py` separates skill fetching logic from the fitting calculation logic.
    *   **Abstraction:** The `archetypes` module abstracts the underlying YAML storage format into Python objects, insulating the rest of the app from file format changes.
*   **Improvements Needed:**
    *   **Global State:** `src/aria_esi/fitting/skills.py` uses a module-level global `_skill_requirements` cache. While efficient for a CLI, this singleton pattern makes unit testing harder (requires explicit reset fixtures) and could be problematic if the app moves to a persistent server model.
        *   *Recommendation:* Encapsulate this cache within a `SkillManager` class that can be instantiated per request or session.

## 4. Type Safety

*   **Strengths:**
    *   **Definitions:** `archetypes/models.py` makes good use of `Literal` types (e.g., `SkillTier`, `ShipClass`) to enforce domain constraints at the type checker level.
*   **Improvements Needed:**
    *   **Generics:** The ESI client's return types are often loose (`Any` or `dict`). Introducing Generics (`T = TypeVar("T")`) for the `get` methods would allow callers to specify the expected return model, improving type safety at the call site.

## Action Items

1.  **Refactor `ArbitrageEngine`:** Decompose the large method to improve readability and testability.
2.  **Migrate to Pydantic:** Evaluate converting `archetypes/models.py` to Pydantic models to reduce code volume and increase validation robustness.
3.  **Encapsulate State:** Refactor the global skill cache in `skills.py` into a proper class-based manager.
4.  **Audit `_safe` Methods:** Review usages of `get_safe` in the client to ensure critical errors aren't being hidden.
