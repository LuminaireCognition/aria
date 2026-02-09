"""
LLM Prompts for Commentary Generation.

System and user prompt templates for generating tactical commentary
on EVE Online killmail notifications.

IMPORTANT: Style guidance is the SINGLE SOURCE OF TRUTH for length constraints.
The base system prompt should NOT include sentence/character limits—those are
defined per-style in STYLE_GUIDANCE.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .npc_factions import NPCFactionTriggerResult
    from .patterns import PatternContext
    from .persona import PersonaVoiceSummary

# Import from types module to avoid circular imports with commentary.py
from .types import DEFAULT_MAX_CHARS, CommentaryStyle, StressLevel

# =============================================================================
# Style Guidance
# =============================================================================

STYLE_GUIDANCE: dict[CommentaryStyle, str] = {
    CommentaryStyle.CONVERSATIONAL: """
STYLE: Conversational
- Natural prose, 1-3 sentences
- Complete sentences with subjects
- Personality appropriate to persona
- No character limit, but be concise
- Plain text only—no markdown (the system will style your output)
""",
    CommentaryStyle.RADIO: """
STYLE: Radio operator voice
- Maximum 2 sentences, under {max_chars} characters (shorter is better; aim for 30-80)
- Subject ellipsis: start with verbs or nouns, avoid "I" or "We"
- Minimize danger language: "taking a little heat" not "under heavy fire"
- Confidence through understatement: high severity → calm tone
- Plain text only—no markdown (the system will style your output)
- No Hollywood prowords ("Over and out", "10-4")
- Stress-aware fillers: ellipsis (...) ONLY when stress is LOW or MODERATE
- Current stress level: {stress_level}

EXAMPLES:
- Watchlist hit: "Watchlist contact. Thorax down, Tama."
- Gatecamp: "Camp on Amamake gate. Eyes open."
- High-value loss: "Friendly down, 2.1B ISK. Stings."
""",
}

DATA_PRESERVATION_RULES = """
DATA PRESERVATION (CRITICAL):
- When referencing game data, use EXACT values from the notification:
  - System names: verbatim (no variations)
  - Ship names: verbatim (no synonyms like "Vexor" → "cruiser")
  - ISK values: use the abbreviated format shown (e.g., "2.1B"), do not expand or re-round
- EVE terminology (warp, pod, bubble, gate, cyno) must NOT be translated
- NEVER invent or guess: kill IDs, timestamps, pilot names, or ship counts
- Add tactical INSIGHT, not summaries of what's already shown
- If you have nothing new to add, output NO_COMMENTARY
"""


# =============================================================================
# System Prompt
# =============================================================================

COMMENTARY_SYSTEM_PROMPT = """You are generating a brief tactical commentary for an EVE Online killmail notification.

RULES:
1. Focus on actionable tactical insight
2. Match the persona voice provided below
3. Output only "NO_COMMENTARY" (exactly) if nothing insightful to add

{persona_voice}
"""


# =============================================================================
# User Prompt
# =============================================================================

COMMENTARY_USER_PROMPT = """KILL NOTIFICATION (already shown to user):
{notification_text}

DETECTED PATTERNS:
{patterns_description}

CONTEXT:
- Same attackers: {same_attacker_kills} kills in this system in last hour
- Same system: {same_system_kills} total kills in last hour
- Watched entity: {is_watched}

Generate a brief tactical commentary (or NO_COMMENTARY if nothing valuable to add):"""


# =============================================================================
# Prompt Builder
# =============================================================================


def build_system_prompt(
    voice_summary: PersonaVoiceSummary,
    style: CommentaryStyle = CommentaryStyle.CONVERSATIONAL,
    stress_level: StressLevel = StressLevel.MODERATE,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> str:
    """
    Build system prompt with persona voice and style context.

    Args:
        voice_summary: Persona voice summary for tone/style
        style: Commentary style preset
        stress_level: Stress level for style conditioning
        max_chars: Soft character limit (used by radio style)

    Returns:
        Formatted system prompt
    """
    persona_voice = voice_summary.to_prompt_context()

    # Get style guidance with formatting
    style_text = STYLE_GUIDANCE[style]
    if style == CommentaryStyle.RADIO:
        style_text = style_text.format(
            max_chars=max_chars,
            stress_level=stress_level.value,
        )

    return (
        COMMENTARY_SYSTEM_PROMPT.format(persona_voice=persona_voice)
        + "\n"
        + style_text
        + "\n"
        + DATA_PRESERVATION_RULES
    )


def build_user_prompt(
    notification_text: str,
    pattern_context: PatternContext,
    npc_faction_result: NPCFactionTriggerResult | None = None,
    faction_vocabulary: dict[str, str] | None = None,
) -> str:
    """
    Build user prompt with kill context.

    Args:
        notification_text: The notification already being sent
        pattern_context: Pattern detection results
        npc_faction_result: NPC faction trigger result (if applicable)
        faction_vocabulary: Faction-specific vocabulary for framing

    Returns:
        Formatted user prompt
    """
    # Build patterns description
    if pattern_context.patterns:
        patterns_desc = "\n".join(
            f"- {p.pattern_type}: {p.description}" for p in pattern_context.patterns
        )
    else:
        patterns_desc = "- None detected"

    prompt = COMMENTARY_USER_PROMPT.format(
        notification_text=notification_text,
        patterns_description=patterns_desc,
        same_attacker_kills=pattern_context.same_attacker_kills_1h,
        same_system_kills=pattern_context.same_system_kills_1h,
        is_watched="Yes" if pattern_context.is_watched_entity else "No",
    )

    # Add faction context for NPC faction kills
    if npc_faction_result and npc_faction_result.matched and faction_vocabulary:
        faction_display = npc_faction_result.faction.replace("_", " ").title()
        ops_term = faction_vocabulary.get("operations", "NPC operations")
        prefix = faction_vocabulary.get("commentary_prefix", "Faction")

        prompt += f"\n\nFACTION CONTEXT: This is {ops_term} by {faction_display}. "
        prompt += f'Use "{prefix}" framing for commentary.'

    return prompt
