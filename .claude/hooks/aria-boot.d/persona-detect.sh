#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# ARIA Boot Module: Persona Detection
# ═══════════════════════════════════════════════════════════════════
# Maps pilot faction to AI persona name and subtitle.
#
# Exports:
#   - FACTION, AI_PERSONA, AI_SUBTITLE
#   - detect_persona() - Main entry point
#
# Requires:
#   - PILOT_PROFILE (set by pilot-resolution.sh)
# ═══════════════════════════════════════════════════════════════════

# State variables (exported for display module)
FACTION=""
AI_PERSONA="ARIA"
AI_SUBTITLE="Tactical Assistant"

# ───────────────────────────────────────────────────────────────────
# Persona Detection
# ───────────────────────────────────────────────────────────────────

detect_persona() {
    if [ -f "$PILOT_PROFILE" ]; then
        # Extract Primary Faction value (handles various formats)
        FACTION=$(grep -i "Primary Faction:" "$PILOT_PROFILE" 2>/dev/null | head -1 | sed 's/.*:\*\* *//' | sed 's/^- \*\*[^:]*:\*\* *//' | tr -d '[:space:]' | tr '[:lower:]' '[:upper:]')
    fi

    # Set persona based on faction
    case "$FACTION" in
        "GALLENTE"|"GALLENTE"*)
            AI_PERSONA="ARIA Mk.IV"
            AI_SUBTITLE="Gallente Federation Tactical Assistant"
            ;;
        "CALDARI"|"CALDARI"*)
            AI_PERSONA="AURA-C"
            AI_SUBTITLE="Caldari State Tactical Interface"
            ;;
        "MINMATAR"|"MINMATAR"*)
            AI_PERSONA="VIND"
            AI_SUBTITLE="Republic Fleet Tactical Core"
            ;;
        "AMARR"|"AMARR"*)
            AI_PERSONA="THRONE"
            AI_SUBTITLE="Imperial Navy Guidance Array"
            ;;
        "PIRATE"|"ANGEL_CARTEL"|"SERPENTIS"|"GURISTAS"|"BLOOD_RAIDERS"|"SANSHAS_NATION")
            AI_PERSONA="PARIA"
            AI_SUBTITLE="Unlicensed Tactical Intelligence Array"
            ;;
        *)
            AI_PERSONA="ARIA"
            AI_SUBTITLE="Tactical Assistant"
            ;;
    esac
}
