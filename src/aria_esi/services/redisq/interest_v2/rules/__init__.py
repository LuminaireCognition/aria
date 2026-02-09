"""
Rule System for Interest Engine v2.

Rules provide hard overrides for notification decisions:
- always_notify: Bypass scoring, always send notification
- always_ignore: Drop notification regardless of score
- require_all/require_any: Category gates

Built-in rules are always available. Template-based custom rules
are available by default. Expression DSL requires features.rule_dsl.
"""

from .builtin import (
    AllianceMemberVictimRule,
    CorpMemberVictimRule,
    GatecampDetectedRule,
    HighValueRule,
    NpcOnlyRule,
    PodOnlyRule,
    StructureKillRule,
    WarTargetActivityRule,
    WatchlistMatchRule,
)
from .evaluator import RuleEvaluator

__all__ = [
    "AllianceMemberVictimRule",
    "CorpMemberVictimRule",
    "GatecampDetectedRule",
    "HighValueRule",
    "NpcOnlyRule",
    "PodOnlyRule",
    "RuleEvaluator",
    "StructureKillRule",
    "WarTargetActivityRule",
    "WatchlistMatchRule",
]
