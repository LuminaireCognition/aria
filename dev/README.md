# ARIA Development

This directory contains development lifecycle artifacts for the ARIA project.

## Structure

```
dev/
├── adr/                 # Architecture Decision Records
│   └── 00X-*.md         # Numbered decisions with rationale
│
├── stp/                 # Skill Tracking Plans
│   ├── active/          # Currently in progress
│   ├── completed/       # Finished STPs
│   └── proposed/        # Under consideration
│
├── proposals/           # Feature proposals and RFCs
│   └── *.md             # Proposal documents
│
├── reviews/             # Code reviews and audits
│   └── *.md             # Review documents
│
├── planning/            # Task tracking and roadmaps
│   ├── TODO.md          # Current tasks
│   └── TODO_SECURITY.md # Security-specific tasks
│
├── archive/             # Historical documents
├── decisions/           # Design decisions (pre-ADR)
├── design/              # Design documents
└── plans/               # Implementation plans
```

## Workflow

### Architecture Decision Records (ADRs)

ADRs document significant architectural decisions. See `adr/README.md` for the template and process.

### Skill Tracking Plans (STPs)

STPs track the implementation of new skills/features:

1. Create proposal in `stp/proposed/`
2. Move to `stp/active/` when work begins
3. Move to `stp/completed/` when done

### Proposals

Feature proposals go through this lifecycle:

1. Draft proposal in `proposals/`
2. Review and iterate
3. Accept → Create ADR if architectural, or STP if implementation
4. Archive completed proposals

## Key Documents

- `DESIGN.md` - Overall architecture and design philosophy
- `RELEASE.md` - Release process and checklist
- `PROMPT_INJECTION_HARDENING.md` - Security considerations
