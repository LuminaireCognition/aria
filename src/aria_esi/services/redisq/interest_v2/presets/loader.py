"""
Preset Loader for Interest Engine v2.

Handles resolution of presets with inheritance and user-defined overrides.
User presets can extend built-in presets using the `base` field.

User preset location: userdata/presets/*.yaml
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .builtin import BUILTIN_PRESETS, PresetDefinition

logger = logging.getLogger(__name__)


class PresetLoader:
    """
    Preset loader with inheritance support.

    Resolves presets in order:
    1. Check user-defined presets (userdata/presets/*.yaml)
    2. Check built-in presets
    3. Apply inheritance chain if `base` field is present

    Usage:
        loader = PresetLoader()
        preset = loader.get_preset("my-corp-intel")
        weights = preset.weights
    """

    def __init__(
        self,
        user_preset_dir: Path | None = None,
    ) -> None:
        """
        Initialize preset loader.

        Args:
            user_preset_dir: Directory for user-defined presets
                           (default: userdata/presets)
        """
        self._user_dir = user_preset_dir
        self._user_presets: dict[str, PresetDefinition] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        """Lazy-load user presets on first access."""
        if self._loaded:
            return
        self._loaded = True

        if self._user_dir and self._user_dir.exists():
            self._load_user_presets()

    def _load_user_presets(self) -> None:
        """Load all user-defined presets from the user directory."""
        try:
            import yaml
        except ImportError:
            logger.warning("PyYAML not available, user presets disabled")
            return

        if not self._user_dir:
            return

        for preset_file in self._user_dir.glob("*.yaml"):
            try:
                with open(preset_file) as f:
                    data = yaml.safe_load(f)

                if not isinstance(data, dict):
                    logger.warning(f"Invalid preset file: {preset_file}")
                    continue

                name = data.get("name", preset_file.stem)
                preset = self._parse_user_preset(name, data)
                if preset:
                    self._user_presets[name.lower()] = preset
                    logger.debug(f"Loaded user preset: {name}")

            except Exception as e:
                logger.warning(f"Failed to load preset {preset_file}: {e}")

    def _parse_user_preset(
        self,
        name: str,
        data: dict[str, Any],
    ) -> PresetDefinition | None:
        """
        Parse a user preset definition.

        Handles inheritance via `base` field.

        Args:
            name: Preset name
            data: Raw YAML data

        Returns:
            PresetDefinition or None if invalid
        """
        # Handle inheritance
        base_name = data.get("base")
        base_preset: PresetDefinition | None = None

        if base_name:
            base_preset = BUILTIN_PRESETS.get(base_name.lower())
            if not base_preset and base_name.lower() in self._user_presets:
                base_preset = self._user_presets[base_name.lower()]

            if not base_preset:
                logger.warning(f"Preset {name} references unknown base: {base_name}")
                # Continue without base

        # Build weights (inherit + override)
        weights: dict[str, float] = {}
        if base_preset:
            weights = dict(base_preset.weights)

        user_weights = data.get("weights", {})
        if isinstance(user_weights, dict):
            for cat, weight in user_weights.items():
                if isinstance(weight, (int, float)):
                    weights[cat] = float(weight)

        # Build signals (inherit + deep merge)
        signals: dict[str, Any] = {}
        if base_preset and base_preset.signals:
            signals = _deep_merge({}, base_preset.signals)

        user_signals = data.get("signals", {})
        if isinstance(user_signals, dict):
            signals = _deep_merge(signals, user_signals)

        # Build rules (inherit + extend lists)
        rules: dict[str, Any] = {}
        if base_preset and base_preset.rules:
            rules = dict(base_preset.rules)
            for key in ("always_notify", "always_ignore"):
                if key in rules:
                    rules[key] = list(rules[key])

        user_rules = data.get("rules", {})
        if isinstance(user_rules, dict):
            for key, value in user_rules.items():
                if key in ("always_notify", "always_ignore") and isinstance(value, list):
                    existing = rules.get(key, [])
                    rules[key] = list(set(existing) | set(value))
                else:
                    rules[key] = value

        # Thresholds (override, not merge)
        thresholds = data.get("thresholds")

        return PresetDefinition(
            name=name,
            description=data.get("description", f"User preset: {name}"),
            weights=weights,
            signals=signals,
            rules=rules,
            thresholds=thresholds,
        )

    def get_preset(self, name: str) -> PresetDefinition | None:
        """
        Get a preset by name.

        Resolution order:
        1. User-defined presets
        2. Built-in presets

        Args:
            name: Preset name (case-insensitive)

        Returns:
            PresetDefinition or None if not found
        """
        self._ensure_loaded()

        name_lower = name.lower()

        # Check user presets first
        if name_lower in self._user_presets:
            return self._user_presets[name_lower]

        # Fall back to built-in
        return BUILTIN_PRESETS.get(name_lower)

    def list_presets(self) -> dict[str, list[str]]:
        """
        List all available presets.

        Returns:
            Dict with 'builtin' and 'user' preset name lists
        """
        self._ensure_loaded()

        return {
            "builtin": list(BUILTIN_PRESETS.keys()),
            "user": list(self._user_presets.keys()),
        }

    def get_effective_weights(
        self,
        preset_name: str,
        customize: dict[str, str] | None = None,
    ) -> dict[str, float]:
        """
        Get effective weights with customize adjustments applied.

        Args:
            preset_name: Preset name
            customize: Dict of category -> adjustment (e.g., "+20%", "-10%")

        Returns:
            Dict of category -> effective weight
        """
        preset = self.get_preset(preset_name)
        if not preset:
            return {}

        weights = dict(preset.weights)

        if customize:
            from ..config import parse_customize_adjustment

            for category, adjustment in customize.items():
                if category in weights:
                    multiplier = parse_customize_adjustment(adjustment)
                    weights[category] = weights[category] * multiplier

        return weights


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """
    Deep merge two dictionaries.

    Args:
        base: Base dictionary (modified in place)
        override: Override values

    Returns:
        Merged dictionary (same object as base)
    """
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


# =============================================================================
# Global Loader
# =============================================================================

_global_loader: PresetLoader | None = None


def get_preset_loader(user_dir: Path | None = None) -> PresetLoader:
    """
    Get the global preset loader.

    Args:
        user_dir: Optional user preset directory

    Returns:
        PresetLoader instance
    """
    global _global_loader
    if _global_loader is None:
        _global_loader = PresetLoader(user_dir)
    return _global_loader


def reset_preset_loader() -> None:
    """Reset the global preset loader (for testing)."""
    global _global_loader
    _global_loader = None
