# Phase 0 · Item 0.4 implementation plan — GitHub process

Authoritative sources: `.claude/plans/Master_plan.md` Phase 0, work item 0.4; `CLAUDE.md` §12.3 (ownership/CODEOWNERS), §12.4 (git workflow & branch protection), §12.5 (PR template), §12.17 (labels/Milestones/ Projects board), §12.12 (release-per-milestone linkage).

Scope note: Master_plan item 0.4 covers exactly — `CODEOWNERS`, the PR template, the label taxonomy, Milestones 1–7, the Kanban board, plus the squash-only ruleset hardening deferred from 0.1/0.3 (tracked in issue #1). CI and required status checks are 0.5; nothing here touches Python code.

---

## 1. Objective

**Purpose.** Give the three-account workflow its enforcement teeth: reviewer routing that fires automatically (`CODEOWNERS`), a PR body structure that stops being copy-paste discipline and becomes a template, one label taxonomy instead of GitHub's defaults, Milestones that make the Phase 1–7 roadmap navigable, a Kanban board for §12.17's Backlog→Done flow, and a ruleset that *prevents* non-squash merges instead of relying on the merger remembering.

**Business objective.** From Phase 1 onward the team splits across modules (§12.3) and PR volume rises. Every piece of process that is manual today (choosing reviewers, writing PR sections, picking the squash button) becomes automatic or enforced, so Phase 1+ PRs carry zero process overhead.

**Deliverables.**

- `.github/CODEOWNERS` with the three real usernames (ordering corrected for GitHub's last-match-wins semantics — see D1)
- `.github/pull_request_template.md` per §12.5
- Label set: `type:*` (6), `priority:p0–p3` (4), `phase:1–7` (7) — completing the two already created in 0.3
- Milestones: `Phase 1` … `Phase 7`, each description linking the matching CLAUDE.md Definition-of-Done section
- GitHub Projects (v2) Kanban board: Backlog / In Progress / In Review / Done, linked to the repo
- `protect-main` ruleset hardened: `allowed_merge_methods = ["squash"]`
- This plan file, committed on the 0.4 branch per repo convention

**Scope.** Only the above.

**Out of scope.** CI workflow + required status checks (0.5 — adding required checks before CI exists would block every merge); `required_approving_review_count` &gt; 1; `require_code_owner_review`(deliberately NOT enabled — see D2); any change to CLAUDE.md's CODEOWNERS example (optionally noted in the PR body instead — D1); issue/PR automation (Actions) of any kind.

---

## 2. Repository Assessment

Verified 2026-07-20 (post-0.3 merge, commit `957918d`):

| Item | Status |
| --- | --- |
| 0.1–0.3 | **done** — squash commits on `main` (#2, #5, #7); issue #6 closed; rollout comments from all 3 accounts on issue #6 |
| Phase-0 gate | claimed with fresh-clone run explicitly deferred to 0.5's CI (issue #6 thread) |
| `.github/` | **does not exist** — no CODEOWNERS, no PR template, no workflows |
| Labels | GitHub's 9 defaults + `type:chore` + `phase:0` (created during 0.3). Missing: 5 `type:*`, all 4 `priority:*`, `phase:1–7`. Defaults `bug`/`enhancement`/`documentation` overlap the planned taxonomy |
| Milestones | **none** |
| Projects board | **none** (as far as CLI can see; needs `project` scope / UI to confirm) |
| Ruleset `protect-main` (id 18805437) | active on default branch; blocks deletion + force-push; PR required with 1 approval; **but** `allowed_merge_methods` = merge+squash+rebase, `require_code_owner_review` = false, no required status checks |
| Issue #1 | open: "Complete branch protection (CODEOWNERS review in 0.4; required status checks in 0.5)" — 0.4 resolves its first half |
| Squash-title hygiene | commit #5's message has the branch name glued on ("…configFeature/4 tooling skeleton"); #7's is clean — evidence the manual-discipline approach is error-prone, motivating the hardening |

**Blockers.** None. Ruleset/board/milestone edits need org-admin rights — PritamK518 actions (UI or API from an authenticated-as-lead session).

**Technical debt addressed here.** The 0.3-plan's known protection gap (squash-only). **Debt deliberately left:** required status checks (0.5); CLAUDE.md §12.3's CODEOWNERS example has the catch-all `*` entry last, which under GitHub's last-match-wins rule would swallow every earlier entry — this plan implements the doc's *intent*, not its literal ordering (D1).

---

## 3. Requirements

From Master_plan 0.4 and CLAUDE.md (no invention):

- **Q1 (§12.3)** `CODEOWNERS` routing: `data_generator/**` → Senior Dev (Pritam1026), `ml_pipeline/**`, `dags/**`, `configs/**`, `*.md` → Team Lead (PritamK518), `serving/**` → Developer 2 (JuhiPreet143), `tests/**` → all three, catch-all → Team Lead. Team Lead reviews every PR (§12.4); the module owner's review is genuine practice, not a technically-enforced second gate (§12.3 verbatim).
- **Q2 (§12.5)** PR template with the exact five sections: Purpose / Implementation summary / Testing performed / Screenshots / Checklist.
- **Q3 (§12.17)** Labels: `type:feature|bug|docs|refactor|test|chore`, `priority:p0..p3`, `phase:1..7` (status = board columns, not labels).
- **Q4 (§12.17)** Milestones map 1:1 to Phases 1–7; description links the phase's Definition-of-Done checklist in CLAUDE.md; Milestone closes when every box is checked. Releases (§12.12) cut per closed Milestone.
- **Q5 (§12.17)** GitHub Projects Kanban: Backlog / In Progress / In Review / Done.
- **Q6 (§12.4)** Squash merge only, enforced by branch protection — the PR title (Conventional Commit) becomes the squash commit on main.
- **Q7 (§12.4)** Branch protection remains: PR required, 1 approval, no force-push/deletion. Required status checks arrive with CI (0.5).

---

## 4. Detailed Implementation Plan

Two tracks: **repo files** (one PR, authored by Pritam1026 on the Mac) and **GitHub configuration** (lead actions as PritamK518 — labels/ milestones via `gh` CLI, board + ruleset via UI). Order: files PR first (CODEOWNERS must be on `main` to take effect), then config, then verification.

### T1 — `.github/CODEOWNERS` (files PR)

- **Creates:** `.github/CODEOWNERS`.
- **Content contract** (order matters — GitHub applies the *last*matching pattern, so the catch-all comes FIRST and specific paths override it; every specific entry also lists the Team Lead so both the module owner and the Lead are auto-requested):
  - `*` → `@PritamK518`
  - `*.md` → `@PritamK518`
  - `data_generator/**` → `@Pritam1026 @PritamK518`
  - `ml_pipeline/**` → `@PritamK518`
  - `serving/**` → `@JuhiPreet143 @PritamK518`
  - `dags/**` → `@PritamK518`
  - `configs/**` → `@PritamK518`
  - `tests/**` → `@PritamK518 @Pritam1026 @JuhiPreet143`
  - A header comment stating the last-match-wins ordering rationale and pointing at §12.3.
- **Validation:** after merge, `gh api repos/{org}/{repo}/codeowners/errors` returns an empty error list; the 0.5 PR auto-requests the expected reviewers.

### T2 — `.github/pull_request_template.md` (files PR)

- **Creates:** `.github/pull_request_template.md` with §12.5's exact markdown (five sections, checkbox lists verbatim).
- **Validation:** next PR opened (0.5) pre-fills with the template.

### T3 — Label taxonomy (lead, `gh` CLI — scriptable from any machine

authenticated as PritamK518; plain `gh label create/delete` needs no admin beyond triage rights)

- **Create 16 labels:**
  - `type:feature` `#a2eeef`, `type:bug` `#d73a4a`, `type:docs#0075ca`, `type:refactor` `#c5def5`, `type:test` `#bfd4f2`(`type:chore` exists from 0.3)
  - `priority:p0` `#b60205` (blocking), `priority:p1` `#d93f0b`, `priority:p2` `#fbca04`, `priority:p3` `#0e8a16` (nice to have)
  - `phase:1` … `phase:7` — one hue family (e.g. graded greens/teals), descriptions naming the phase ("Phase 1: data_generator", …)
- **Delete 3 overlapping defaults:** `bug`, `enhancement`, `documentation` (replaced by `type:bug`/`type:feature`/`type:docs` — two names for one concept guarantees inconsistent labeling). Keep the non-overlapping defaults (`question`, `wontfix`, `duplicate`, `good first issue`, `help wanted`, `invalid`) — resolution/community labels, orthogonal to the taxonomy (D3).
- **Validation:** `gh label list` shows 6+4+8 project labels (`type:*`×6, `priority:*`×4, `phase:0–7`×8) and no `bug`/`enhancement`/`documentation`.

### T4 — Milestones 1–7 (lead, `gh api` — POST `/milestones`)

- **Create 7 milestones**, `title` = `Phase N — <short name>` (Phase 1 — data_generator, Phase 2 — EDA pipeline, Phase 3 — preprocessing & feature selection, Phase 4 — models & Optuna, Phase 5 — MLOps, Phase 6 — serving & RAG, Phase 7 — Feast (stretch)); `description` = one line
  - pointer to the phase's CLAUDE.md DoD section (§4–§10) and Master_plan gate + planned release tag (`v0.1.0` … `v0.7.0`).
- No due dates (no calendar commitments exist; lead can add later in UI).
- No Phase-0 milestone: Phase 0 closes with 0.5, retro-creating a milestone for nearly-done work adds nothing (D4).
- **Validation:** `gh api .../milestones --jq length` returns 7.

### T5 — Projects Kanban board (lead, web UI — Projects v2 CLI needs the

`project` token scope; UI is the low-friction path for a one-time setup)

- Org-level Project "Petrochem Roadmap" (or repo-linked equivalent): Board view; Status field options renamed/extended to exactly Backlog / In Progress / In Review / Done; repo linked; existing open issues (#1 + the 0.5 issue when created) added to Backlog.
- Optional built-in workflows: auto-add new repo issues; move to Done on close. Nothing custom.
- **Validation:** board visible under the org's Projects tab with the 4 columns; issue #1 appears on it.

### T6 — Ruleset hardening (lead, repo Settings → Rules → `protect-main`,

or `gh api -X PUT /rulesets/18805437` from a lead-authenticated session)

- **Change exactly one thing:** pull-request rule `allowed_merge_methods`: `["merge","squash","rebase"]` → `["squash"]`.
- Everything else stays: 1 approval, deletion + non-fast-forward blocks, `require_code_owner_review` stays **false** (D2), no status checks (0.5).
- **Validation:** `gh api .../rulesets/18805437` shows `allowed_merge_methods == ["squash"]`; the 0.5 PR's merge button offers only "Squash and merge".

### T7 — Issue #1 bookkeeping (lead)

- Comment on issue #1: CODEOWNERS + squash-only done in 0.4 (link PR); required status checks remain, arriving with 0.5's CI. Keep the issue **open** — it closes with 0.5 (D5).

---

## 5. Detailed Step-by-Step Execution

 1. **Issue:** PritamK518 creates the 0.4 issue in the web UI (per established practice): title "Phase 0.4: CODEOWNERS, PR template, labels, Milestones, board, squash-only", labels `type:chore` + `phase:0`, assignee Pritam1026 for the files PR, body listing T1–T7 with acceptance criteria from §8. Note the issue number **N**.
 2. **Branch:** on the Mac as Pritam1026: `git checkout main && git pull && git checkout -b feature/N-github-process`.
 3. **T1:** write `.github/CODEOWNERS` per the T4.1 content contract (catch-all first; real usernames; header comment). No local validation possible beyond eyeballing — GitHub validates post-push (step 8).
 4. **T2:** write `.github/pull_request_template.md` — §12.5's markdown verbatim.
 5. **Commit + push** (`chore: add CODEOWNERS and PR template`) — this plan file rides along. Pre-commit hooks fire (yaml/whitespace hooks apply; no Python touched, so mypy/pytest are trivially green).
 6. **PR:** `gh pr create` titled per §9, body `Closes #N` *for the files portion* — actually reference "Part of #N" (the issue also tracks lead config actions; don't auto-close it from the PR — close it manually in step 12). Note: template isn't on `main` yet, so this PR's body is written manually per §12.5 one last time.
 7. **Review + squash-merge:** PritamK518 approves in the UI (checklist: ordering rule respected, usernames real, template matches §12.5) and squash-merges — manually picking squash for the last time; watch the commit-title box.
 8. **Post-merge validation (Mac):** `gh api repos/petrochem-ml-projects/petrochem-xgboost-lstm-ta/codeowners/errors`→ `{"errors":[]}`.
 9. **T3 labels:** as PritamK518 (from whichever machine is authenticated): run the create/delete commands per T4.3. Verify with `gh label list`.
10. **T4 milestones:** as PritamK518: 7 × `gh api -X POST .../milestones`. Verify count.
11. **T5 board:** PritamK518 in the web UI: create project, set the four Status options, link repo, add open issues, enable auto-add/auto-done workflows.
12. **T6 ruleset:** PritamK518 in Settings → Rules: edit `protect-main`, restrict merge methods to squash only. Verify via `gh api` read-back (any account can read).
13. **T7 + close-out:** comment on issue #1 (scope split note); comment results on issue N (label list, milestone count, board link, ruleset read-back) and close it. Move its card to Done on the new board — the board's first real use.
14. **Sync check (other machines):** nothing to pull beyond the two `.github/` files; a plain `git pull` on Windows/Ubuntu at next session start suffices — no rollout ritual needed (no code, no environment change; D6).

---

## 6. Design Decisions

- **D1 — CODEOWNERS ordering deviates from CLAUDE.md's literal example**.GitHub applies the **last matching pattern**, and the §12.3 example puts `*` last — which would make the Team Lead sole owner of everything and dead-letter every specific entry. Options: (a) copy the example verbatim (broken routing); (b) reorder — catch-all first, specifics after, each specific entry including the Lead. **Chosen: (b)** — implements the documented *intent* (module owner + Lead both requested; Lead covers everything else). The deviation is called out in the PR body; optionally a one-line CLAUDE.md fix PR later (doc-wins rule §"If code ever conflicts").
- **D2 —** `require_code_owner_review` **stays off.** With single-owner paths (`ml_pipeline/** @PritamK518` only), enabling it would deadlock every Lead-authored PR: GitHub requires a code-owner approval *other than the author*, and no second owner exists for those paths. §12.3 itself says the count stays at 1 "satisfied specifically by the Lead" as practice, not machine enforcement. Options: (a) enable + add second owners everywhere (dilutes ownership semantics); (b) leave off — CODEOWNERS still auto-requests reviewers, approval count 1 still enforced. **Chosen: (b)**. Revisit if the team ever has ≥2 people per module.
- **D3 — Delete only the 3 overlapping default labels.** Full default wipe is tidier but destroys nothing-wrong labels (`question`, `wontfix`) that serve as resolution markers orthogonal to the type/priority/phase taxonomy. Overlap is the actual harm (two names for one concept → inconsistent data), so only `bug`/`enhancement`/ `documentation` go.
- **D4 — No Phase-0 milestone.** Master_plan says Milestones 1–7; Phase 0 is one item from done and its tracking lives in issues #1/#6/N. Retro-creating a milestone would be ceremony.
- **D5 — Issue #1 stays open across 0.4.** It was written to span two work items (CODEOWNERS-era protection + status checks); closing it half-done loses the 0.5 reminder. Comment now, close with 0.5.
- **D6 — No 3-machine rollout ritual for this item.** 0.2/0.3 changed the local environment (deps, hooks, importable tree) — rollout proved each machine still worked. 0.4 ships two `.github/` files and server-side config; machines are unaffected until they open PRs, which 0.5 exercises anyway.
- **D7 — Labels/milestones via** `gh` **CLI, board/ruleset via UI.** Labels and milestones are plain REST, scriptable, and idempotent enough to re-run; Projects v2 needs an extra token scope and the ruleset editor benefits from the UI's method checkboxes. Matches the established lead-uses-UI / scripted-where-cheap split.

---

## 7. Testing Strategy

No code → no unit/integration/pipeline/e2e tiers. Verification is behavioral, against live GitHub state:

| Check | Action | Expected |
| --- | --- | --- |
| CODEOWNERS syntax | `gh api repos/{org}/{repo}/codeowners/errors` | `errors: []` |
| Routing works | open the 0.5 PR (touches `.github/workflows/`) | PritamK518 auto-requested; a test PR touching `serving/` would request JuhiPreet143 + PritamK518 |
| Template renders | open the 0.5 PR | body pre-filled with §12.5 sections |
| Label taxonomy | `gh label list` | 18 project labels present; `bug`/`enhancement`/`documentation` absent |
| Milestones | `gh api .../milestones --jq length` | `7` |
| Board | org Projects tab | 4 columns, repo linked, issue #1 carded |
| Squash-only | `gh api .../rulesets/18805437` + 0.5 PR merge box | `allowed_merge_methods == ["squash"]`; single merge option in UI |
| Protection regression | attempt direct push to `main` (dry: `git push --dry-run`) | still rejected |

---

## 8. Acceptance Criteria

1. `.github/CODEOWNERS` and `.github/pull_request_template.md` on `main`via a squash-merged PR (author Pritam1026, approver PritamK518); `codeowners/errors` API returns no errors.
2. `gh label list` shows exactly the taxonomy: `type:*`×6, `priority:p0–p3`, `phase:0–7`; the three overlapping defaults gone.
3. Seven milestones `Phase 1`…`Phase 7`, each description pointing at its CLAUDE.md DoD section and release tag.
4. Projects board exists with Backlog/In Progress/In Review/Done, repo linked, open issues carded.
5. Ruleset `protect-main`: `allowed_merge_methods == ["squash"]`; 1 approval, no-force-push, no-deletion unchanged.
6. Issue #1 carries the scope-split comment and remains open; the 0.4 issue is closed with verification evidence and its card sits in Done.
7. The next real PR (0.5) demonstrably: pre-fills the template, auto-requests reviewers, and offers only squash merge.

---

## 9. Pull Request Plan

One PR carries everything file-shaped; the rest is GitHub configuration executed by the lead and evidenced in the 0.4 issue (config isn't PR-able — the issue thread is its audit trail):

| \# | Branch → PR title | Scope | Review focus (PritamK518) |
| --- | --- | --- | --- |
| 1 | `feature/N-github-process` → `chore: add CODEOWNERS and PR template` | `.github/CODEOWNERS`, `.github/pull_request_template.md`, this plan file | catch-all-first ordering + rationale comment present; all three usernames correct (Pritam1026 / PritamK518 / JuhiPreet143); every specific path also lists the Lead; `tests/**` lists all three; template matches §12.5 verbatim; D1 deviation noted in PR body |

PR body: "Part of #N" (not `Closes` — the issue also tracks T3–T7), the D1 ordering rationale, and a checklist of the lead's follow-up config tasks so the issue can't be closed with them forgotten.

After 0.4: proceed to 0.5 (CI v1: ruff → mypy → unit tests → docker build placeholders + weekly cross-platform matrix), which also closes issue #1 (required status checks) and finishes Phase 0.
