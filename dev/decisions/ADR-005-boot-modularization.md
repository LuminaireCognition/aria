# ADR-005: Boot Script Modularization

**Status:** Accepted
**Date:** 2026-01

## Context

ARIA's SessionStart hook performs multiple operations:
- Pilot resolution
- Persona detection
- Configuration validation
- ESI synchronization
- Context assembly
- Welcome display

Initially, this was a monolithic script that was difficult to maintain and debug.

## Decision

Modularize the boot sequence into independent scripts in `.claude/hooks/aria-boot.d/`:

```
aria-boot.sh (orchestrator)
├── pilot-resolution.sh
├── persona-detect.sh
├── boot-operations.sh
└── boot-display.sh
```

### Responsibilities

| Module | Purpose | Exports |
|--------|---------|---------|
| pilot-resolution.sh | Find active pilot | ACTIVE_PILOT_ID, ACTIVE_PILOT_DIR |
| persona-detect.sh | Map faction to AI persona | DETECTED_PERSONA |
| boot-operations.sh | Validation, ESI sync, context | CONFIG_STATUS, ESI_STATUS |
| boot-display.sh | Format welcome message | (stdout) |

### Execution Order

1. Source all modules (load functions)
2. Run pilot resolution (required first)
3. Run persona detection (depends on pilot)
4. Run boot operations in parallel where possible
5. Display formatted output

### Parallel Execution

Independent operations run concurrently:
- ESI sync (background, non-blocking)
- Skill index regeneration (background)
- Validation and context assembly (parallel, waited)

## Consequences

### Positive

- Each module testable independently
- Clear separation of concerns
- Easier debugging (can run single module)
- Parallel execution improves boot time
- New operations easy to add

### Negative

- More files to maintain
- Module dependencies must be documented
- Sourcing overhead (minimal)
- Error handling across modules more complex

## Alternatives Considered

### Monolithic Script
Rejected: Difficult to maintain, test, and extend.

### Python Boot Script
Rejected: Shell is faster for simple orchestration, Python for heavy lifting.

### Separate Hook per Operation
Rejected: Claude Code hooks execute sequentially, no parallelism benefit.

### Makefile-style Dependencies
Rejected: Overkill for 4-5 operations, adds complexity.
