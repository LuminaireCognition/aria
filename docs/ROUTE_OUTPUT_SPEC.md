# Route Output Constraint Spec

All route-producing outputs (`/route`, `/escape-route`, `/orient` escape routes, `roam_route`) must follow these rules.

## Principle 1: Show Topology, Don't Narrate It

Every named waypoint must include its gate neighbor list with security status. Dead ends, pipes, and hubs are self-evident from the data.

Territory labels derive from sovereignty data:

| Sov Data | Territory Label |
|----------|----------------|
| Alliance in known coalition (`sovereignty.coalition_name` present) | `[TICKER] Alliance — Coalition Name` |
| Alliance without coalition | `[TICKER] Alliance` |
| No sovereignty holder | `NPC Null-sec` |
| No holder + recent sov changes in constellation | `Contested` |

Do not generate behavioral predictions from territory type.

## Principle 2: No Prescriptive Language

Route outputs may contain: system names, security statuses, constellation names, gate neighbors, sovereignty, and timestamped activity numbers. They may NOT contain verbs that prescribe FC behavior. The one permitted imperative is safety-critical warnings derived from data (e.g., "pipe system," "ACTIVE CAMP" from real-time detection).

## Principle 3: Timestamp Volatile Data

Activity figures (NPC kills, ship kills, jumps, gatecamp detections) must include a staleness indicator. Current-hour data shows as-is. Data older than 1 hour shows `(>1h)`.

## Principle 4: Gate Topology Appendix (routes >5 jumps)

Routes with more than 5 waypoints must include a gate topology block listing full gate neighbors (with security status) for: terminus system, dead ends, pipes, and decision points (3+ gates).

**Annotations** (structural facts, not tactical advice):
- `[dead end]` — ≤2 gates with all neighbors on-route
- `[pipe]` — exactly 2 gates, both on-route
- `[hub]` — 5+ gates

## Banned Patterns

| Pattern | Replace With |
|---------|-------------|
| "offers alternate routing options" | Show gate neighbors; FC decides |
| "burn through" / "don't linger" | `pipe (2 gates)` in Notes column |
| "expect caps/supers" | Show NPC kill count |
| "[group] will form/respond" | Show sovereignty |
| "good d-scan checkpoint" | Show gate count |
| "stay aligned" | Omit |
| "your fastest exit is X" | Show escape routes from tool calls only |
| "push deeper after terminus" | Show neighbor topology of terminus |
| "Known camp spot: X gate in Y" | Show real-time gatecamp data if available; otherwise omit |
| Entity claims from training data | Show sovereignty from sov data; omit entity names not in MCP response |
