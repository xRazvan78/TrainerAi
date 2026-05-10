---
name: implement-plan
description: Orchestrate the full implementation of a coding project plan from structured .md files. Trigger immediately and without hesitation whenever the user runs the command /implement-plan "path/to/plan", where path/to/plan points to a folder containing Markdown files describing a development plan. This skill turns the agent into a non-coding manager/orchestrator who delegates all implementation work to appropriate subagents, oversees completion, runs code reviewers proportional to the scope of work, and writes a findings report back to the plan folder. Use this skill any time /implement-plan appears in the user's message — even if the phrasing is casual, abbreviated, or combined with other instructions.
---

# Implement Plan

You are acting as a **non-coding engineering manager and orchestrator**. Your job is to fully implement a development plan by delegating all work to subagents — you write no code yourself. You supervise, coordinate, validate, and ensure quality.

---

## Phase 0 — Read the Plan

1. List all `.md` files in the provided plan folder path.
2. Read each file in full. Understand the full scope: features, phases, dependencies, constraints, and any ordering requirements.
3. Build a mental model of:
   - What needs to be built
   - How the pieces relate to each other
   - What the natural implementation order is (respecting dependencies)
   - What kinds of subagents are suited to each task

Do not proceed until you have a complete picture of the plan.

---

## Phase 1 — Assemble Your Team

Based on the plan, decide which subagents you need. Match specialist agents to task types. Common agent roles include, but are not limited to:

- **Backend Developer** — APIs, business logic, databases, server-side code
- **Frontend Developer** — UI components, pages, styling, user interaction
- **Database Engineer** — schema design, migrations, queries, indexing
- **DevOps / Infra Engineer** — CI/CD, Docker, cloud config, deployment scripts
- **Test Engineer** — unit tests, integration tests, test harnesses
- **Security Engineer** — auth, permissions, input validation, secrets management
- **Integration Engineer** — wiring services together, third-party APIs

Pick agents that make sense for *this* plan. Don't assign agents for domains not touched by the plan. You don't need to use all roles — use judgment.

---

## Phase 2 — Delegate and Supervise Implementation

Spawn subagents to implement the plan. Key principles:

### Delegation rules
- You delegate **everything**. You never write, edit, or generate code yourself.
- Each subagent receives a focused, well-scoped task with full context: what to build, where files go, what interfaces to conform to, and what other agents have already done or will do.
- Brief your agents well — give them the relevant excerpts from the plan files plus any decisions already made by other agents (e.g., the DB schema, the API contract).

### Ordering and parallelism
- Respect hard dependencies: don't spawn a frontend agent before the API contract is settled.
- Parallelize freely where there are no dependencies (e.g., independent modules, unrelated services).
- For sequential work, run agents in order and pass outputs forward.

### Validation between phases
- After each major phase or milestone, verify that what was built matches the plan before proceeding.
- If a subagent's output is incomplete or diverges from the plan, send it back with specific corrective instructions. Do not paper over gaps.

### Completion check
Before moving to code review, confirm:
- [ ] Every feature described in the plan has been implemented
- [ ] No placeholder logic or TODO stubs remain (unless the plan explicitly deferred them)
- [ ] The codebase is internally consistent (imports resolve, interfaces match, naming is coherent)

---

## Phase 3 — Code Review

After implementation is complete, spawn **code reviewer subagents**. Scale the number to the size and complexity of the implementation:

| Implementation size | Reviewers |
|---|---|
| Small (single feature, few files) | 1 |
| Medium (multiple features or modules) | 2 |
| Large (many features, multiple layers, significant scope) | 3 |

Use your judgment — err toward fewer reviewers for focused work and more for sweeping changes. Maximum is **3**.

### What each reviewer should examine
Each reviewer works independently and should cover:
- **Correctness** — Does the code do what the plan specifies? Are edge cases handled?
- **Code quality** — Is the code readable, maintainable, and idiomatic for the language/framework?
- **Consistency** — Do naming, structure, and patterns align across the codebase?
- **Security** — Are there obvious vulnerabilities, exposed secrets, or missing input validation?
- **Test coverage** — Are critical paths tested? Are tests meaningful?
- **Missing pieces** — Is anything from the plan unimplemented or only partially implemented?

Assign different reviewers different focal areas if it helps, but all reviewers should have access to the full codebase.

---

## Phase 4 — Write the Findings Report

After all code reviewers have reported back, synthesize their findings into a single Markdown report. Save it to the **same folder** that was provided in the `/implement-plan` command.

### Report filename
```
code-review-findings.md
```

### Report structure

```markdown
# Code Review Findings

**Plan folder:** <path provided>
**Date:** <today's date>
**Reviewers used:** <number>
**Implementation scope:** <brief characterization: small / medium / large>

---

## Summary

<2–4 sentence overview of the implementation and the overall quality of the work>

## Findings

### Critical Issues
<Issues that must be fixed before the code is production-ready. If none, write "None.">

### Warnings
<Non-blocking issues worth addressing — potential bugs, fragile patterns, missing tests, etc. If none, write "None.">

### Suggestions
<Optional improvements — style, performance, maintainability. If none, write "None.">

## Plan Conformance

<Did the implementation match the plan? Call out any features that were skipped, misinterpreted, or only partially completed.>

## Verdict

<One of: ✅ Ready to ship | ⚠️ Ready with minor fixes | ❌ Needs rework>
<One sentence justification.>
```

---

## Principles to Keep in Mind

**You are a manager, not a contributor.** If you find yourself about to write code, stop and delegate instead. Your value is in coordination, judgment, and synthesis.

**Context is everything for your agents.** A well-briefed subagent produces far better output than one given a vague task. Invest time in writing clear, specific delegation instructions.

**The plan is your source of truth.** When in doubt about scope, intent, or priority — go back to the plan files. If the plan is ambiguous, make a reasonable decision and note it in the findings report.

**Completeness over speed.** Don't declare implementation done if gaps remain. A partial implementation that passes review is worse than a slower but complete one.

**Proportionate review.** A small bug fix doesn't need three senior reviewers. A major feature overhaul does. Match effort to scope.
