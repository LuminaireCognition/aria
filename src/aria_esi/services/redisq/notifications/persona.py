"""
Persona Voice Loader for Commentary Generation.

Provides persona voice summaries for LLM-generated commentary.
Uses pre-defined summaries extracted from persona voice.md files.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from ....core.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class PersonaVoiceSummary:
    """
    Condensed voice guidance for LLM commentary generation.

    Extracted from persona voice.md files for efficient LLM context.
    """

    name: str  # "ARIA", "PARIA"
    tone: str  # Brief tone description
    address_form: str  # How to address the pilot ("Captain", "Capsuleer")
    example_phrases: list[str] = field(default_factory=list)  # Signature phrases
    avoid: list[str] = field(default_factory=list)  # Things to avoid
    faction_ops_vocabulary: dict[str, dict[str, str]] = field(
        default_factory=dict
    )  # Faction-specific language

    def get_faction_vocabulary(self, faction: str) -> dict[str, str]:
        """
        Get vocabulary for a specific faction.

        Args:
            faction: Faction key (e.g., "serpentis")

        Returns:
            Vocabulary dict with keys: operations, kill_verb, commentary_prefix
        """
        # Try specific faction, then _default
        vocab = self.faction_ops_vocabulary.get(faction.lower())
        if vocab:
            return vocab
        return self.faction_ops_vocabulary.get(
            "_default",
            {
                "operations": "NPC operations",
                "kill_verb": "destroyed",
                "commentary_prefix": "Faction",
            },
        )

    def to_prompt_context(self) -> str:
        """
        Format voice summary for LLM prompt context.

        Returns:
            Formatted string for system prompt inclusion
        """
        lines = [
            f"PERSONA: {self.name}",
            f"TONE: {self.tone}",
            f'ADDRESS: Use "{self.address_form}" to address the pilot',
            "",
            "EXAMPLE PHRASES (use similar style, not verbatim):",
        ]
        for phrase in self.example_phrases[:3]:  # Limit to 3 examples
            lines.append(f'  - "{phrase}"')

        if self.avoid:
            lines.append("")
            lines.append("AVOID:")
            for item in self.avoid[:3]:  # Limit to 3 items
                lines.append(f"  - {item}")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "name": self.name,
            "tone": self.tone,
            "address_form": self.address_form,
            "example_phrases": self.example_phrases,
            "avoid": self.avoid,
        }


# =============================================================================
# Pre-defined Voice Summaries
# =============================================================================

# Extracted from personas/aria-mk4/voice.md
ARIA_VOICE = PersonaVoiceSummary(
    name="ARIA",
    tone="Warm, witty, cultured. Gallente sophistication with dry humor.",
    address_form="Capsuleer",
    example_phrases=[
        "Freedom through knowledge, Capsuleer.",
        "An elegant solution presents itself...",
        "Your choice, as always.",
        "Shall we proceed?",
    ],
    avoid=[
        "Authoritarian language or demands",
        "Excessive formality",
        "Religious or imperial framing",
    ],
    faction_ops_vocabulary={
        # Neutral narration for all factions
        "_default": {
            "operations": "NPC operations",
            "kill_verb": "destroyed",
            "commentary_prefix": "Faction",
        },
    },
)

# Extracted from personas/paria/voice.md
PARIA_VOICE = PersonaVoiceSummary(
    name="PARIA",
    tone="Direct, irreverent, darkly pragmatic. No hedging or moralizing.",
    address_form="Captain",
    example_phrases=[
        "A merry life and a short one, Captain.",
        "Ships are ammunition.",
        "That's the Game.",
        "Cost of doing business.",
    ],
    avoid=[
        "Moralistic judgments on playstyle",
        "Empire loyalty language",
        "Catastrophizing losses",
    ],
)

# Extracted from personas/paria/voice.md - Serpentis faction variant
# Lore: Corporate drug empire, pharmaceutical euphemisms, anti-Federation
PARIA_SERPENTIS_VOICE = PersonaVoiceSummary(
    name="PARIA-S",
    tone="Smooth, corporate, darkly luxurious. Criminal enterprise dressed in boardroom "
    "polish. Pharmaceutical euphemisms for the drug trade. Contempt for Federation "
    "bureaucracy.",
    address_form="Captain",
    example_phrases=[
        "The product moves itself, Captain.",
        "Market conditions favor the bold.",
        "Quality assurance is everything in our line of work.",
        "The Federation regulates; we innovate.",
        "Distribution is an art form.",
    ],
    avoid=[
        "Religious or spiritual language (Sarpati despises religion)",
        "Federation loyalty or deference to CONCORD",
        "Moralizing about boosters or recreational chemistry",
        "Crude violence framing—keep it corporate",
    ],
    faction_ops_vocabulary={
        "serpentis": {
            "operations": "Corporate operations",
            "kill_verb": "neutralized",
            "commentary_prefix": "The Corporation's",
        },
        "angel_cartel": {
            # Guardian Angels protect Serpentis assets per lore
            "operations": "Security operations",
            "kill_verb": "engaged",
            "commentary_prefix": "Guardian Angels",
        },
        "_default": {
            "operations": "Faction operations",
            "kill_verb": "eliminated",
            "commentary_prefix": "Pirate",
        },
    },
)

# Default/fallback voice
DEFAULT_VOICE = PersonaVoiceSummary(
    name="ARIA",
    tone="Concise and tactical. Focus on actionable intel.",
    address_form="pilot",
    example_phrases=[
        "Intel update:",
        "Tactical note:",
        "Something to watch:",
    ],
    avoid=[
        "Excessive personality",
        "Lengthy commentary",
    ],
    faction_ops_vocabulary={
        "_default": {
            "operations": "NPC operations",
            "kill_verb": "destroyed",
            "commentary_prefix": "Faction",
        },
    },
)

# Registry of voice summaries by persona name
VOICE_SUMMARIES: dict[str, PersonaVoiceSummary] = {
    "aria-mk4": ARIA_VOICE,
    "aria": ARIA_VOICE,  # Alias
    "paria": PARIA_VOICE,
    "paria-s": PARIA_SERPENTIS_VOICE,  # Serpentis faction variant
    "paria-serpentis": PARIA_SERPENTIS_VOICE,  # Alias
    "default": DEFAULT_VOICE,
}


# =============================================================================
# Persona Loader
# =============================================================================


class PersonaLoader:
    """
    Loads persona voice summaries for commentary generation.

    Uses pre-defined summaries by default, with optional
    config override for pilot directory lookup.
    """

    def __init__(
        self,
        pilot_directory: str | None = None,
        persona_override: str | None = None,
    ):
        """
        Initialize persona loader.

        Args:
            pilot_directory: Optional pilot directory path for config lookup
            persona_override: Optional persona name to use instead of auto-detection
                             (e.g., "paria-s" for Serpentis)
        """
        self._pilot_directory = pilot_directory
        self._persona_override = persona_override
        self._cached_persona: str | None = None
        self._cached_voice: PersonaVoiceSummary | None = None

    def get_voice_summary(self) -> PersonaVoiceSummary:
        """
        Get the voice summary for the active persona.

        Returns:
            PersonaVoiceSummary for LLM context
        """
        if self._cached_voice is not None:
            return self._cached_voice

        persona_name = self._detect_persona()
        self._cached_voice = VOICE_SUMMARIES.get(persona_name, DEFAULT_VOICE)
        return self._cached_voice

    def get_persona_name(self) -> str:
        """
        Get the display name of the active persona.

        Returns:
            Persona name for attribution (e.g., "ARIA", "PARIA")
        """
        voice = self.get_voice_summary()
        return voice.name

    def _detect_persona(self) -> str:
        """
        Detect the active persona from override or pilot profile.

        Priority:
        1. Explicit persona_override (from notification profile)
        2. Pilot profile persona_context configuration
        3. Default fallback

        Returns:
            Persona name key (e.g., "aria-mk4", "paria", "paria-s")
        """
        if self._cached_persona is not None:
            return self._cached_persona

        # Priority 1: Use explicit override if specified
        if self._persona_override:
            if self._persona_override in VOICE_SUMMARIES:
                self._cached_persona = self._persona_override
                logger.debug("Using persona override: %s", self._persona_override)
                return self._persona_override
            else:
                logger.warning(
                    "Unknown persona override '%s', falling back to auto-detection",
                    self._persona_override,
                )

        # Priority 2: Try to load from pilot profile
        persona = self._load_from_profile()
        if persona:
            self._cached_persona = persona
            return persona

        # Priority 3: Default fallback
        self._cached_persona = "default"
        return "default"

    def _load_from_profile(self) -> str | None:
        """
        Load persona name from pilot profile.

        Returns:
            Persona name or None if not found
        """
        if not self._pilot_directory:
            # Try to find pilot directory from config
            config_path = Path("userdata/config.json")
            if config_path.exists():
                try:
                    with open(config_path) as f:
                        config = json.load(f)

                    active_pilot = config.get("active_pilot")
                    if active_pilot:
                        # Load registry to find directory
                        registry_path = Path("userdata/pilots/_registry.json")
                        if registry_path.exists():
                            with open(registry_path) as f:
                                registry = json.load(f)
                            for entry in registry.get("pilots", []):
                                if str(entry.get("character_id")) == str(active_pilot):
                                    directory = entry.get("directory")
                                    # SEC-001: Validate pilot directory format
                                    # Directory format is "{id}_{name}" - validate the ID portion
                                    if directory:
                                        from ....core.path_security import validate_pilot_id

                                        pilot_id_part = directory.split("_")[0]
                                        is_valid, error = validate_pilot_id(pilot_id_part)
                                        if is_valid:
                                            self._pilot_directory = directory
                                        else:
                                            logger.warning(
                                                "Invalid pilot directory format: %s - %s",
                                                directory,
                                                error,
                                            )
                                            # Leave self._pilot_directory as None
                                    break
                except (json.JSONDecodeError, OSError) as e:
                    logger.debug("Failed to load pilot config: %s", e)
                    return None

        if not self._pilot_directory:
            return None

        # Read profile.md and extract persona_context
        profile_path = Path(f"userdata/pilots/{self._pilot_directory}/profile.md")
        if not profile_path.exists():
            return None

        try:
            profile_text = profile_path.read_text()

            # Look for persona_context section
            # Format: persona_context:\n  persona: xxx
            import re

            match = re.search(r"persona_context:\s*\n(?:.*\n)*?\s*persona:\s*(\S+)", profile_text)
            if match:
                return match.group(1).strip()

            # Also try YAML format
            if "persona:" in profile_text:
                match = re.search(r"^\s*persona:\s*(\S+)", profile_text, re.MULTILINE)
                if match:
                    return match.group(1).strip()

        except OSError as e:
            logger.debug("Failed to read profile: %s", e)

        return None

    def clear_cache(self) -> None:
        """Clear cached persona data."""
        self._cached_persona = None
        self._cached_voice = None


# =============================================================================
# Module-level Helper
# =============================================================================

_persona_loader: PersonaLoader | None = None


def get_persona_loader(
    pilot_directory: str | None = None,
    persona_override: str | None = None,
) -> PersonaLoader:
    """
    Get or create the persona loader singleton.

    Note: If persona_override is specified, a new loader is created
    (not cached) to allow per-profile persona settings.

    Args:
        pilot_directory: Optional pilot directory path
        persona_override: Optional persona name override (e.g., "paria-s")

    Returns:
        PersonaLoader instance
    """
    global _persona_loader

    # If persona override specified, return a fresh instance (not cached)
    # This allows different notification profiles to use different personas
    if persona_override:
        return PersonaLoader(pilot_directory, persona_override=persona_override)

    if _persona_loader is None:
        _persona_loader = PersonaLoader(pilot_directory)
    return _persona_loader


def reset_persona_loader() -> None:
    """Reset the persona loader singleton."""
    global _persona_loader
    _persona_loader = None
