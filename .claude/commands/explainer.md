---
description: Generate a designed HTML explanation, saved under Explanation/. No argument = all work completed so far (phases, subphases, steps); with a file/folder path argument = a focused explanation of that target.
argument-hint: [file-or-folder]
---

# Explainer Command

Argument: `$ARGUMENTS`

Two modes, chosen by the argument above:

- **Project mode** (argument empty) — explain, to someone who has not
  followed the work, **what has been done on this project so far, why it
  was done, and where the project stands** — derived from the plans and
  the actual repository state, never from assumption.
- **Target mode** (argument is a file or folder name/path) — explain
  **that target**: what it is, why it exists, how it works, and how it
  fits into the project. Resolve the argument to a real path first
  (exact path, else search the repo for a matching file/folder name); if
  nothing matches, say so and list close candidates — never guess.

Sections below marked *(project mode)* or *(target mode)* apply to one
mode only; unmarked sections apply to both.

---

## Required Inputs (project mode — read all before writing)

1. `CLAUDE.md` — the authoritative build guide (phases, architecture,
   goals). Source for *purpose* language: why each phase/step exists.
2. `.claude/plans/Master_plan.md` — the execution roadmap (phase → work
   items → gates).
3. Every `.claude/plans/phase_*.md` file — the detailed plans for work
   that has been planned so far.
4. The actual repository state — this determines what counts as
   **completed**:
   - `git log --oneline` and `git status` (commits made, branch, remote)
   - files that exist on disk vs. files each plan says should exist
   - repo settings work (remote, protection) only if evidenced (e.g.
     `git remote -v`, merge history) — otherwise mark "not verifiable
     from the repo; per plan checklist".

**Ground rule:** a step is "completed" only if the repository shows it
(file exists, commit exists, remote configured). A plan existing is NOT
completion of the work it plans — planning and implementation are
tracked as separate accomplishments.

---

## Required Inputs (target mode — read all before writing)

1. **The target itself** — read the file in full; for a folder, list its
   tree and read every file in it (skim only if a file is very large or
   generated, e.g. a lockfile — then describe structure, not every line).
2. `CLAUDE.md` and any `.claude/plans/*.md` that mention the target —
   source for *why* it exists and which phase/work item it belongs to.
3. `git log --oneline -- <target>` — when it was introduced/changed and
   by which commits.
4. Its neighbors — anything that imports/reads/configures the target or
   that the target depends on, enough to explain its role accurately.

**Ground rule:** explain what the target actually contains, not what a
plan says it should contain. Where the two differ, call out the gap
explicitly.

---

## Output File

- Directory: `Explanation/` at the repo root — create it if missing.
- Filename:
  - Project mode: `Explanation_NN.html`
  - Target mode: `Explanation_<slug>_NN.html`, where `<slug>` is the
    target's base name lowercased with non-alphanumerics replaced by `_`
    (e.g. `pyproject.toml` → `pyproject_toml`, `data_generator/` →
    `data_generator`).
  - In both cases `NN` is the next free two-digit number for that exact
    filename pattern (`01` if none exist; if `..._01.html` and
    `..._02.html` exist, write `..._03.html`).
  Never overwrite an existing numbered file — each run is a snapshot.
- The file must be **fully self-contained**: all CSS in a `<style>`
  block, all diagrams as inline SVG or pure HTML/CSS. No external
  scripts, stylesheets, fonts, CDNs, or images — it must render
  perfectly offline from a `file://` open in any browser.

---

## Required Content — project mode (in this order)

1. **Header** — project name, snapshot date, current git branch +
   latest commit (if any), and a one-paragraph plain-language summary of
   what this project is (from CLAUDE.md §1).
2. **Purpose section** — why this project exists and why the work done
   so far was done first (bootstrap-before-code rationale, workflow-from-
   commit-1 rule, etc.). Written for a reader who knows software but not
   this repo.
3. **Overall progress map** — a diagram (inline SVG or styled HTML)
   showing all phases 0–7 as a pipeline, each colored by status:
   completed / in progress / planned / not started. Include a legend.
