# Gemini 3 Pro Review: ARIA (Adaptive Reasoning & Intelligence Array)

## 1. Executive Summary

ARIA is a sophisticated EVE Online tactical assistant transitioning from a direct-ESI CLI tool to a high-performance Model Context Protocol (MCP) server. The project is well-structured with a clear separation between legacy CLI commands and modern MCP tools.

*   **Current State:** Hybrid architecture (Legacy CLI + Modern MCP).
*   **Key Strength:** The new MCP layer (`src/aria_esi/mcp`) uses local graph algorithms (igraph) for navigation, offering O(1) lookups and custom pathfinding that outperforms the ESI API.
*   **Primary Weakness:** Legacy CLI commands (`src/aria_esi/commands`) rely on slow, synchronous ESI calls and have poor test coverage (~8-35%).
*   **Overall Health:** Good. The core infrastructure is solid, but the legacy CLI needs refactoring to match the quality of the MCP layer.

## 2. Architecture Analysis

The codebase is split into two distinct generations of tooling:

### Legacy Layer (`src/aria_esi/commands/`)
*   **Design:** Direct-to-API synchronous scripts.
*   **Pattern:** Parse args -> Auth -> Call ESI Endpoint -> Format JSON.
*   **Performance:** Bound by network latency and ESI rate limits.
*   **Maintenance:** High. Complex mocking required for tests; logic is duplicated across commands.

### Modern Layer (`src/aria_esi/mcp/`)
*   **Design:** Graph-based, local-first architecture.
*   **Pattern:** Pre-load Universe Graph -> Local Algo (igraph) -> Return Result.
*   **Performance:** Extremely fast (microseconds vs seconds).
*   **Maintenance:** Low. High testability, decoupled from network state.

### Dependency Graph
*   `src/aria_esi/core` is the shared foundation (Auth, Client, Constants).
*   `src/aria_esi/universe` provides the graph builder used by MCP.
*   `src/aria_esi/commands` depends on `core` but ignores `universe/mcp`.
*   `src/aria_esi/mcp` depends on `universe` and `core`.

## 3. Technical Debt & Code Quality

### Critical Issues
1.  **Low Coverage in CLI:** The `commands/` directory averages <30% coverage. Critical modules like `corporation.py` (8%) are effectively untested.
2.  **Logic Duplication:** Route planning logic exists in two places:
    *   `commands/navigation.py`: Calls `GET /route/` (ESI).
    *   `mcp/tools_route.py`: Uses `igraph.get_shortest_paths` (Local).
    *   **Recommendation:** Refactor CLI to use the local `UniverseGraph` for routing, removing the dependency on the ESI `/route/` endpoint.
3.  **Inefficient Data Fetching:** `cmd_activity` fetches *all* system kills/jumps (global dataset) to look up a single system.
4.  **Resource Leaks:** Tests trigger `ResourceWarning: unclosed database`, indicating SQLite connections in `mcp/server.py` or cache layers are not being closed properly.

### Code Hygiene
*   **Type Hinting:** "Phase 1" (baseline) adoption. Many function signatures lack complete type info (`dict` vs `TypedDict`).
*   **Error Handling:** Good custom exception hierarchy (`ESIError`, `CredentialsError`), but some "catch-all" exceptions in older code.
*   **Hardcoded Dependencies:** Direct instantiation of `ESIClient()` inside functions prevents effective unit testing without heavy patching.

## 4. Test Coverage Report

**Overall Coverage:** 42% (Target: 45%)

| Module Group | Coverage | Status | Notes |
|--------------|----------|--------|-------|
| `mcp/tools_*` | >90% | ✅ Excellent | Core logic of the new system is well-tested. |
| `core/*` | ~75% | 🟢 Good | Auth and client logic are stable. |
| `commands/*` | ~25% | 🔴 Critical | CLI interface is fragile. |
| `mcp/market` | <20% | 🟠 Low | Market tools need more attention. |

## 5. Performance Assessment

*   **MCP Routing:** Local graph traversal is O(V+E) and negligible cost. This is a massive win over network calls.
*   **ESI Polling:** The legacy CLI is chatty. Resolving asset names one-by-one (`cmd_corp_assets`) is an N+1 problem waiting to happen on large corps.
*   **Graph Building:** The `universe` builder is efficient but requires a cold-start time to load the pickle/graph.

## 6. Recommendations

### Immediate Actions
1.  **Refactor CLI Navigation:** Update `commands/navigation.py` to use `UniverseGraph` instead of ESI. This unifies logic and boosts performance.
2.  **Fix Resource Leaks:** Audit SQLite usage in tests to close connections and clear warnings.
3.  **Bump Coverage:** Add integration tests for `commands/corporation.py` using cached/mocked ESI responses.

### Long-Term Strategy
1.  **Retire Legacy CLI Logic:** Make the CLI a thin wrapper around MCP tools. e.g., `aria-esi route` should just call `universe_route` tool logic.
2.  **Async CLI:** Move the CLI entry point to async to match the MCP server's capabilities and allow parallel fetching for things like asset name resolution.
3.  **Strict Typing:** Advance to Phase 2/3 of the mypy roadmap defined in `pyproject.toml`.

## 7. Conclusion

ARIA is on the right track. The shift to MCP and local graph processing is architecturally sound and provides a competitive advantage over standard API wrappers. The primary task ahead is bridging the gap between the legacy CLI interface and the powerful new backend.
