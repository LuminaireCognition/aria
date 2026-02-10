# README First-Run Improvements Proposal

**Status:** PROPOSED (2026-02-08)
**Owner:** Docs / DX
**Scope:** `README.md` (primary), with links to existing docs and tests
**Related:** `dev/proposals/LINUX_VM_DOCKER_RUNTIME_PROPOSAL.md`

## Executive Summary

This proposal converts 10 high-level documentation suggestions into implementation-ready README edits that reduce first-run drop-off, resolve setup ambiguity, and strengthen trust claims with concrete evidence.

Primary objective: a new user should go from clone to first useful ARIA response in under 5 minutes with minimal uncertainty.

## Problem Statement

Current README issues observed:

- Value proposition is broad but not oriented around a fast first success path.
- Quick Start does not include explicit expected output or verification checks.
- Setup flow (`./aria-init` vs `/setup` vs optional ESI) is split across sections and feels fragmented.
- Compatibility assumptions are implicit.
- “See It In Action” appears before users are oriented and adds early scroll depth.
- Trust language is strong but evidence links are not foregrounded.
- First-run failure handling appears late.
- Legal/disclaimer tone is heavy for top-level onboarding scan.
- No direct next-doc CTA after Quick Start.

## Success Criteria

A first-time user can answer all of the following from `README.md` without opening additional docs:

1. Is this for me?
2. What will I achieve in 5 minutes?
3. Which setup command do I run first?
4. What output should I expect if setup worked?
5. What do I do if first run fails?
6. Where do I go next immediately after Quick Start?

Measurable quality gates:

- One copy/paste starter prompt appears above fold.
- Quick Start includes a “What you’ll see when it works” block with real output signatures.
- Setup paths are presented in a single decision table.
- At least 3 concrete evidence links back trust claims (policy + tests).
- Troubleshooting has a short first-run subsection directly after Quick Start.

## Proposed README Changes

### 1) Add above-the-fold value + 60-second success path

**Current anchor:** `README.md:26` (`### What ARIA Does`)

**Change:** Insert a compact `## Get Value in 60 Seconds` section before the long feature list.

**Proposed copy:**

```md
## Get Value in 60 Seconds

**Who this is for:** EVE Online pilots using Claude Code who want tactical answers quickly (missions, fittings, route safety, market checks).

**What you get in the first 5 minutes:**
- ARIA initialized for your pilot
- Profile files generated
- First tactical answer in natural language

**First useful prompt (copy/paste):**
`I'm in a Vexor running level 2 missions. Give me a fit and damage profile for Damsel in Distress.`
```

**What success looks like to the user:** ARIA responds with concrete fit and tactical guidance, not setup/error prompts.

---

### 2) Add “What you’ll see when it works” directly after Quick Start

**Current anchor:** `README.md:49`

**Change:** Add `### What you'll see when it works` immediately after the 3-step quick start commands.

**Use real script signatures from `aria-init` output:**

```text
Pilot profile        [OK]
Operational profile  [OK]
Ship status          [OK]
Mission log          [OK]
Exploration catalog  [OK]
Blueprint library    [OK]

✓ All files generated successfully
✓ ARIA is fully configured and ready to use.
```

```text
Files created:
✓ userdata/pilots/0000000000_<pilot_slug>/profile.md
✓ userdata/pilots/0000000000_<pilot_slug>/operations.md
✓ userdata/pilots/0000000000_<pilot_slug>/ships.md
✓ userdata/pilots/0000000000_<pilot_slug>/missions.md
✓ userdata/pilots/0000000000_<pilot_slug>/exploration.md
✓ userdata/pilots/0000000000_<pilot_slug>/industry/blueprints.md
```

**Add verification commands (copy/paste):**

```bash
# Verify key outputs exist
ls -la userdata/pilots/*/profile.md userdata/pilots/*/operations.md

# Verify boot hook is executable
ls -la .claude/hooks/aria-boot.sh
# Should include: -rwxr-xr-x

# Start session
claude
```

**What success looks like to the user:** they see ARIA session boot output and can run `/help` without setup prompts.

---

### 3) Clarify setup flow (`./aria-init`, `/setup`, optional ESI)