4. **Phase & subphase breakdown** — for every phase that has any
   activity (a plan file, or implemented work): its subphases/work items
   and their steps, each with a status badge (✅ done, 🔄 in progress,
   📋 planned only, ⬜ not started), *what* the step does, and *why it
   matters* (one or two sentences each — brief, not the full plan).
   Steps with no activity at all may be collapsed into a single
   "not started" row per phase.
5. **What exists in the repo right now** — a short annotated file tree
   of actual committed/on-disk artifacts and one line each on their role.
6. **Design decisions so far** — briefly restate the notable decisions
   from the plan files (e.g. public repo, phased branch protection,
   PDF gitignored, squash-only merges) with their one-line rationale.
7. **Testing approach (brief)** — describe only the *kinds* of tests the
   project will use (the four tiers: unit, integration, pipeline,
   end-to-end, and what each tier is for, plus behavioral/manual checks
   for infrastructure work). Do **not** list test files, test cases, or
   per-test details.
8. **What's next** — the immediate next work item(s) per Master_plan and
   the not-yet-met acceptance criteria of the current item.

---

## Required Content — target mode (in this order)

1. **Header** — target path, file/folder badge, snapshot date, current
   git branch + the target's latest commit (or "uncommitted"), and a
   one-paragraph plain-language summary of what the target is.
2. **Purpose** — why this target exists: the problem it solves, which
   phase/work item it belongs to, and what breaks or degrades without it.
   Written for a reader who knows software but not this repo.
3. **Where it fits** — a small diagram (inline SVG or styled HTML)
   placing the target in the project's data/dependency flow: what feeds
   it, what consumes it, what configures it.
4. **Contents walkthrough** —
   - File: section-by-section (or class/function-by-function)
     explanation of what each part does and why it's there. Quote short
     key excerpts, don't reproduce the whole file.
   - Folder: an annotated tree, one line per entry, then a subsection
     per significant file with the same treatment as above.
5. **Design decisions** — non-obvious choices embedded in the target
   (e.g. a deliberately missing section, a pinned version, an ignore
   rule) with their one-line rationale from the plans; mark anything
   with no documented rationale as such.
6. **Current status & gaps** — how the target compares to what the
   plans say it should be: done / partial / drifted, with specifics.
7. **How to verify it** — the concrete commands or checks that prove
   the target works (e.g. for `pyproject.toml`: `uv sync`, `uv lock
   --check`; for a module: its test command). Only include checks that
   actually apply.

---

## Design Requirements

- Real visual design, not a wall of text: a styled header, section
  cards, status badges, at least one SVG diagram (project mode: the
  progress map — additionally an architecture-flow diagram of the target
  system from CLAUDE.md §12.13 is welcome; target mode: the "where it
  fits" diagram), a progress bar or stat tiles (project mode: e.g.
  "phases complete", "steps done in current item"; target mode: e.g.
  "lines / sections / last touched").
- Clean typography via system font stacks; consistent spacing; a small,
  coherent color palette with sufficient contrast; tables styled, not
  browser-default.
- Support both light and dark reading: either design on a neutral light
  theme that remains legible everywhere, or add a
  `@media (prefers-color-scheme: dark)` variant.
- Wide elements (trees, tables, diagrams) must scroll horizontally
  inside their own container, never the whole page.
- Keep the document skimmable: status is visible at a glance from
  badges/colors; prose explains, never pads.

---

## Rules

- Do not modify `CLAUDE.md`, `Master_plan.md`, any plan file, or (in
  target mode) the target itself — this command only ever writes under
  `Explanation/`.
- Do not include test-file contents or per-test detail (project-mode
  section 7 is a tier overview only).
- Be honest about status: unverifiable manual steps (GitHub UI settings)
  are reported as "per checklist / not verifiable from repo", never
  silently assumed done.
- Target mode: if the argument matches nothing on disk, produce no HTML
  — report the failed lookup and the closest matching paths instead.
- After saving, tell the user: the file path; project mode — which
  phases/steps were marked completed and anything that could not be
  verified; target mode — what was explained and any plan-vs-reality
  gaps found.
