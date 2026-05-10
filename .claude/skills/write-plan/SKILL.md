---
name: write-plan
description: >
  Saves a development plan discussed with a planning agent to the filesystem.
  Trigger this skill immediately and without hesitation whenever the user runs the command /write-plan "path",
  where the path is a folder where the plan subfolder should be created.
  The skill creates a descriptively-named subfolder inside the given path, writes each phase of the plan
  as its own Markdown file (phase-1-name.md, phase-2-name.md, etc.), and optionally writes a README.md
  overview if the plan has multiple phases or significant cross-cutting context.
  Always use this skill when the /write-plan command is present — never skip it or summarize inline instead.
---

# write-plan

Saves a fully detailed development plan to the filesystem after it has been discussed with the user in plan mode.

## Trigger

The user runs:

```
/write-plan "path/to/plans-folder"
```

The path is where the new plan subfolder will be created.

---

## Workflow

### 1. Derive the subfolder name

- Look at the plan discussed in the conversation and pick a short, descriptive, lowercase kebab-case name that captures the project or feature (e.g. `auth-refactor`, `payment-gateway-integration`, `user-onboarding-flow`).
- Create the full path: `<user-provided-path>/<subfolder-name>/`

### 2. Decide whether a README is needed

Write a `README.md` if **any** of the following apply:
- The plan has 3 or more phases
- There are cross-cutting concerns, shared conventions, or architectural decisions that apply across phases
- An external reader picking up phase files cold would lack important context without an overview

If the plan is very small (1–2 phases, self-contained), skip the README.

### 3. Write the README.md (if needed)

Include:
- **Project / feature summary**: what is being built and why
- **Goals and success criteria**
- **High-level architecture or design decisions** that span phases
- **Tech stack and dependencies** if relevant
- **Phase overview table**: a quick reference listing each phase file and its purpose
- **Assumptions and constraints**
- **Glossary** (optional, if the domain has non-obvious terminology)

### 4. Write each phase file

Filename format: `phase-<N>-<short-name>.md` (e.g. `phase-1-foundation.md`, `phase-2-api-integration.md`)

Each phase file must be thorough — these files are handed directly to a team of workers who were not part of the planning conversation. Include everything they need:

#### Required sections per phase file

```markdown
# Phase <N>: <Phase Title>

## Overview
What this phase accomplishes and why it comes at this point in the sequence.

## Prerequisites
What must be completed or available before this phase begins (prior phases, environment setup, credentials, etc.).

## Goals
Bulleted list of concrete, verifiable outcomes for this phase.

## Technical Design
Architecture decisions, data models, API contracts, component structure, or any other design details specific to this phase. Be as specific as possible — include field names, types, endpoint signatures, file paths, config keys, etc.

## Implementation Steps
Ordered, granular steps a developer follows to implement this phase. Each step should be actionable without ambiguity. Use sub-steps where needed.

## File & Directory Changes
List every file or directory that will be created, modified, or deleted, with a brief note on what changes.

## Testing & Validation
How to verify this phase is complete. Include unit tests, integration tests, manual checks, or acceptance criteria.

## Edge Cases & Risks
Known edge cases, failure modes, and how to handle them. Flag anything uncertain.

## Notes
Any additional context, references, or decisions recorded for posterity.
```

Omit a section only if it is genuinely not applicable to that phase (e.g. no file changes in a planning-only phase). Never omit it just to save space.

### 5. Output confirmation

After writing all files, confirm to the user:
- The full path of the subfolder created
- The list of files written
- A one-line summary of each phase

---

## File naming conventions

| Item | Format | Example |
|---|---|---|
| Subfolder | `kebab-case` | `payment-gateway-integration` |
| Phase files | `phase-<N>-<name>.md` | `phase-1-foundation.md` |
| Overview | `README.md` | `README.md` |

---

## Quality bar

The plan files are the single source of truth for the workers implementing the feature. Write them as if you will not be available to answer follow-up questions. Err on the side of more detail, not less. Every implementation step should be specific enough that a competent developer can execute it without re-reading the planning conversation.
