---
description: Generate a designed HTML explanation of all work completed so far (phases, subphases, steps), saved as Explanation/Explanation_NN.html.
---

# Explainer Command

Produce a self-contained HTML document that explains, to someone who has
not followed the work, **what has been done on this project so far, why
it was done, and where the project stands** — derived from the plans and
the actual repository state, never from assumption.

---

## Required Inputs (read all before writing)

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

## Output File

- Directory: `Explanation/` at the repo root — create it if missing.
- Filename: `Explanation_NN.html` where `NN` is the next free
  two-digit number (`01` if the folder is empty; if `Explanation_01.html`
  and `Explanation_02.html` exist, write `Explanation_03.html`).
  Never overwrite an existing numbered file — each run is a snapshot.
- The file must be **fully self-contained**: all CSS in a `<style>`
  block, all diagrams as inline SVG or pure HTML/CSS. No external
  scripts, stylesheets, fonts, CDNs, or images — it must render
  perfectly offline from a `file://` open in any browser.

---

## Required Content (in this order)

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

## Design Requirements

- Real visual design, not a wall of text: a styled header, section
  cards, status badges, at least one SVG diagram (the progress map;
  additionally an architecture-flow diagram of the target system from
  CLAUDE.md §12.13 is welcome), a progress bar or stat tiles
  (e.g. "phases complete", "steps done in current item").
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

- Do not modify `CLAUDE.md`, `Master_plan.md`, or any plan file.
- Do not include test-file contents or per-test detail (section 7 is a
  tier overview only).
- Be honest about status: unverifiable manual steps (GitHub UI settings)
  are reported as "per checklist / not verifiable from repo", never
  silently assumed done.
- After saving, tell the user: the file path, which phases/steps were
  marked completed, and anything that could not be verified.
