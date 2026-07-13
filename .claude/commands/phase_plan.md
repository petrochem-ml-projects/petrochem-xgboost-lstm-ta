---
description: Generate a detailed implementation plan for a project phase or a phase subsection.
argument-hint: <phase> [subsection]
---

# Phase Planning Command

Generate a detailed implementation plan for **phase `$1`**, subsection `$2`.

Raw arguments as typed: `$ARGUMENTS`

- If the phase/subsection fields above are empty or look malformed, parse
  them from the raw arguments instead — accept `<phase> <subsection>`,
  `<phase>.<subsection>` (e.g. `0.1` = phase 0, subsection 1), or a bare
  `<phase>`.
- If no subsection was given, plan the **entire phase**.
- Otherwise, plan **only that subsection**, identifying prerequisites from
  earlier subsections or phases.

Phase-to-document mapping: Phase N's build guide lives in CLAUDE.md
section §(N+3) (Phase 1 → §4, Phase 2 → §5, … Phase 7 → §10). Phase 0 is
the repo bootstrap, covered by §3 and §12. A subsection number M refers to
the numbered build step within that phase's guide (e.g. phase 1
subsection 7 → §4.7).

---

## Required Inputs

Before generating the plan, read the following completely:

1. `CLAUDE.md`
   - This is the authoritative implementation specification.
   - Follow its architecture, interfaces, contracts, coding standards, implementation guidelines, testing strategy, and acceptance criteria.
   - Use the requested phase and subsection to determine the relevant implementation requirements.

2. `.claude/plans/Master_plan.md`
   - This is the project's execution roadmap.
   - Use it to determine:
     - the work items belonging to the requested phase,
     - dependencies,
     - implementation order,
     - milestones,
     - completion criteria.
   - **If this file does not exist**, note it as a missing prerequisite in
     the plan and derive the work-item breakdown from CLAUDE.md alone —
     do not block on it and do not invent its contents.

3. Inspect the current repository.
   Determine:

   - what has already been implemented,
   - which previous phase tasks are complete,
   - missing prerequisites,
   - partially completed work,
   - architecture deviations,
   - technical debt that affects this phase.

Always build on the current repository state instead of assuming a clean project.

---

# Required Plan Structure

## 1. Objective

Describe:

- purpose of the phase
- business objective
- deliverables
- scope
- out-of-scope items

---

## 2. Repository Assessment

Summarize the current repository.

Include:

- completed prerequisites
- partially completed work
- missing prerequisites
- files that already exist
- reusable components
- blockers
- technical debt relevant to this phase

---

## 3. Requirements

Summarize the requirements extracted from:

- CLAUDE.md
- `.claude/plans/Master_plan.md` (if present)

Do not invent requirements.

---

## 4. Detailed Implementation Plan

Break the implementation into logical tasks.

For every task include:

- objective
- implementation order
- files to create
- files to modify
- classes
- functions
- method signatures
- interfaces
- models
- configuration
- validation
- algorithms
- logging
- exception handling
- dependencies

Implementation order must be explicit.

---

## 5. Detailed Step-by-Step Execution

For every task provide detailed implementation steps.

Each step should be sufficiently detailed that another engineer can implement it without ambiguity.

Include:

- files to edit
- code components
- responsibilities
- interactions with other modules
- expected outputs
- validation checks

Avoid implementation code.

---

## 6. Design Decisions

Document every design choice.

Include:

- available options
- selected approach
- rationale
- trade-offs

---

## 7. Testing Strategy

Specify:

- Unit tests
- Integration tests
- Pipeline tests
- End-to-End tests

For each include:

- test files
- scenarios
- edge cases
- failure cases
- expected outcomes

---

## 8. Acceptance Criteria

Convert the Definition of Done into measurable verification points.

Every acceptance criterion should be objectively testable.

---

## 9. Pull Request Plan

Split the implementation into logical squash-merge pull requests.

For each PR include:

- Conventional Commit title
- scope
- affected files
- review focus

---

## Planning Principles

The generated plan must:

- strictly follow CLAUDE.md
- strictly follow `.claude/plans/Master_plan.md` (when it exists)
- respect existing repository structure
- avoid duplicate work
- identify missing prerequisites
- remain implementation-ready
- be detailed enough for another engineer to execute without additional planning

Do not generate implementation code.

---

## Output

Save the generated plan as:

- `.claude/plans/phase_$1.md` for a complete phase

or

- `.claude/plans/phase_$1_$2.md` for a subsection plan.

Create `.claude/plans/` if it does not exist.

Do not modify:

- `CLAUDE.md`
- `.claude/plans/Master_plan.md`

After saving the plan:

1. Summarize the generated plan.
2. List any missing prerequisites.
3. Report the saved file path.
