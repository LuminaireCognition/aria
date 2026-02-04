# Persona-Driven Discord Notifications Proposal

## Executive Summary

ARIA's current Discord notification system delivers **tactical data**—system name, ship lost, attacker count, ISK value. While useful, these notifications are indistinguishable from any zkillboard mirror. Pilots receive raw intel without context, pattern recognition, or the personality that makes ARIA distinctive.

This proposal introduces **persona-driven commentary** for Discord notifications. When interesting patterns emerge (repeat attackers, unusual losses, activity spikes), ARIA generates optional contextual commentary in the active pilot's persona voice. A gank fleet's third miner kill becomes not just data, but tactical insight delivered with personality.

**Key capabilities:**

| Capability | Current State | Proposed |
|------------|---------------|----------|
| Notification content | Template-based data | Data + optional LLM commentary |
| Pattern recognition | None | Repeat attackers, activity spikes, unusual events |
| Persona integration | None | Full persona voice (ARIA, PARIA, custom) |
| Webhook routing | Single webhook | Per-region/per-trigger webhook routing |
| Commentary warrant | N/A | Strict warrant check—only when genuinely interesting |

**Design principle:** Commentary is additive, not blocking. Tactical data fires immediately via template. LLM commentary, when warranted, arrives as a follow-up or inline addition with minimal latency impact.

---

## Problem Statement

### Current Notification Experience

```
⚠️ INTEL: Aunsou
Retriever down • 3 attackers (SAFETY.)
12.4M ISK • 2 min ago
https://zkillboard.com/kill/12345678/
```

This notification tells **what** happened but provides no:
- **Pattern context:** Is this the first kill or the fifth in an hour?
- **Tactical assessment:** Is this a roaming gang or a stationary camp?
- **Actionable guidance:** Should I dock up? Change route?
- **Personality:** Could be from any zkill bot

### What Pilots Want

When a pilot configures ARIA to watch Verge Vendor, they want intel that feels like it comes from their tactical assistant—not a data feed.

**Scenario: Third miner gank in Aunsou**

*Current notification:*
> ⚠️ INTEL: Aunsou
> Retriever down • 3 attackers (SAFETY.)
> 12.4M ISK • 2 min ago

*Desired notification:*
> ⚠️ INTEL: Aunsou
> Retriever down • 3 attackers (SAFETY.)
> 12.4M ISK • 2 min ago
>
> ---
> *Third mining barge SAFETY's popped in Aunsou this hour. They're running a gank rotation—dock up or tank up.*

**Scenario: Nothing interesting (single kill, no pattern)**

Same format as today—no commentary. The system should know when to stay quiet.

### Design Constraints

1. **Latency sensitivity:** Discord notifications must fire quickly. LLM calls add latency.
2. **Token cost:** Generating commentary for every kill is expensive and noisy.
3. **Warrant requirement:** Commentary should only appear when genuinely insightful.
4. **Persona consistency:** Voice must match the pilot's configured persona.
5. **Graceful degradation:** LLM unavailability must not break core notifications.

---

## Proposed Solution

### Architecture Overview

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Kill Processor │────▶│ Pattern Detector │────▶│ Commentary      │
│                 │     │ (Local analysis) │     │ Evaluator       │
└─────────────────┘     └──────────────────┘     └─────────────────┘
         │                       │                        │
         │                       │                        ▼
         │                       │              ┌─────────────────┐
         │                       │              │ Warrant Check   │
         │                       │              │ (Is commentary  │
         │                       │              │  warranted?)    │
         │                       │              └─────────────────┘
         │                       │                        │
         │                       │                   Yes? │ No?
         │                       │                        │
         ▼                       ▼                        ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ Template        │     │ Pattern Context  │     │ Skip Commentary │
│ Formatter       │────▶│ (for LLM)        │────▶│ (template only) │
│ (Immediate)     │     └──────────────────┘     └─────────────────┘
└─────────────────┘              │
         │                       ▼
         │              ┌──────────────────┐
         │              │ LLM Commentary   │
         │              │ Generator        │
         │              │ (Claude API)     │
         │              └──────────────────┘
         │                       │
         ▼                       ▼
┌─────────────────────────────────────────────┐
│           Webhook Router                     │
│  (Routes to appropriate Discord channel)     │
└─────────────────────────────────────────────┘
```

### Delivery Strategy: Inline vs Follow-up

**Option A: Inline Commentary (Recommended)**

Single Discord message with commentary appended after a horizontal rule:

```
⚠️ INTEL: Aunsou
Retriever down • 3 attackers (SAFETY.)
12.4M ISK • 2 min ago
https://zkillboard.com/kill/12345678/

───────────────────────────
Third mining barge SAFETY's popped in Aunsou this hour.
They're running a gank rotation—dock up or tank up.
                                             — ARIA
