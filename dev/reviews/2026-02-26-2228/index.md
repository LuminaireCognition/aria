# Skill Review Batch Run — 2026-02-26-2228

**Template:** skill-review
**Skills reviewed:** 45 of 49 (skipped: mission-brief, fitting, orient, aria-review — reviewed/reworked earlier today)
**Agents:** 9 parallel batches of 5

---

## Summary Table

| Skill | Est. Tokens | Est. Savings | % | Top Issue |
|-------|------------|-------------|---|-----------|
| abyssal | ~1,725 | ~1,160 | 67% | 5 examples inline data from declared `data_source` |
| agents-research | ~3,400 | ~1,080 | 32% | ESI availability check (B), ASCII templates (E) |
| arbitrage | ~1,890 | ~520 | 28% | MCP param docs duplicate tool schema |
| aria-status | ~1,340 | ~340 | 25% | Example output duplicates response format (G) |
| assets | ~3,400 | ~1,470 | 43% | 6 fabricated examples contradict hallucination guard |
| build-cost | ~7,400 | ~5,140 | 69% | ~2,450 tokens of pseudocode importing non-existent modules |
| clones | ~2,750 | ~1,440 | 52% | ESI availability (B), 4 ASCII templates (E), implant tables (A) |
| contracts | ~3,750 | ~2,410 | 64% | Two full JSON response structures as dev docs |
| corp | ~3,278 | ~1,450 | 44% | No hallucination guard, ESI check (B), data volatility (B) |
| escape-route | ~2,100 | ~810 | 39% | Hardcoded gatecamp system names contradict MCP-first |
| esi-query | ~3,230 | ~1,230 | 38% | Triple-redundant "ESI is optional", inlined URL lists |
| exploration | ~1,900 | ~380 | 20% | Inlined site/hacking tables duplicate prerequisites |
| find | ~1,950 | ~700 | 36% | Stale MCP tool syntax, experience adaptation (B) |
| first-run-setup | ~3,170 | ~730 | 23% | Pseudocode uses non-existent Python API |
| fit-budget | ~3,250 | ~650 | 20% | 90-line substitution DB inlines `sde(meta_variants)` data |
| fit-check | ~2,900 | ~930 | 32% | Pseudo-code + full example output duplicate MCP logic |
| fittings | ~2,450 | ~1,200 | 49% | 3 JSON examples + slot flag table are CLI internals |
| gatecamp | ~2,140 | ~820 | 38% | "Known Gatecamp Systems" is static reference data (A) |
| help | ~9,780 | ~4,800 | 49% | Should be dynamic dispatcher reading `_index.json` |
| hunting-grounds | ~3,100 | ~890 | 29% | Coalition response table is static/perishable |
| industry-jobs | ~3,330 | ~1,830 | 55% | 5 ASCII-box response templates consume 60% of file |
| isk-compare | ~3,875 | ~2,325 | 60% | 70 lines of ISK/hour tables duplicate declared data source |
| journal | ~2,575 | ~875 | 34% | Confirmation templates duplicate entry format (G) |
| killmail | ~1,917 | ~690 | 36% | 6-step manual pipeline replaced by single MCP call |
| killmails | ~3,100 | ~1,210 | 39% | Zero MCP integration, legacy Python scripts |
| lp-store | ~3,270 | ~1,080 | 33% | Redundant field-to-source table, 3 ASCII templates |
| mail | ~2,550 | ~930 | 36% | No hallucination guard, 70 lines of JSON schemas |
| mark-assessment | ~1,730 | ~750 | 43% | **Zero MCP integration** — all data is hardcoded |
| mining | ~3,080 | ~1,140 | 37% | 90 lines JSON schemas, ore table duplicates prerequisite |
| mining-advisory | ~1,470 | ~200 | 14% | Ore table duplicates declared prerequisite (A) |
| orders | ~2,948 | ~1,620 | 55% | 93 lines JSON examples + 4 duplicate ASCII templates |
| pi | ~3,371 | ~1,480 | 44% | 3 profit examples where 1 suffices, inlined constants |
| pilot | ~2,366 | ~750 | 32% | 5 ASCII-box templates for near-identical layouts |
| price | ~2,398 | ~1,130 | 47% | No MCP `market()` usage despite documented dispatchers |
| ransom-calc | ~1,681 | ~1,010 | 60% | **Zero data grounding** — all ISK figures hardcoded |
| reactions | ~2,760 | ~1,130 | 40% | Inlined reference data without prerequisite declaration |
| route | ~4,110 | ~990 | 24% | 3 near-identical ASCII templates (G) |
| sec-status | ~2,220 | ~810 | 37% | Inlined security status data without prerequisite |
| ship-next | ~3,330 | ~1,040 | 31% | Inlined progression paths without prerequisite |
| skillplan | ~5,200 | ~770 | 15% | Best grounding discipline — model for other skills |
| skillqueue | ~2,752 | ~1,200 | 44% | ESI boilerplate (B), 4 ASCII templates (G) |
| standings | ~3,909 | ~1,600 | 41% | ~135 lines inline declared `data_sources` content (A) |
| threat-assessment | ~4,972 | ~1,910 | 38% | Exemplary guards, but 5 response format variants |
| wallet-journal | ~2,690 | ~740 | 28% | 19-row ref type table is static ESI metadata |
| watchlist | ~1,680 | ~310 | 18% | Integration section describes other skills' behavior |