**Current anchors:** `README.md:77`, `README.md:224`

**Change:** Add a single decision table under `## Using ARIA` and cross-link optional ESI section.

**Proposed copy:**

```md
### Setup Decision Table

| Goal | Required? | Run where | Command | Use when |
|---|---|---|---|---|
| Initial bootstrap | Yes (first install) | Shell | `./aria-init` | First time in this repo |
| Edit/update pilot profile | Optional | Claude Code | `/setup` | Changing faction, playstyle, operating profile |
| Enable live character sync | Optional | Shell | `uv run python .claude/scripts/aria-oauth-setup.py` | Want auto location/ship/wallet/skills |

If you run only one setup command on day 1, run `./aria-init`.
```

**What success looks like to the user:** no ambiguity about command order or required/optional paths.

---

### 4) Add explicit Compatibility block near Requirements

**Current anchor:** `README.md:40`

**Change:** Add `### Compatibility` below requirements bullets.

**Proposed copy:**

```md
### Compatibility

- **OS support:** Linux and macOS supported; native Windows shell unsupported
- **Windows 11 path:** use WSL2 as your Linux environment
- **Runtime recommendation:** Docker quick start only when container OAuth + MCP gates pass; otherwise use native `uv` setup
- **Linux VM:** always valid as a hardened deployment option
- **Shell:** Bash-compatible shell (bootstrap script uses `#!/usr/bin/env bash`)
- **Python:** 3.11+ (CI-tested on 3.11, 3.12, 3.13)
- **Claude Code:** Current stable release
```

**What success looks like to the user:** fewer immediate failures caused by environment mismatch.

---

### 5) Restructure “See It In Action” for scanability

**Current anchor:** `README.md:88`

**Change:** Keep one short example visible; move full transcripts behind collapsible details.

**Proposed structure:**

- Keep one 5-8 line visible example (recommended: Mission Brief).
- Add one-line summaries for Route Planning and Fit Recommendation.
- Place their long output under `<details>`.

**What success looks like to the user:** they see proof quickly without early scroll fatigue.

---

### 6) Add compact architecture/data-path flow near trust section

**Current anchor:** `README.md:236`

**Change:** Add a minimal “How ARIA works” bullet flow above detailed trust text.

**Proposed copy:**

```md
### How ARIA Works (Data Path)

1. You ask in Claude Code (`claude` session)
2. ARIA routes the request to the relevant skill/tools
3. MCP services query SDE/ESI/market/reference sources
4. Verification rules gate factual claims before response
5. ARIA returns actionable output (with source-aware confidence)

See: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
```

**What success looks like to the user:** fast mental model of how answers are produced.

---

### 7) Strengthen trust claims with concrete verification evidence

**Current anchor:** `README.md:238`

**Change:** Keep trust statement but follow it with specific verification links and tests.

**Proposed additions:**

```md
Evidence and enforcement:

- Verification policy: [docs/DATA_VERIFICATION.md](docs/DATA_VERIFICATION.md)
- Source authority model: [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md)
- Security controls: [SECURITY.md](SECURITY.md)

Example test coverage:
- `tests/test_data_integrity.py` (SHA256 + manifest validation)
- `tests/integration/test_security_paths.py` (path traversal/allowlist protections)
- `tests/fitting/test_eos_bridge.py` (fit-stat calculation and EOS integration behavior)
- `tests/integration/test_sde_data_integrity.py` (SDE integrity expectations)
```

**What success looks like to the user:** trust claims are auditable in-repo.

---

### 8) Move common first-run failures to immediately after Quick Start

**Current anchor:** `README.md:263` (currently late in file)

**Change:** Add a compact “Common first-run failures” section after Quick Start and before “Using ARIA”.

**Proposed copy:**

```md
### Common First-Run Failures

**`./aria-init: Permission denied`**
```bash
chmod +x aria-init
./aria-init
```

**No ARIA boot sequence in `claude`**
```bash
chmod +x .claude/hooks/aria-boot.sh
ls -la .claude/hooks/aria-boot.sh
# Should include: -rwxr-xr-x
```