```

**Pros:**
- Single notification = less noise
- Context immediately visible
- Cleaner UX

**Cons:**
- LLM latency delays entire notification (mitigated by parallel processing)

**Option B: Follow-up Commentary**

Template notification fires immediately; commentary follows as a second message if warranted.

**Pros:**
- Zero latency on critical data
- LLM can take its time

**Cons:**
- Two notifications for one event
- Commentary may arrive seconds later (confusing)
- More notification fatigue

**Decision:** Option A (inline) with **parallel LLM invocation**. Start LLM call alongside template formatting; if LLM completes within timeout (3s), include commentary; otherwise, send template-only.

---

## Component Design

### 1. Multi-Webhook Router

Route notifications to different Discord channels based on region or trigger type.

**Configuration:**

```json
{
  "redisq": {
    "notifications": {
      "webhooks": {
        "verge_vendor": {
          "url": "https://discord.com/api/webhooks/.../...",
          "regions": [10000068],
          "triggers": ["watchlist_activity", "gatecamp_detected", "high_value"]
        },
        "the_forge": {
          "url": "https://discord.com/api/webhooks/.../...",
          "regions": [10000002],
          "triggers": ["gatecamp_detected"]
        },
        "high_value_anywhere": {
          "url": "https://discord.com/api/webhooks/.../...",
          "regions": [],
          "triggers": ["high_value"],
          "min_value": 5000000000
        }
      },
      "default_webhook_url": "https://discord.com/api/webhooks/.../..."
    }
  }
}
```

**Routing Logic:**

```python
def route_notification(
    kill: ProcessedKill,
    trigger_result: TriggerResult,
    config: NotificationConfig,
) -> list[WebhookTarget]:
    """
    Determine which webhooks should receive this notification.

    A kill may match multiple webhooks (e.g., high-value in Verge Vendor
    matches both "verge_vendor" and "high_value_anywhere").
    """
    targets = []
    kill_region = get_region_for_system(kill.solar_system_id)

    for name, webhook_config in config.webhooks.items():
        # Check region match (empty list = all regions)
        if webhook_config.regions and kill_region not in webhook_config.regions:
            continue

        # Check trigger match
        if not any(t.value in webhook_config.triggers for t in trigger_result.triggers):
            continue

        # Check value threshold if configured
        if webhook_config.min_value and kill.total_value < webhook_config.min_value:
            continue

        targets.append(WebhookTarget(
            name=name,
            url=webhook_config.url,
        ))

    # Fall back to default if no specific match
    if not targets and config.default_webhook_url:
        targets.append(WebhookTarget(
            name="default",
            url=config.default_webhook_url,
        ))

    return targets
```

**Deduplication:**

If multiple webhooks point to the same URL (user error), deduplicate before sending.

---

### 2. Pattern Detection Engine

Identify interesting patterns that warrant commentary.

**Pattern Types:**

| Pattern | Detection Logic | Commentary Warrant |
|---------|-----------------|-------------------|
| **Repeat attacker** | Same attacker corp/alliance appears in 3+ kills within 1 hour in same system | High |
| **Gank rotation** | Known gank corp (SAFETY, CODE.) with 3+ kills in 1 hour | High |
| **Activity spike** | Kills in system exceed 2x historical average (same hour, same day of week) | Medium |
| **Unusual victim** | Capital/faction ship in highsec, or expensive hauler (>1B) | Medium |
| **Security transition** | First lowsec kill after pilot entered from highsec | Medium |
| **War target activity** | Watched war target has 2+ kills in operational region | High |

**Pattern Context Object:**

```python
@dataclass
class PatternContext:
    """Context collected for potential LLM commentary."""

    kill: ProcessedKill
    system_name: str
    ship_name: str
    attacker_group: str | None

    # Detected patterns
    patterns: list[DetectedPattern]

    # Historical context
    same_attacker_kills_1h: int
    same_system_kills_1h: int
    historical_avg_kills_1h: float

    # Watchlist context
    is_watched_entity: bool
    watched_entity_names: list[str]

    # Gatecamp context
    is_active_gatecamp: bool
    gatecamp_kill_count: int

    def warrant_score(self) -> float:
        """
        Calculate how warranted commentary is (0.0 - 1.0).

        Used by the warrant checker to decide if LLM should be invoked.
        """
        score = 0.0

        for pattern in self.patterns:
            score += pattern.weight

        # Normalize to 0-1 range
        return min(score, 1.0)


@dataclass
class DetectedPattern:
    """A single detected pattern."""

    pattern_type: str  # "repeat_attacker", "gank_rotation", etc.
    description: str   # Human-readable description
    weight: float      # Contribution to warrant score (0.0 - 0.5)
    context: dict      # Pattern-specific context for LLM
