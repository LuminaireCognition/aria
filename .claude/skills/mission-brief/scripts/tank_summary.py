#!/usr/bin/env python3
"""Pre-render faction→hardener lookup from faction_tuning.yaml.

Injected into mission-brief via !`command` so the model receives
a flat, unambiguous table without needing to parse YAML at runtime.
"""

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    # PyYAML not available — fall back to manual extraction
    print("⚠ PyYAML not installed, tank summary unavailable")
    sys.exit(0)

TUNING_PATH = Path(__file__).resolve().parents[4] / "reference" / "archetypes" / "_shared" / "faction_tuning.yaml"

PROFILE_LABELS = {
    "armor_active": "Armor (active)",
    "shield_passive": "Shield (passive)",
    "shield_active": "Shield (active)",
    "shield_buffer": "Shield (buffer)",
}


def main():
    if not TUNING_PATH.exists():
        print("⚠ faction_tuning.yaml not found")
        return

    data = yaml.safe_load(TUNING_PATH.read_text())
    if not data:
        print("⚠ faction_tuning.yaml empty")
        return

    for profile_key, label in PROFILE_LABELS.items():
        profile = data.get(profile_key, {})
        if not profile:
            continue
        entries = []
        for faction, cfg in profile.items():
            if faction in ("drone_types", "drone_tech_suffix"):
                continue
            # Resolve inheritance
            if "inherit" in cfg:
                parent = cfg["inherit"]
                cfg = profile.get(parent, cfg)
            modules = cfg.get("modules", [])
            for mod in modules:
                if mod.get("slot") == "resist":
                    hardeners = mod.get("to", [])
                    short = " + ".join(
                        h.replace(" Armor Hardener I", "")
                        .replace(" Shield Hardener I", "")
                        .replace("Multispectrum Energized Membrane I", "Multispectrum")
                        for h in hardeners
                    )
                    entries.append(f"{faction}={short}")
        if entries:
            print(f"{label}: {' | '.join(entries)}")


if __name__ == "__main__":
    main()