**ESI token expired / auth errors (if ESI enabled)**
```bash
.claude/scripts/aria-refresh
# If still failing:
uv run python .claude/scripts/aria-oauth-setup.py
```
```

**What success looks like to the user:** first-run blockers are resolved without hunting through the full README.

---

### 9) Tighten disclaimer tone and move extended flavor lower

**Current anchor:** `README.md:335`

**Change:** Keep concise legal clarity in README; move extended humorous copy to `ATTRIBUTION.md` (or remove).

**Proposed README replacement:**

```md
### Disclaimer

ARIA provides tactical guidance, not guarantees.
Verify critical decisions in-game before committing ships or ISK.
Provided "as is" without warranty.
```

**What success looks like to the user:** professionalism during initial evaluation, full legal detail still available.

---

### 10) Add explicit Quick Start CTA to exact next doc

**Current anchors:** `README.md:18`, `README.md:49`

**Change:** Add a one-line next step directly under Quick Start.

**Proposed copy:**

```md
Next step: follow [docs/FIRST_RUN.md](docs/FIRST_RUN.md) for a guided 5-minute first session and profile walkthrough.
```

Optional addition (if you want an even tighter path): add a second link to `docs/TLDR.md` for returning users.

**What success looks like to the user:** obvious continuation path instead of doc-choice paralysis.

## Proposed Section Order (Top of README)

1. Title + short product statement
2. Quick docs links
3. `Get Value in 60 Seconds` (new)
4. Requirements + Compatibility (expanded)
5. Quick Start
6. What you’ll see when it works (new)
7. Common first-run failures (new, compact)
8. Quick Start CTA to `docs/FIRST_RUN.md` (new)
9. Using ARIA + Setup Decision Table (clarified)
10. See It In Action (compressed)
11. ESI Optional
12. Data Freshness & Trust + How ARIA works + evidence links

## Implementation Notes

- Reuse existing wording where it already aligns with scripts/docs to avoid drift.
- Keep Quick Start runnable with minimal branching.
- Ensure command examples are consistent with current README style (`bash` blocks).
- Keep first-run file/path examples canonical (`userdata/pilots/...` + `profile.md` style names), not legacy `data/...`.
- Keep runtime/platform wording aligned with `LINUX_VM_DOCKER_RUNTIME_PROPOSAL.md` outcomes.

## Acceptance Checklist

- [ ] Above-the-fold section includes audience, 5-minute outcome, and copy/paste first prompt.
- [ ] Quick Start has explicit “What you’ll see when it works” with recognizable output.
- [ ] Setup decision table clearly marks required vs optional steps.
- [ ] Compatibility block added near Requirements.
- [ ] No first-run examples reference legacy `data/...` paths or legacy bootstrap filenames.
- [ ] Platform narrative matches runtime proposal: Linux/macOS supported, Windows 11 via WSL2, Docker quick start is gate-conditional.
- [ ] “See It In Action” has one visible short example and collapsed long examples.
- [ ] Architecture/data path is summarized near trust section.
- [ ] Trust claims link to policy + security + tests.
- [ ] Common first-run failures appear right after Quick Start.
- [ ] Disclaimer is concise and professional in README.
- [ ] Quick Start ends with one-line next-doc CTA.

## Rollout Sequence

Recommended order (highest first-run impact first):

1. Add 60-second value section
2. Add “What you’ll see when it works” + verification checks
3. Add setup decision table
4. Add common first-run failures near Quick Start
5. Add compatibility block
6. Add Quick Start CTA
7. Compress “See It In Action”
8. Add architecture/data-path summary
9. Add trust evidence links
10. Tighten disclaimer placement/tone

## Risks and Mitigations

- Risk: README grows too long despite improvements.
  - Mitigation: keep primary flow compact; push depth into linked docs and `<details>`.

- Risk: output examples drift from script behavior over time.
  - Mitigation: keep examples to stable signatures (`[OK]`, file list, executable checks) and avoid brittle timestamps.

- Risk: compatibility statement overpromises.
  - Mitigation: label as “recommended/tested” not “only supported.”

## Notes for Follow-up PR

When implemented, include before/after screenshots of top README sections and validate commands in a clean clone flow.