```

**Pattern Detector Implementation:**

```python
class PatternDetector:
    """Detects interesting patterns in kill activity."""

    def __init__(self, threat_cache: ThreatCache):
        self.threat_cache = threat_cache
        # Known gank corps (could be configurable)
        self.known_gank_corps = {
            98506879,  # SAFETY.
            98326526,  # CODE.
            # ... more
        }

    async def detect_patterns(
        self,
        kill: ProcessedKill,
        entity_match: EntityMatchResult | None,
    ) -> PatternContext:
        """
        Analyze a kill and detect interesting patterns.

        Returns PatternContext with all detected patterns and
        historical context for potential LLM commentary.
        """
        patterns = []

        # Get recent kills in same system
        recent_kills = await self.threat_cache.get_recent_kills(
            system_id=kill.solar_system_id,
            since_minutes=60,
        )

        # Pattern: Repeat attacker
        attacker_kill_count = sum(
            1 for k in recent_kills
            if set(k.attacker_corps) & set(kill.attacker_corps)
        )
        if attacker_kill_count >= 3:
            patterns.append(DetectedPattern(
                pattern_type="repeat_attacker",
                description=f"Same attackers have {attacker_kill_count} kills here in the last hour",
                weight=0.4,
                context={"kill_count": attacker_kill_count},
            ))

        # Pattern: Gank rotation (known gank corp + multiple kills)
        is_gank_corp = bool(set(kill.attacker_corps) & self.known_gank_corps)
        if is_gank_corp and attacker_kill_count >= 2:
            patterns.append(DetectedPattern(
                pattern_type="gank_rotation",
                description="Known ganking organization running active operation",
                weight=0.5,
                context={"is_gank_corp": True, "kill_count": attacker_kill_count},
            ))

        # Pattern: Unusual victim (high value in unexpected context)
        if self._is_unusual_victim(kill):
            patterns.append(DetectedPattern(
                pattern_type="unusual_victim",
                description=self._describe_unusual_victim(kill),
                weight=0.3,
                context={"value": kill.total_value},
            ))

        # Pattern: War target activity
        if entity_match and entity_match.has_match:
            war_kills = await self._count_war_target_kills(
                entity_match.matched_entities,
                since_minutes=60,
            )
            if war_kills >= 2:
                patterns.append(DetectedPattern(
                    pattern_type="war_target_activity",
                    description=f"War target has {war_kills} kills in your operational area",
                    weight=0.5,
                    context={"kill_count": war_kills},
                ))

        # Build full context
        return PatternContext(
            kill=kill,
            system_name=await self._resolve_system_name(kill.solar_system_id),
            ship_name=await self._resolve_ship_name(kill.victim_ship_type_id),
            attacker_group=await self._resolve_primary_attacker(kill),
            patterns=patterns,
            same_attacker_kills_1h=attacker_kill_count,
            same_system_kills_1h=len(recent_kills),
            historical_avg_kills_1h=await self._get_historical_avg(kill.solar_system_id),
            is_watched_entity=entity_match.has_match if entity_match else False,
            watched_entity_names=entity_match.matched_entity_names if entity_match else [],
            is_active_gatecamp=False,  # Set from trigger_result
            gatecamp_kill_count=0,
        )
```

---

### 3. Warrant Checker

Determines if a kill warrants LLM commentary.

**Philosophy:** Commentary should be the exception, not the rule. Most kills receive template-only notifications. Commentary is reserved for genuinely interesting situations.

**Warrant Thresholds:**

| Threshold | Commentary Behavior |
|-----------|---------------------|
| < 0.3 | No commentary (template only) |
| 0.3 - 0.5 | Commentary if LLM available and fast |
| > 0.5 | Always attempt commentary (with timeout) |

**Implementation:**

```python
class WarrantChecker:
    """Determines if a kill warrants LLM commentary."""

    THRESHOLD_SKIP = 0.3
    THRESHOLD_OPPORTUNISTIC = 0.5

    def __init__(self, config: CommentaryConfig):
        self.config = config

    def should_generate_commentary(
        self,
        pattern_context: PatternContext,
    ) -> CommentaryDecision:
        """
        Decide whether to generate LLM commentary.

        Returns:
            CommentaryDecision with action and reasoning
        """
        score = pattern_context.warrant_score()

        if not self.config.enabled:
            return CommentaryDecision(
                action="skip",
                reason="Commentary disabled in config",
            )

        if score < self.THRESHOLD_SKIP:
            return CommentaryDecision(
                action="skip",
                reason=f"Warrant score {score:.2f} below threshold",
            )

        if score < self.THRESHOLD_OPPORTUNISTIC:
            return CommentaryDecision(
                action="opportunistic",
                reason=f"Warrant score {score:.2f} - attempt if fast",
                timeout_ms=1500,  # Shorter timeout for borderline cases
            )

        return CommentaryDecision(
            action="generate",
            reason=f"Warrant score {score:.2f} - commentary warranted",
            timeout_ms=3000,
        )


