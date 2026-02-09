"""
Interest Engine v2 Presets.

Presets provide complete weight baselines for common playstyles.
Built-in presets are always available; user-defined presets can
extend or override them.
"""

from .builtin import BUILTIN_PRESETS, get_builtin_preset, list_builtin_presets
from .loader import PresetLoader, get_preset_loader

__all__ = [
    "BUILTIN_PRESETS",
    "PresetLoader",
    "get_builtin_preset",
    "get_preset_loader",
    "list_builtin_presets",
]
