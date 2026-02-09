from __future__ import annotations

from dataclasses import dataclass

TIER_PRECEDENCE = {"gate": 0, "deep_dive": 1, "foundation": 2, "fallback": 3}
SEVERITY_RANK = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1, "Info": 0}


@dataclass(frozen=True)
class PromptSelection:
    prompt_id: str
    prompt_instance_id: str
    prompt_path: str
    tier: str
    selection_reason: str
    selection_trace: list[dict]


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str


@dataclass(frozen=True)
class AggregateResult:
    gate_decision: str
    unresolved_high_count: int
    requires_high_waiver_check: bool
    normalized: dict
    issues: list[ValidationIssue]


@dataclass(frozen=True)
class WaiverValidationResult:
    ok: bool
    issues: list[ValidationIssue]