### Aggregate

- **Total tokens across 45 skills:** ~136,986
- **Total estimated savings:** ~51,140 tokens
- **Average reduction:** ~37%
- **Post-reduction estimate:** ~85,846 tokens

---

## Grounding Risk Tiers

### Critical — Zero or Near-Zero Data Grounding

These skills have no MCP calls, no prerequisite files, and no hallucination guards. All output is from training data.

| Skill | Issue |
|-------|-------|
| **mark-assessment** | No `sde()`, `market()`, or `fitting()` calls. Ship stats, gank calcs, CONCORD times all hardcoded. |
| **ransom-calc** | Ship values, implant prices, insurance payouts, ransom ranges all static ISK from training data. |
| **killmails** | No MCP integration despite `killmails()` dispatcher existing. Uses legacy Python scripts. |
| **price** | No `market()` dispatcher usage despite it being the primary market interface. |

### High — Missing Hallucination Guards

Skills with MCP integration but no explicit "do not fabricate" instruction:

corp, mail, mining, clones, contracts, orders, pilot, skillqueue, wallet-journal

### Good — Model Grounding Patterns

Skills whose grounding discipline should be adopted project-wide:

- **skillplan** — hallucination guard, field-to-source mapping, anti-pattern examples
- **threat-assessment** — same pattern, plus sovereignty/FW conditional guards
- **escape-route** — field-to-source mapping with explicit anti-patterns
- **mining-advisory** — proper prerequisite declaration + hallucination guard

---

## Cross-Cutting Patterns (by frequency)

### 1. Pattern B: ESI Availability Check Duplication (~12 skills)

Nearly identical 20-30 line blocks restating CLAUDE.md's session-level ESI availability handling. Found in: agents-research, assets, clones, corp, esi-query, fit-budget, industry-jobs, orders, pilot, skillqueue, wallet-journal, and others.

**Recommendation:** Delete from all skills. This is system-level behavior handled before skill loading.

### 2. Pattern E: ASCII-Box Response Template Bloat (~25 skills)

Box-drawing response templates (3-5 variants per skill) consume 30-50% of file size. Multiple variants for: standard, RP, empty-state, error-state, multi-item.

**Recommendation:** One compact template per skill. RP formatting belongs in persona overlays, not SKILL.md. Empty/error states need one line each, not full ASCII art.

### 3. Pattern A: Inlined Reference Data (~15 skills)

Static game data embedded in SKILL.md that duplicates declared `prerequisite_files` or `data_sources`, or data that should come from MCP at runtime.

Worst offenders: abyssal (170 lines), standings (~135 lines), isk-compare (70 lines), mining (ore table), fit-budget (90-line substitution DB), build-cost (facility/decryptor tables).

**Recommendation:** Delete inlined data. Add imperative reference: "Read `{file}` for X" or "Query `sde(action=...)` for Y."

### 4. Pattern G: Duplicate Sections Within Same File (~10 skills)

Response format shown multiple times, example output that duplicates the template, confirmation display that mirrors entry format.

Worst offenders: aria-status, journal, route (3 near-identical templates), orders (4 templates), industry-jobs (5 templates).

**Recommendation:** One canonical template. Variant differences noted as inline conditions, not separate blocks.

### 5. Pattern D: "Why X?" Justification Prose (~8 skills)

Paragraphs explaining rationale for protocols. Claude needs instructions, not justifications.

**Recommendation:** Delete all justification prose.

### 6. Missing MCP Migration (~4 skills)

Skills that predate the MCP dispatcher architecture and still use legacy CLI commands, direct ESI URLs, or no data source at all.

**Recommendation:** mark-assessment, ransom-calc, price, and killmails need fundamental rewrites to use MCP dispatchers.

### 7. JSON Response Schema Documentation (~6 skills)

Full JSON response structures embedded as "documentation." Claude sees actual responses at runtime.

Worst offenders: contracts (~600 tokens), orders (93 lines), mail (70 lines), mining (90 lines), fittings.

**Recommendation:** Delete. MCP tool responses are self-documenting at runtime.

---

## Recommended Action Priority

1. **Delete ESI Availability Check** from all 12+ skills — mechanical, zero-risk removal (~2,400 tokens)
2. **Rewrite help** as dynamic `_index.json` dispatcher — single largest saving (~4,800 tokens)
3. **Fix zero-grounding skills** (mark-assessment, ransom-calc, price, killmails) — highest quality risk
4. **Add hallucination guards** to the 9 skills missing them — template from skillplan
5. **Remove inlined reference data** (Pattern A) across 15 skills — ~3,000+ tokens
6. **Consolidate response templates** to 1 per skill — ~5,000+ tokens across 25 skills
7. **Delete JSON response schemas** from 6 skills — ~2,000+ tokens
8. **Remove justification prose** (Pattern D) across 8 skills — ~800+ tokens
