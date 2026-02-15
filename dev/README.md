# ARIA Development

This directory contains development lifecycle artifacts for the ARIA project.

## Structure

```
dev/
├── prompts/             # Review prompt library (standalone toolkit)
│   ├── architecture/    # System design, MCP, Python, LLM integration
│   ├── security/        # AI audit, supply chain
│   ├── testing/         # Test harness, coverage quality
│   ├── cicd/            # Pipeline quality, release & rollback
│   ├── docs/            # Onboarding & first-run UX
│   ├── ux/              # Product interaction UX analysis
│   ├── repo/            # GitHub first impression
│   ├── dev/             # Pre-merge, post-merge, proposal readiness
│   └── meta/            # Scoring rubric (shared reference)
│
├── stp/                 # Skill Tracking Plans
│   ├── active/          # Currently in progress
│   ├── completed/       # Finished STPs
│   └── proposed/        # Under consideration
│
├── proposals/           # Feature proposals and RFCs
│   ├── *.md             # Active proposals
│   └── archive/         # Implemented, superseded, or consolidated
│
├── reviews/             # Code reviews and audits
├── planning/            # Task tracking and roadmaps
├── archive/             # Historical documents (pre-proposal era)
├── decisions/           # Design decisions
├── design/              # Design documents
├── plans/               # Implementation plans
├── playbooks/           # Operational playbooks
├── scripts/             # Development scripts
├── spikes/              # Technical spikes and experiments
├── evidence/            # Supporting evidence for decisions
└── mechanics/           # Game mechanics documentation
```

## Finding Things

| I want to... | Look in |
|--------------|---------|
| Add a new skill | `dev/docs/CONTRIBUTING_SKILLS.md` |
| Add a new persona | `dev/docs/CONTRIBUTING_PERSONAS.md` |
| Add an MCP dispatcher action | `dev/docs/MCP_DEVELOPMENT.md` |
| Understand test tiers | `dev/docs/TESTING.md` |
| See design decisions | `dev/decisions/` |
| Find a past proposal | `dev/proposals/archive/` |
| Check typing progress | `dev/docs/TYPING_ROADMAP.md` |
| Set up dev environment | `dev/docs/GETTING_STARTED.md` |
| Run a code review | `dev/prompts/README.md` |
| Understand data sources | `dev/docs/DATA_SOURCES.md` |
| Read AI runtime rules | `dev/docs/ai-runtime/README.md` |
| Release a new version | `dev/RELEASE.md` |
| Run a doc freshness audit | `dev/docs/DOC_FRESHNESS.md` |

## Review Prompt Library

The `prompts/` directory contains standalone review prompts for evaluating code quality. Give any prompt to an AI coding agent with full codebase access to produce a structured, severity-ranked report.

See [`prompts/README.md`](prompts/README.md) for the full catalog and usage guide.

## Workflow

### Skill Tracking Plans (STPs)

STPs track the implementation of new skills/features:

1. Create proposal in `stp/proposed/`
2. Move to `stp/active/` when work begins
3. Move to `stp/completed/` when done

### Proposals

Feature proposals go through this lifecycle:

1. Draft proposal in `proposals/`
2. Review and iterate
3. Accept → Create STP if implementation-focused
4. Archive completed proposals in `proposals/archive/`

## Key Documents

- `RELEASE.md` - Release process and checklist
- `PROMPT_INJECTION_HARDENING.md` - Security considerations
