# Route Skill Analysis: Dodixie→Jita Avoiding Uedama

**Date:** 2026-03-01
**Triggered by:** Exercise review 20260301-002542, queries 22-23
**Status:** Investigation complete — initial review finding partially retracted

---

## The Observed Issue

The route skill, when asked "Safest route from Dodixie to Jita avoiding Uedama," returns a 14-jump route through **Olettiers (0.43 lowsec)** and states "No fully high-sec route exists when avoiding Uedama."

The initial exercise review (REVIEW.md) flagged this as a **CRITICAL correctness error**, claiming multiple highsec paths exist. That assessment was wrong.

---

## What Has Been Eliminated

### 1. Model quality is NOT a factor

The route skill was upgraded from haiku to sonnet and re-exercised (run 20260301-092245). Both models produce identical output for both route queries. The route and warning text are faithful renderings of what the routing engine returns — the LLM is not confabulating the route or the warning.

**Eliminated:** Model confabulation or quality gap.

### 2. The routing engine is consistent

Three routing engine calls were made to characterize the topology:

| Query | Lowsec Systems | Warning |
|-------|----------------|---------|
| Safe, no avoidance | 0 (routes through Uedama at 0.50) | None |
| Safe, avoid Uedama | 1: Olettiers (0.43) | "No fully high-sec route available" |
| Safe, avoid Uedama + Olettiers | 2: Kubinen (0.42) + Enderailen (0.45) | "No fully high-sec route available" |

Each progressive avoidance produces a longer route through different lowsec systems. The router is consistently finding alternative paths and correctly flagging them as containing lowsec.

**Eliminated:** Router returning inconsistent or arbitrary results.

### 3. The "no highsec route" claim appears to be correct

Uedama is a chokepoint *because* there is no highsec alternative. The EVE stargate topology between Gallente space (Sinq Laison) and Caldari space (The Forge) has limited highsec crossings:

- **Primary:** Algogille → Kassigainen → Hatakani → Sivala → **Uedama** → Haatomo → ... → Jita
- **Secondary:** ... → Iyen-Oursta → Perimeter → Jita (requires transiting **Olettiers**, lowsec)
- **Tertiary:** ... → Sivala → **Kubinen** → **Enderailen** → Rairomon → ... → Jita (two lowsec)

All three paths from Gallente to Caldari space funnel through the same chokepoint region. Removing Uedama from the graph forces lowsec transit regardless of path.

**Eliminated:** Router graph error or missing highsec connections.

---

## What Remains as Concerns

### 1. Safe mode semantics may surprise users

The `safe` mode uses **weighted penalties**, not hard exclusion:

| Transition | Weight |
|------------|--------|
| Highsec → Highsec | 1.0 |
| Highsec → Lowsec | 50.0 |
| Lowsec → Lowsec | 10.0 |
| Any → Nullsec | 100.0 |

Source: `src/aria_esi/services/navigation/weights.py:102-146`

This means `--safe` will route through lowsec when no highsec-only path exists. The warning "No fully high-sec route available" is generated **post-hoc** by `result_builder.py:129-130` when the computed route contains systems below the highsec threshold (0.45).

**Concern:** A user asking for a "safe" route reasonably expects an all-highsec result. Getting a lowsec system in a "safe" route, even with a warning, may feel like a bug. The skill output handles this acceptably — both haiku and sonnet versions highlight Olettiers clearly — but the UX could be improved.

**Possible enhancement:** When safe mode must transit lowsec, lead with the constraint explanation ("Uedama is the only highsec crossing between Gallente and Caldari space; avoiding it requires one lowsec jump") before showing the route. This frames the result as a topology fact rather than a routing failure.

### 2. The skill output doesn't explain *why* no highsec route exists

Both model outputs state the fact ("no fully highsec route exists") but don't explain the geographic chokepoint. A user unfamiliar with the Gallente-Caldari border topology might think the router is broken. Adding a brief explanation would improve trust.

### 3. The REVIEW.md contains an incorrect CRITICAL finding

The review at `dev/reviews/exercise-outputs/20260301-002542/REVIEW.md` flags this as "CRITICAL: Route confabulation" and says "multiple highsec paths exist." This is factually wrong and should be corrected to avoid misleading future reviewers.

### 4. HIGHSEC_THRESHOLD value (0.45)

The warning fires when any system is below 0.45 security. Olettiers is 0.43 — correctly flagged. Ambeke on the route is 0.50 — borderline highsec (rounds to 0.5 in-game). The threshold appears correct for its purpose.

---

## Recommendations

| Priority | Action | Rationale |
|----------|--------|-----------|
| P1 | Correct REVIEW.md finding from CRITICAL to NOT A BUG | Prevents false remediation work |
| P2 | Add chokepoint explanation to route skill output when safe mode transits lowsec | Improves user trust and understanding |
| P3 | Consider adding a `--strict-highsec` mode that refuses to route through lowsec | Clear semantic distinction from soft-preference `--safe` |
| — | Revert route model to haiku | Sonnet produces identical results for this skill; haiku is sufficient and cheaper |

---

## Appendix: Model Comparison

| Metric | Haiku (original) | Sonnet (rerun) |
|--------|-------------------|----------------|
| Q1 duration | 17.1s | 18.0s |
| Q2 duration | 15.4s | 16.1s |
| Route returned | Identical | Identical |
| Warning text | Identical | Identical |
| Formatting quality | Good | Good (marginally more context) |

The sonnet upgrade provides no meaningful improvement for route queries. The skill's value comes from the MCP routing engine, not the LLM's reasoning. Haiku is adequate.
