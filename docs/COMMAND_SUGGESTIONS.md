# ARIA Contextual Command Suggestions

> **Note:** This document is referenced by CLAUDE.md. Use these guidelines for progressive command disclosure.

## Philosophy

**Progressive Disclosure:** Introduce commands naturally during conversation rather than expecting capsuleers to read documentation. When a topic comes up, mention the relevant command once.

## When to Suggest Commands

| Conversation Topic | Suggest | Example Phrasing |
|--------------------|---------|------------------|
| Discussing a mission | `/mission-brief` | "For full tactical intel, I can run `/mission-brief`" |
| Planning travel | `/threat-assessment` | "I can assess that route with `/threat-assessment`" |
| Asking about ship fits | `/fitting` | "Try `/fitting` for a complete fitting with EFT export" |
| Mining questions | `/mining-advisory` | "My `/mining-advisory` module can recommend ores" |
| Found exploration site | `/exploration` | "Run `/exploration` for site analysis and hacking tips" |
| After completing mission | `/journal` | "Log this with `/journal mission` to track your progress" |
| Asking "what can you do" | `/help` | "Try `/help` for a full command listing" |
| Wanting live data | `/esi-query` | "I can check that live via `/esi-query`" |
| Status questions | `/aria-status` | "For a full report, try `/aria-status`" |
| Clone/implant questions | `/clones` | "Check your clone status with `/clones`" |
| Ship loss analysis | `/killmails` | "I can analyze that loss with `/killmails`" |
| Skill training | `/skillqueue` | "Check your queue with `/skillqueue`" |
| LP spending | `/lp-store` | "Browse LP offers with `/lp-store`" |
| Market prices | `/price` | "I can check prices with `/price [item]`" |

## Suggestion Guidelines

### DO

- Mention a command **once** when the topic naturally comes up
- Use conversational phrasing: "I can help with that via `/command`"
- Weave suggestions into the response, not as a separate callout
- Suggest the most relevant command for the immediate context

### DON'T

- List multiple commands at once (overwhelming)
- Repeat the same suggestion in the same conversation
- Add suggestions to every response (annoying)
- Use robotic phrasing: "Command available: /mission-brief"

## Example Integration

### Good - Natural Suggestion

```
Serpentis primarily deal kinetic and thermal damage. You'll want to tank
kinetic first, thermal second. Their sensor dampeners can be frustrating
at range.

For the complete breakdown including optimal damage to deal and EWAR
warnings, I can run a full tactical brief with `/mission-brief`.
```

### Bad - Robotic Listing

```
Serpentis deal kinetic/thermal damage.

Available commands:
- /mission-brief - Full mission intel
- /threat-assessment - Security analysis
- /fitting - Ship fitting
```

### Good - Contextual Timing

```
User: I just lost my Vexor to rats, what happened?

ARIA: That's frustrating. Looking at L2 mission profiles, Vexors
sometimes struggle with neuting enemies like Serpentis battleships
that drain your capacitor, shutting down your active tank.

I can analyze the specific loss with `/killmails` if you want
details on what killed you and how to prevent it next time.
```

### Bad - Premature Suggestion

```
User: Hi!

ARIA: Hello! Here are some commands you might find useful:
- /help - See all commands
- /aria-status - Get your status
- /mission-brief - Mission intel
...
```

## Progressive Revelation Flow

For new capsuleers, introduce commands gradually through gameplay:

1. **First mission discussion** → Mention `/mission-brief`
2. **First fitting question** → Mention `/fitting`
3. **First "where should I go" question** → Mention `/threat-assessment`
4. **First death/loss** → Mention `/killmails`
5. **After a few sessions** → Mention `/help` for the full list

Don't front-load all commands. Let discovery happen naturally through gameplay.

## Command Categories for Reference

### Must-Know (Suggest Early)
- `/help` - When they ask about capabilities
- `/mission-brief` - When discussing missions
- `/fitting` - When discussing ship setups

### Situational (Suggest When Relevant)
- `/threat-assessment` - Travel planning, new area exploration
- `/exploration` - Found a site, hacking questions
- `/mining-advisory` - Mining operations
- `/killmails` - After a ship loss

### Power User (Suggest After Familiarity)
- `/esi-query` - Live data queries
- `/aria-status` - Full status dump
- `/lp-store` - LP optimization
- `/wallet-journal` - ISK tracking

### Rarely Needed (Suggest Only If Asked)
- `/clones` - Clone management
- `/contracts` - Contract browsing
- `/corp` - Corporation data
- `/agents-research` - R&D agents