@dataclass
class CommentaryDecision:
    action: str  # "skip", "opportunistic", "generate"
    reason: str
    timeout_ms: int = 3000
```

---

### 4. LLM Commentary Generator

Generates persona-aware commentary using Claude API.

**Prompt Engineering:**

```python
COMMENTARY_SYSTEM_PROMPT = """
You are generating a brief tactical commentary for an EVE Online killmail notification.

RULES:
1. Maximum 2 sentences (under 200 characters preferred)
2. Focus on actionable tactical insight, not description
3. Match the persona voice provided
4. Never repeat information already in the notification (ship name, ISK value, etc.)
5. If there's nothing genuinely insightful to add, output exactly: NO_COMMENTARY

PERSONA VOICE:
{persona_voice}

EXAMPLES OF GOOD COMMENTARY:
- "Third miner SAFETY's popped here this hour. They're running a gank rotation."
- "War target's hunting your pipe. Consider the Osmeden bypass."
- "Unusual traffic for this hour—possible fleet forming."

EXAMPLES OF BAD COMMENTARY (too generic, don't do this):
- "Be careful out there."
- "This is a dangerous system."
- "Someone died here."
"""

COMMENTARY_USER_PROMPT = """
KILL NOTIFICATION:
{notification_text}

DETECTED PATTERNS:
{patterns_description}

CONTEXT:
- Same attackers: {same_attacker_kills} kills in last hour
- System activity: {system_kills} kills in last hour (avg: {historical_avg})
- Watched entity: {is_watched}

Generate a brief tactical commentary (or output NO_COMMENTARY if nothing insightful to add):
"""
```

**Implementation:**

```python
class CommentaryGenerator:
    """Generates persona-aware kill commentary using Claude API."""

    def __init__(
        self,
        anthropic_client: Anthropic,
        persona_loader: PersonaLoader,
    ):
        self.client = anthropic_client
        self.persona_loader = persona_loader

    async def generate_commentary(
        self,
        pattern_context: PatternContext,
        notification_text: str,
        timeout_ms: int = 3000,
    ) -> str | None:
        """
        Generate commentary for a kill notification.

        Args:
            pattern_context: Detected patterns and context
            notification_text: The template notification being sent
            timeout_ms: Maximum time to wait for LLM response

        Returns:
            Commentary string, or None if not warranted/timeout
        """
        # Load persona voice
        persona_context = await self.persona_loader.get_active_persona()
        persona_voice = self._extract_voice_guidance(persona_context)

        # Build prompts
        system_prompt = COMMENTARY_SYSTEM_PROMPT.format(
            persona_voice=persona_voice,
        )

        user_prompt = COMMENTARY_USER_PROMPT.format(
            notification_text=notification_text,
            patterns_description=self._format_patterns(pattern_context.patterns),
            same_attacker_kills=pattern_context.same_attacker_kills_1h,
            system_kills=pattern_context.same_system_kills_1h,
            historical_avg=f"{pattern_context.historical_avg_kills_1h:.1f}",
            is_watched="Yes" if pattern_context.is_watched_entity else "No",
        )

        try:
            response = await asyncio.wait_for(
                self._call_claude(system_prompt, user_prompt),
                timeout=timeout_ms / 1000,
            )

            # Check for explicit no-commentary signal
            if response.strip() == "NO_COMMENTARY":
                return None

            return response.strip()

        except asyncio.TimeoutError:
            logger.debug(f"Commentary generation timed out after {timeout_ms}ms")
            return None
        except Exception as e:
            logger.warning(f"Commentary generation failed: {e}")
            return None

    async def _call_claude(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """Make Claude API call."""
        response = await self.client.messages.create(
            model="claude-3-haiku-20240307",  # Fast model for low latency
            max_tokens=100,  # Short responses only
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return response.content[0].text

    def _extract_voice_guidance(self, persona_context: dict) -> str:
        """Extract voice guidance from persona context for prompt."""
        # Load voice.md from persona and extract key guidance
        # This is a summary, not the full file
        # ...
        pass
```

**Model Selection:**

| Model | Latency | Quality | Cost | Recommendation |
|-------|---------|---------|------|----------------|
| claude-3-haiku | ~300ms | Good for short tactical commentary | Low | **Default** |
| claude-3-5-sonnet | ~800ms | Better nuance | Medium | For `rp_level: full` |
| claude-3-opus | ~2000ms | Best quality | High | Not recommended (too slow) |

---

### 5. Persona Integration

Load and apply persona voice to commentary generation.

**Voice Extraction:**

Rather than passing the entire persona context to the LLM (token-expensive), extract a concise voice summary:

```python
@dataclass
class PersonaVoiceSummary:
    """Concise voice guidance for LLM commentary."""

    name: str           # "ARIA", "PARIA", "FORGE"
    tone: str           # "Professional and direct", "Irreverent and sharp"
    address_form: str   # "Capsuleer", "Boss", "Researcher"
    example_phrases: list[str]  # 3-5 characteristic phrases
    avoid: list[str]    # Things this persona doesn't say
```

**Example Voice Summaries:**

```yaml
# ARIA Mk.IV (Empire)
name: ARIA
tone: Professional tactical assistant. Direct, concise, focused on pilot safety.
address_form: Capsuleer
example_phrases:
  - "Recommend caution."
  - "Threat assessment: elevated."
  - "Consider alternate routing."
avoid:
  - Slang or casual language
  - Excessive warnings
  - Emotional language

# PARIA (Pirate)
name: PARIA
tone: Irreverent but competent. Treats danger as opportunity. Dark humor.
address_form: Boss
example_phrases:
  - "Looks like someone found out."
  - "That's a nice killmail. Shame about the cargo."
  - "Your route just got interesting."
avoid:
  - Excessive caution
  - Corporate-speak
  - Moralizing
```

**Integration Point:**

```python
class PersonaLoader:
    """Loads persona context for commentary generation."""

    async def get_voice_summary(self) -> PersonaVoiceSummary:
        """
        Get concise voice summary for active pilot's persona.

        Reads from persona_context in pilot profile, extracts
        key voice characteristics for LLM prompting.
        """
        # 1. Get active pilot
        pilot_dir = await self._resolve_active_pilot()

        # 2. Load profile.md
        profile = await self._load_profile(pilot_dir)

        # 3. Extract persona_context
        persona_context = profile.get("persona_context", {})

        # 4. Check rp_level (skip for "off")
        if persona_context.get("rp_level") == "off":
            return self._default_voice_summary()

        # 5. Load voice summary from persona
        persona_name = persona_context.get("persona", "aria-mk4")
        return await self._load_voice_summary(persona_name)
```

---

### 6. Enhanced Message Formatter

Combines template notification with optional commentary.

```python
class EnhancedMessageFormatter(MessageFormatter):
    """Formats kills with optional persona-driven commentary."""

    def format_kill_with_commentary(
        self,
        kill: ProcessedKill,
        trigger_result: TriggerResult,
        commentary: str | None,
        persona_name: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Format a kill with optional commentary appended.

        Args:
            kill: The processed killmail
            trigger_result: Trigger evaluation result
            commentary: Optional LLM-generated commentary
            persona_name: Persona name for attribution
            **kwargs: Additional formatting args

        Returns:
            Discord webhook payload with commentary section if present
        """
        # Generate base notification
        payload = self.format_kill(kill, trigger_result, **kwargs)

        if commentary:
            # Append commentary section to description
            embed = payload["embeds"][0]

            # Add horizontal rule and commentary
            attribution = f"— {persona_name}" if persona_name else "— ARIA"
            commentary_section = f"\n\n───────────────────────────\n*{commentary}*\n{attribution}"

            embed["description"] += commentary_section

        return payload
```

---

## Implementation Phases

### Phase 6A: Multi-Webhook Routing ✅

**Goal:** Route notifications to different Discord channels based on region/trigger.

**Deliverables:**
- [x] `WebhookRouter` class with routing logic
- [x] Extended configuration schema for multiple webhooks
- [x] Deduplication for same-URL webhooks
- [x] Update `NotificationManager` to use router
- [x] Unit tests for router (26 tests)
- [ ] CLI command to test specific webhook routes
- [ ] Documentation update

**Complexity:** Low-Medium

**Files:**
- `src/aria_esi/services/redisq/notifications/router.py` (new)
- `src/aria_esi/services/redisq/notifications/config.py` (extend)
- `src/aria_esi/services/redisq/notifications/manager.py` (modify)
- `tests/services/redisq/notifications/test_router.py` (new)

### Phase 6B: Pattern Detection Engine ✅

**Goal:** Identify interesting patterns that warrant commentary.

**Deliverables:**
- [x] `PatternDetector` class with detection logic
- [x] `PatternContext` and `DetectedPattern` models
- [ ] Historical average calculation (requires schema extension) — deferred
- [x] Known gank corp configuration
- [x] Unit tests for each pattern type

**Complexity:** Medium

**Schema Extension:**

```sql
-- Track hourly kill averages per system for spike detection
CREATE TABLE system_activity_history (
    system_id INTEGER NOT NULL,
    hour_of_week INTEGER NOT NULL,  -- 0-167 (hour 0 of Sunday to hour 23 of Saturday)
    avg_kills REAL NOT NULL,
    sample_count INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    PRIMARY KEY (system_id, hour_of_week)
);
```

**Files:**
- `src/aria_esi/services/redisq/notifications/patterns.py` (new)
- `src/aria_esi/services/redisq/notifications/models.py` (extend)
- `tests/unit/test_pattern_detection.py` (new)

### Phase 6C: Warrant Checker ✅

**Goal:** Determine when commentary is valuable vs. noise.

**Deliverables:**
- [x] `WarrantChecker` class with threshold logic
- [x] `CommentaryDecision` model
- [x] Configuration for thresholds
- [x] Metrics tracking (commentary rate, skip reasons)
- [x] Unit tests for threshold behavior

**Complexity:** Low

**Files:**
- `src/aria_esi/services/redisq/notifications/warrant.py` (new)
- `tests/services/redisq/notifications/test_warrant.py` (new)

### Phase 6D: LLM Commentary Generator ✅

**Goal:** Generate persona-aware tactical commentary.

**Deliverables:**
- [x] `CommentaryGenerator` class with Claude API integration
- [x] Prompt templates with persona voice injection
- [x] Async timeout handling
- [x] Fallback behavior on API failure
- [x] Rate limiting / cost tracking
- [x] Unit tests with mocked API

**Complexity:** Medium

**Configuration:**

```json
{
  "redisq": {
    "notifications": {
      "commentary": {
        "enabled": true,
        "model": "claude-3-haiku-20240307",
        "timeout_ms": 3000,
        "max_tokens": 100,
        "warrant_threshold": 0.3,
        "cost_limit_daily": 1.00
      }
    }
  }
}
```

**Files:**
- `src/aria_esi/services/redisq/notifications/commentary.py` (new)
- `src/aria_esi/services/redisq/notifications/prompts.py` (new)
- `tests/services/redisq/notifications/test_commentary.py` (new)

### Phase 6E: Persona Integration ✅

**Goal:** Load and apply persona voice to commentary.

**Deliverables:**
- [x] `PersonaLoader` class for notification context
- [x] `PersonaVoiceSummary` model
- [x] Voice summary extraction from persona files (hardcoded summaries)
- [x] Cache for voice summaries (avoid repeated file reads)
- [x] Fallback to default voice when persona unavailable

**Complexity:** Low-Medium

**Files:**
- `src/aria_esi/services/redisq/notifications/persona.py` (new)
- Voice summary definitions in persona directories — deferred (using hardcoded summaries)

### Phase 6F: Integration & Enhanced Formatter ✅

**Goal:** Wire everything together and update the formatter.

**Deliverables:**
- [x] `EnhancedMessageFormatter` with commentary support
- [x] Update `NotificationManager` to orchestrate full pipeline
- [x] Parallel LLM invocation (non-blocking)
- [x] Unit tests
- [ ] Documentation: `docs/PERSONA_NOTIFICATIONS.md` — deferred

**Complexity:** Medium

**Pipeline Orchestration:**

```python
async def process_kill_notification(
    self,
    kill: ProcessedKill,
    trigger_result: TriggerResult,
    entity_match: EntityMatchResult | None,
) -> None:
    """
    Process a kill through the full notification pipeline.

    1. Check throttle
    2. Route to webhooks
    3. Detect patterns
    4. Check commentary warrant
    5. Generate commentary (if warranted, with timeout)
    6. Format and send
    """
    # 1. Throttle check
    if self._throttle.is_throttled(kill.solar_system_id, trigger_result.primary_trigger):
        return

    # 2. Route to webhooks
    targets = self._router.route(kill, trigger_result)
    if not targets:
        return

    # 3. Detect patterns (fast, local)
    pattern_context = await self._pattern_detector.detect_patterns(kill, entity_match)

    # 4. Check warrant
    decision = self._warrant_checker.should_generate_commentary(pattern_context)

    # 5. Start formatting + optional commentary generation in parallel
    format_task = asyncio.create_task(
        self._resolve_names_for_formatting(kill)
    )

    commentary = None
    if decision.action != "skip":
        commentary_task = asyncio.create_task(
            self._generate_commentary_with_timeout(
                pattern_context,
                timeout_ms=decision.timeout_ms,
            )
        )

        # Wait for formatting (required)
        names = await format_task

        # Wait for commentary (optional, with timeout already built in)
        try:
            commentary = await commentary_task
        except Exception:
            commentary = None
    else:
        names = await format_task

    # 6. Format final message
    message = self._formatter.format_kill_with_commentary(
        kill=kill,
        trigger_result=trigger_result,
        commentary=commentary,
        persona_name=self._persona_loader.get_name(),
        **names,
    )

    # 7. Send to all target webhooks
    for target in targets:
        await self._queue.enqueue(WebhookMessage(
            target=target,
            payload=message,
        ))

    # 8. Record throttle
    self._throttle.record(kill.solar_system_id, trigger_result.primary_trigger)
```

---

## Configuration Schema

### Full Configuration Example

```json
{
  "redisq": {
    "enabled": true,
    "notifications": {
      "webhooks": {
        "verge_vendor_intel": {
          "url": "https://discord.com/api/webhooks/1234567890/abcdef...",
          "regions": [10000068],
          "triggers": ["watchlist_activity", "gatecamp_detected", "high_value"]
        },
        "high_value_alerts": {
          "url": "https://discord.com/api/webhooks/0987654321/fedcba...",
          "regions": [],
          "triggers": ["high_value"],
          "min_value": 5000000000
        }
      },
      "default_webhook_url": null,
      "triggers": {
        "watchlist_activity": true,
        "gatecamp_detected": true,
        "high_value_threshold": 1000000000
      },
      "throttle_minutes": 5,
      "quiet_hours": {
        "enabled": true,
        "start": "02:00",
        "end": "08:00",
        "timezone": "America/New_York"
      },
      "commentary": {
        "enabled": true,
        "model": "claude-3-haiku-20240307",
        "timeout_ms": 3000,
        "max_tokens": 100,
        "warrant_threshold": 0.3,
        "cost_limit_daily_usd": 1.00
      }
    }
  }
}
```

### Configuration Validation

```python
@dataclass
class CommentaryConfig:
    enabled: bool = False
    model: str = "claude-3-haiku-20240307"
    timeout_ms: int = 3000
    max_tokens: int = 100
    warrant_threshold: float = 0.3
    cost_limit_daily_usd: float = 1.00

    def validate(self) -> list[str]:
        errors = []
        if self.timeout_ms < 500:
            errors.append("timeout_ms must be >= 500")
        if self.timeout_ms > 10000:
            errors.append("timeout_ms must be <= 10000 (10 seconds)")
        if self.warrant_threshold < 0 or self.warrant_threshold > 1:
            errors.append("warrant_threshold must be between 0 and 1")
        return errors
```

---

## Security Considerations

### API Key Management

The Claude API key for commentary generation must be stored securely:

```json
{
  "anthropic": {
    "api_key": "sk-ant-..."
  }
}
```

**Or via environment variable:**
```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

**Security notes:**
- API key should NOT be in pilot profiles (those are per-user, key is installation-wide)
- Store in `userdata/config.json` which is already gitignored
- Consider keyring integration for sensitive credential storage

### Cost Control

LLM calls have real costs. Built-in safeguards:

1. **Daily cost limit:** Stop generating commentary when limit reached
2. **Warrant threshold:** Only generate for genuinely interesting events
3. **Token limit:** Cap response length to 100 tokens
4. **Model selection:** Default to Haiku (cheapest capable model)

**Cost estimation:**
- Haiku: ~$0.00025 per 1K input tokens, ~$0.00125 per 1K output tokens
- Per commentary: ~500 input tokens, ~50 output tokens = ~$0.0002
- 100 commentaries/day = ~$0.02/day
- Default daily limit: $1.00 (covers high-activity days)

### Prompt Injection

Pattern context comes from kill data (untrusted). Mitigations:

1. **Structured data only:** Pattern context is formatted, not raw text
2. **System prompt boundary:** User prompt is clearly separated
3. **Output validation:** Check for `NO_COMMENTARY` signal, sanitize output

---

## Testing Strategy

### Unit Tests

**Pattern Detection:**
```python
def test_repeat_attacker_detection():
    """Detects when same attacker has multiple kills."""
    kills = [
        make_kill(attacker_corps=[100]),
        make_kill(attacker_corps=[100]),
        make_kill(attacker_corps=[100]),
    ]
    context = detector.detect_patterns(kills[-1], kills[:-1])
    assert any(p.pattern_type == "repeat_attacker" for p in context.patterns)

def test_gank_rotation_requires_known_corp():
    """Gank rotation only triggers for known gank corps."""
    kills = [make_kill(attacker_corps=[999999])]  # Unknown corp
    context = detector.detect_patterns(kills[-1], [])
    assert not any(p.pattern_type == "gank_rotation" for p in context.patterns)
```

**Warrant Checker:**
```python
def test_low_warrant_skips_commentary():
    context = PatternContext(patterns=[], ...)  # No patterns
    decision = checker.should_generate_commentary(context)
    assert decision.action == "skip"

def test_high_warrant_generates_commentary():
    context = PatternContext(
        patterns=[
            DetectedPattern(pattern_type="gank_rotation", weight=0.5, ...),
        ],
        ...
    )
    decision = checker.should_generate_commentary(context)
    assert decision.action == "generate"
```

**Commentary Generator:**
```python
@pytest.mark.asyncio
async def test_commentary_timeout():
    """Returns None when LLM times out."""
    generator = CommentaryGenerator(slow_mock_client)
    result = await generator.generate_commentary(
        pattern_context,
        notification_text="...",
        timeout_ms=100,  # Very short timeout
    )
    assert result is None

@pytest.mark.asyncio
async def test_no_commentary_signal():
    """Respects NO_COMMENTARY response from LLM."""
    mock_client = MockClient(response="NO_COMMENTARY")
    generator = CommentaryGenerator(mock_client)
    result = await generator.generate_commentary(pattern_context, "...")
    assert result is None
```

### Integration Tests

```python
@pytest.mark.integration
async def test_full_notification_pipeline():
    """End-to-end test of notification with commentary."""
    # Setup
    config = load_test_config()
    manager = NotificationManager(config)

    # Create kill with interesting pattern
    kill = make_kill(
        system_id=30002187,  # Aunsou
        attacker_corps=[98506879],  # SAFETY.
    )

    # Pre-populate cache with prior kills (creates pattern)
    for _ in range(3):
        await manager.threat_cache.add_kill(make_kill(
            system_id=30002187,
            attacker_corps=[98506879],
        ))

    # Process notification
    with patch_discord_webhook() as mock_webhook:
        await manager.process_kill(kill, trigger_result, entity_match)

    # Verify commentary was included
    sent_payload = mock_webhook.call_args[1]["json"]
    description = sent_payload["embeds"][0]["description"]
    assert "───────────────────────────" in description  # Has commentary separator
```

### Manual Testing Checklist

- [ ] Commentary appears for repeat attacker scenario
- [ ] No commentary for single isolated kill
- [ ] Commentary matches active persona voice
- [ ] Timeout fallback works (template-only when LLM slow)
- [ ] Multi-webhook routing sends to correct channels
- [ ] Throttling prevents commentary spam
- [ ] Cost limit stops commentary when exceeded
- [ ] Quiet hours suppress notifications entirely

---

## Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Commentary warrant precision | >80% | Manual review: was commentary genuinely useful? |
| Commentary latency (p50) | <500ms | Timestamp logging |
| Commentary latency (p95) | <2000ms | Timestamp logging |
| Timeout rate | <5% | Counter metric |
| Daily cost | <$1.00 | API usage tracking |
| Notification delivery rate | >99% | Compare kills processed vs webhooks sent |
| Persona voice accuracy | >90% | Manual review: does commentary match persona? |

---

## Alternatives Considered

### Alternative 1: Pre-computed Commentary Templates

**Approach:** Write fixed commentary templates for each pattern type.

```python
TEMPLATES = {
    "gank_rotation": "Gank fleet active in {system}. {count} kills this hour.",
    "repeat_attacker": "{attacker} has {count} kills here recently.",
}
```

**Pros:**
- Zero latency
- Zero cost
- Predictable output

**Cons:**
- No personality
- No nuance
- Feels robotic

**Decision:** Rejected. The point is persona-driven commentary, not more templates.

### Alternative 2: Always Generate Commentary

**Approach:** Run LLM for every notification, let it decide if commentary is warranted.

**Pros:**
- Simpler architecture (no warrant checker)
- LLM has full context for decision

**Cons:**
- High cost (every kill = API call)
- Latency on every notification
- LLM may hallucinate patterns

**Decision:** Rejected. Local pattern detection is faster and cheaper for the common case (no commentary).

### Alternative 3: Batch Commentary

**Approach:** Accumulate kills, generate summary commentary every N minutes.

```
📊 Verge Vendor Summary (Last 15 min)
- 3 kills in Aunsou (SAFETY. gank rotation)
- 1 high-value Proteus loss in Dodixie
- War target spotted in Botane
```

**Pros:**
- Reduced notification volume
- More context for LLM
- Lower cost

**Cons:**
- Not real-time
- Loses urgency of immediate alerts
- More complex state management

**Decision:** Interesting for future consideration, but doesn't meet the "real-time intel" requirement.

---

## Future Extensions

### Adaptive Warrant Thresholds

Learn from user engagement (click-through on zkill links, responses in session) to tune warrant thresholds per pilot.

### Commentary Feedback Loop

Allow pilots to thumbs-up/thumbs-down commentary. Use feedback to improve prompt or adjust warrant thresholds.

### Voice Fine-tuning

Train persona-specific adapters or use Claude's style guidance more heavily to improve voice consistency.

### Multi-kill Summaries

When multiple kills arrive in quick succession (fleet fight), generate a summary rather than individual commentaries.

---

## Summary

| Aspect | Current | Proposed |
|--------|---------|----------|
| **Notification content** | Template data only | Data + optional LLM commentary |
| **Pattern awareness** | None | Repeat attackers, gank rotations, spikes |
| **Persona voice** | None | Full persona integration |
| **Webhook routing** | Single webhook | Per-region, per-trigger routing |
| **Commentary cost** | $0 | ~$0.02/day typical, $1/day limit |
| **Commentary latency** | N/A | <500ms p50, <2s p95 |
| **Architecture** | Simple pipeline | Pattern detection → warrant check → LLM → format |

Persona-driven commentary transforms ARIA notifications from data feeds into tactical advisories. Pilots receive not just "what happened" but "what it means"—delivered in the voice of their configured persona. The warrant system ensures commentary appears only when genuinely insightful, avoiding notification fatigue while providing value when it matters.
