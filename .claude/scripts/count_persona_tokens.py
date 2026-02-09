#!/usr/bin/env python3
"""
Count tokens in persona files to validate proposal claims.

Uses tiktoken with cl100k_base encoding (Claude-compatible approximation).
"""

import json
from pathlib import Path

try:
    import tiktoken
except ImportError:
    print("ERROR: tiktoken not installed. Run: uv add tiktoken")
    exit(1)


def count_tokens(text: str, encoding) -> int:
    """Count tokens in text using specified encoding."""
    return len(encoding.encode(text))


def count_file_tokens(filepath: Path, encoding, base_dir: Path) -> dict:
    """Count tokens in a file, return metadata."""
    # Make path absolute for existence check
    abs_path = base_dir / filepath if not filepath.is_absolute() else filepath

    if not abs_path.exists():
        return {"path": str(filepath), "exists": False, "tokens": 0, "lines": 0}

    content = abs_path.read_text()
    return {
        "path": str(filepath),
        "exists": True,
        "tokens": count_tokens(content, encoding),
        "lines": len(content.splitlines()),
        "chars": len(content),
    }


def main():
    # Use cl100k_base - closest to Claude's tokenizer
    encoding = tiktoken.get_encoding("cl100k_base")

    # Get the project root (where personas/ lives)
    project_root = Path(__file__).parent.parent.parent
    base = Path("personas")

    # Define file groups for analysis
    groups = {
        "shared": [
            base / "_shared/rp-levels.md",
            base / "_shared/skill-loading.md",
        ],
        "aria-mk4": [
            base / "aria-mk4/manifest.yaml",
            base / "aria-mk4/voice.md",
            base / "aria-mk4/intel-sources.md",
        ],
        "aura-c": [
            base / "aura-c/manifest.yaml",
            base / "aura-c/voice.md",
            base / "aura-c/intel-sources.md",
        ],
        "vind": [
            base / "vind/manifest.yaml",
            base / "vind/voice.md",
            base / "vind/intel-sources.md",
        ],
        "throne": [
            base / "throne/manifest.yaml",
            base / "throne/voice.md",
            base / "throne/intel-sources.md",
        ],
        "paria": [
            base / "paria/manifest.yaml",
            base / "paria/voice.md",
            base / "paria/intel-sources.md",
        ],
        "paria-overlays": [
            base / "paria/skill-overlays/threat-assessment.md",
            base / "paria/skill-overlays/route.md",
            base / "paria/skill-overlays/fitting.md",
            base / "paria/skill-overlays/price.md",
            base / "paria/skill-overlays/mission-brief.md",
        ],
        "paria-exclusive": [
            base / "paria-exclusive/mark-assessment.md",
            base / "paria-exclusive/hunting-grounds.md",
            base / "paria-exclusive/escape-route.md",
            base / "paria-exclusive/ransom-calc.md",
            base / "paria-exclusive/sec-status.md",
        ],
    }

    results = {}
    totals = {"by_group": {}, "grand_total": 0}

    print("=" * 70)
    print("PERSONA TOKEN COUNT ANALYSIS")
    print("Encoding: cl100k_base (Claude-compatible approximation)")
    print("=" * 70)
    print()

    for group_name, files in groups.items():
        group_tokens = 0
        group_files = []

        for filepath in files:
            info = count_file_tokens(filepath, encoding, project_root)
            group_files.append(info)
            if info["exists"]:
                group_tokens += info["tokens"]

        results[group_name] = group_files
        totals["by_group"][group_name] = group_tokens
        totals["grand_total"] += group_tokens

        print(f"## {group_name}")
        print(f"{'File':<50} {'Tokens':>8} {'Lines':>6}")
        print("-" * 66)
        for f in group_files:
            if f["exists"]:
                print(f"{f['path']:<50} {f['tokens']:>8} {f['lines']:>6}")
            else:
                print(f"{f['path']:<50} {'N/A':>8} {'N/A':>6}")
        print(f"{'SUBTOTAL':<50} {group_tokens:>8}")
        print()

    # Session load analysis
    print("=" * 70)
    print("PER-SESSION LOAD ANALYSIS")
    print("=" * 70)
    print()

    # Empire session (full RP): shared + faction files
    empire_personas = ["aria-mk4", "aura-c", "vind", "throne"]

    print("### Empire Sessions (Full RP)")
    print(f"{'Persona':<15} {'Shared':>10} {'Faction':>10} {'Total':>10}")
    print("-" * 47)

    shared_tokens = totals["by_group"]["shared"]
    for persona in empire_personas:
        faction_tokens = totals["by_group"][persona]
        total = shared_tokens + faction_tokens
        print(f"{persona:<15} {shared_tokens:>10} {faction_tokens:>10} {total:>10}")

    avg_empire = shared_tokens + sum(totals["by_group"][p] for p in empire_personas) // len(
        empire_personas
    )
    print(f"{'AVERAGE':<15} {'-':>10} {'-':>10} {avg_empire:>10}")
    print()

    # Pirate session (full RP): shared + paria + overlays (when skills invoked)
    print("### Pirate Session (Full RP)")
    paria_base = shared_tokens + totals["by_group"]["paria"]
    paria_with_overlays = paria_base + totals["by_group"]["paria-overlays"]
    paria_exclusive = totals["by_group"]["paria-exclusive"]

    print(f"Base (shared + paria):       {paria_base:>6} tokens")
    print(f"With all skill overlays:     {paria_with_overlays:>6} tokens")
    print(f"Exclusive skills (separate): {paria_exclusive:>6} tokens")
    print()

    # Duplication analysis
    print("=" * 70)
    print("DUPLICATION ANALYSIS")
    print("=" * 70)
    print()

    # Read actual voice files to find common content
    personas_dir = project_root / base
    voice_files = {
        "aria-mk4": (personas_dir / "aria-mk4/voice.md").read_text()
        if (personas_dir / "aria-mk4/voice.md").exists()
        else "",
        "aura-c": (personas_dir / "aura-c/voice.md").read_text()
        if (personas_dir / "aura-c/voice.md").exists()
        else "",
        "vind": (personas_dir / "vind/voice.md").read_text()
        if (personas_dir / "vind/voice.md").exists()
        else "",
        "throne": (personas_dir / "throne/voice.md").read_text()
        if (personas_dir / "throne/voice.md").exists()
        else "",
    }

    # Find common lines (exact matches)
    all_lines = {}
    for persona, content in voice_files.items():
        for line in content.splitlines():
            stripped = line.strip()
            if stripped and len(stripped) > 10:  # Ignore short/empty lines
                if stripped not in all_lines:
                    all_lines[stripped] = set()
                all_lines[stripped].add(persona)

    # Lines appearing in all 4 empire personas
    common_to_all = [line for line, personas in all_lines.items() if len(personas) == 4]
    common_to_3plus = [line for line, personas in all_lines.items() if len(personas) >= 3]

    print(f"Lines common to ALL 4 empire personas: {len(common_to_all)}")
    print(f"Lines common to 3+ empire personas:    {len(common_to_3plus)}")
    print()

    if common_to_all:
        print("Common lines (all 4):")
        for line in common_to_all[:10]:  # Show first 10
            print(f"  - {line[:60]}{'...' if len(line) > 60 else ''}")
    print()

    # Calculate actual duplication percentage
    total_empire_voice_tokens = sum(
        count_tokens(content, encoding) for content in voice_files.values()
    )
    common_tokens = sum(count_tokens(line, encoding) for line in common_to_all) * 4  # Duplicated 4x

    if total_empire_voice_tokens > 0:
        dup_pct = (common_tokens / total_empire_voice_tokens) * 100
        print(f"Estimated duplication in empire voice.md files: {dup_pct:.1f}%")

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total tokens in persona system: {totals['grand_total']}")
    print()

    # Output JSON for programmatic use
    output = {
        "encoding": "cl100k_base",
        "files": results,
        "totals": totals,
        "session_loads": {
            "empire_avg": avg_empire,
            "paria_base": paria_base,
            "paria_with_overlays": paria_with_overlays,
        },
    }

    json_path = project_root / "docs/proposals/token_analysis.json"
    json_path.write_text(json.dumps(output, indent=2))
    print(f"Detailed results written to: {json_path}")


if __name__ == "__main__":
    main()
