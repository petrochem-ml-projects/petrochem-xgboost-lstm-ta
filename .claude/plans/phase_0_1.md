# Phase 0 · Item 0.1 implementation plan — `git init` + GitHub repo + branch protection

Authoritative sources: `.claude/plans/Master_plan.md` Phase 0, work item
0.1; `CLAUDE.md` §12.4 (git workflow / branch protection), §12.14
(secrets, scanning), §12.15 (line endings, multi-platform), §14 ($0-cost /
public-repo ground rules).

Scope note: Master_plan item 0.1 covers exactly — `git init` + GitHub
repo, branch protection on `main`, `.gitattributes` (force LF),
`.gitignore` (`.env`, `.venv`, `reports/`, DVC cache). Items 0.2–0.5
(tooling, skeleton, GitHub process files, CI) are separate plans.

---

## 1. Objective

**Purpose.** Turn this bare directory into a version-controlled, GitHub-
hosted repository operating under the §12.4 team workflow from commit 1 —
CLAUDE.md §1 explicitly requires the workflow to be in place from the
start, "not bolted on later".

**Business objective.** Three developers on three OSes (macOS / Windows /
Ubuntu) need one integration branch (`main`) that nobody can push to
directly, uniform LF line endings so diffs don't churn across OSes, and a
guarantee that secrets and large binaries never enter history (history is
forever — prevention beats cleanup).

**Deliverables.**
- Local git repository on branch `main`, first commit pushed.
- Public GitHub repository, all 3 machines authenticated over SSH with
  per-machine committer identities.
- `.gitignore` and `.gitattributes` committed.
- Branch protection on `main` active (the subset enforceable before CI
  and CODEOWNERS exist — see §6-D3).
- Secret scanning + push protection verified on.

**Scope.** Only the above.

**Out of scope (deferred to their own items).** `pyproject.toml` /
`uv.lock` / pre-commit (0.2); directory skeleton, `config.py` stub,
`.env.example` (0.3); `CODEOWNERS`, PR template, labels, Milestones,
Kanban board (0.4); CI workflow and therefore the "required status
checks" and PR-title-convention halves of branch protection (0.5); any
Phase 1+ code.

---

## 2. Repository Assessment

Verified 2026-07-09:

| Item | Status |
|---|---|
| Git repository | **missing** — `git rev-parse` fails; nothing under version control |
| GitHub remote | **missing** |
| `.gitignore` / `.gitattributes` | **missing** |
| `CLAUDE.md` | present — must be in the first commit |
| `.claude/` (commands + plans incl. `Master_plan.md`) | present — commit it (team-shared planning assets); ignore `settings.local.json` if it appears |
| `XGBOOST_LSTM_TA.pdf` (~18 MB) | present — **must be gitignored before the first commit**; committing it would bloat every clone forever and (once 0.2 lands) trip `check-added-large-files` |
| Prior work items | none — 0.1 is the project's first work item; no prerequisites exist or are needed |

**Blockers.** None technical. Two pieces of information are needed from
the humans before finishing: the GitHub org/user + repo name, and the
three GitHub accounts (needed in 0.4 for CODEOWNERS, but SSH keys are
registered now).

**Technical debt created knowingly.** Branch protection lands here in a
reduced form and is completed by 0.4/0.5 (see §6-D3). Track with a
follow-up issue so it isn't forgotten.

---

## 3. Requirements

From Master_plan item 0.1 and CLAUDE.md (no invention):

- **Q1 (§12.4)** `main` is the single integration branch (GitHub Flow);
  branch prefixes `feature/* fix/* refactor/* docs/* test/* experiment/*
  release/*` for all subsequent work.
- **Q2 (§12.4)** Branch protection on `main`: PR required, 1 approval
  (via CODEOWNERS once 0.4 lands), required CI status checks (once 0.5
  lands), branches must be up to date before merge, **squash merge only**.
- **Q3 (§12.4)** Conventional Commits enforced on **PR titles** only
  (mechanism arrives with CI in 0.5); in-branch commits unconstrained.
- **Q4 (§12.4)** Each machine has its own SSH key and matching
  `git config user.name` / `user.email` for its GitHub identity.
- **Q5 (Master_plan 0.1, §12.15)** `.gitattributes` forcing LF on every
  checked-out file.
- **Q6 (Master_plan 0.1, §12.14)** `.gitignore` covering `.env`, `.venv`,
  `reports/`, DVC cache — plus (repo-state-driven, see §2) the paper PDF
  and standard Python/OS/IDE noise.
- **Q7 (§12.14)** GitHub secret scanning + push protection on (default on
  public repos — verify, don't assume).
- **Q8 (§14)** Public repository, no paid features (branch protection of
  this shape is free only on public repos — a private repo would need a
  paid plan, so public is both the ground rule and the cost-correct
  choice).

---

## 4. Detailed Implementation Plan

Three tasks, strictly ordered (each needs the previous).

### T1 — Hygiene files + local repository
- **Creates:** `.gitignore`, `.gitattributes`; initializes git.
- **`.gitattributes` content:** single rule `* text=auto eol=lf`
  (normalize on commit, LF on checkout, all platforms — §12.15; the 0.2
  `mixed-line-ending` pre-commit hook later backstops it).
- **`.gitignore` sections (grouped, commented):**
  - Secrets: `.env` (keep future `.env.example` committable — no glob
    that would catch it)
  - Python: `.venv/`, `__pycache__/`, `*.py[cod]`, `.pytest_cache/`,
    `.mypy_cache/`, `.ruff_cache/`, `htmlcov/`, `.coverage*`,
    `*.egg-info/`, `dist/`, `build/`
  - Project outputs: `reports/`
  - DVC cache (pre-declared for Phase 5): `.dvc/cache/`, `.dvc/tmp/`
  - Large/local docs: `*.pdf` (the paper stays local-only)
  - Tooling-local: `.claude/settings.local.json`
  - OS/IDE: `.DS_Store`, `Thumbs.db`, `.idea/`, `.vscode/`
- **Algorithm/order:** write both files → `git init -b main` → verify
  `git status` lists only `CLAUDE.md`, `.claude/**`, `.gitignore`,
  `.gitattributes` (PDF absent) → first commit.
- **First commit message:** `chore: initialize repository with git
  hygiene files and planning docs` (Conventional type per §12.4 even
  though only PR titles are formally enforced — this commit lands on
  `main` directly, so it should look like every other `main` commit).
- **Validation:** `git check-attr text eol -- CLAUDE.md` reports
  `text: auto`, `eol: lf`; `git status --ignored` shows the PDF ignored.

### T2 — GitHub repository + per-machine authentication
- **Creates:** public GitHub repo; remote `origin`; 3 SSH keys.
- **Steps:** create repo (no auto-generated README/.gitignore/license —
  the local history is authoritative; an auto-README would force an
  immediate merge conflict) → `git remote add origin
  git@github.com:<owner>/<repo>.git` → `git push -u origin main`.
- **Per machine (×3):** generate `ed25519` key, add to that developer's
  GitHub account, set repo-local `git config user.name/user.email`
  matching the account (§12.4). Verify with `ssh -T git@github.com`.
- **Configuration (repo settings):** default branch `main`; merge
  methods: **squash only** (disable merge commits and rebase merging);
  optionally enable "automatically delete head branches" (keeps the
  branch list clean under the §12.4 short-lived-branch model).
- **Validation:** fresh `git clone` on a second machine yields identical
  content with LF endings (spot-check a file on the Windows machine).

### T3 — Branch protection + scanning verification
- **Configuration (ruleset or classic protection on `main`):**
  - Require a pull request before merging; required approvals: 1.
  - Require branches to be up to date before merging (the toggle exists
    without required checks; the *checks themselves* are added by 0.5).
  - Block force pushes and deletions (implicit in protection; verify).
  - Do **not** enable "require review from Code Owners" yet — no
    CODEOWNERS file until 0.4 (see §6-D3).
- **Deferred-completion issue:** open GitHub issue "Complete branch
  protection (CODEOWNERS review 0.4; required status checks + PR-title
  check 0.5)" so the reduced protection is a tracked, temporary state.
- **Verify Q7:** repo Settings → Code security: secret scanning + push
  protection enabled.
- **Validation:** see §7's behavioral checks.
- **Exception handling (process, not code):** if a direct push to `main`
  is ever needed again (it shouldn't be after this item), it requires
  deliberately lifting protection — treat as an incident, not a habit.

---

## 5. Detailed Step-by-Step Execution

1. **Write `.gitignore`** at repo root with the §4-T1 sections.
   Responsibility: keeping secrets, bulk artifacts, and machine-local
   noise out of history. Interacts with: 0.3's `.env.example` (must not
   be caught), Phase 2's `reports/`, Phase 5's DVC. Check: after T1's
   init, `git status --ignored --short` lists `XGBOOST_LSTM_TA.pdf`
   under ignored.
2. **Write `.gitattributes`** (`* text=auto eol=lf`). Responsibility:
   OS-independent line endings (§12.15 calls mixed endings the top
   "works on my machine" source). Check: `git check-attr` as in §4-T1.
3. **`git init -b main`** in the project root (explicit `-b main`
   avoids depending on the machine's `init.defaultBranch`).
4. **Stage and inspect:** `git add .` then `git status` — expected
   staged set: `CLAUDE.md`, `.claude/commands/phase_plan.md`,
   `.claude/plans/{Master_plan.md,phase_1.md,phase_0_1.md}`,
   `.gitignore`, `.gitattributes`. If the PDF appears, stop and fix
   `.gitignore` before committing.
5. **Commit** with the §4-T1 message. This is the one legitimate direct
   commit to `main` (protection can't precede the branch's existence —
   the §6-D1 bootstrap ordering).
6. **Create the public GitHub repo** (empty — no auto-files), named per
   the owner's choice (CLAUDE.md §15 uses `fcc-xgboost-lstm-ta` in its
   clone example; confirm with the team lead).
7. **Add remote + push:** `git remote add origin …` →
   `git push -u origin main`. Expected: `main` visible on GitHub with
   the full first commit.
8. **Authenticate all 3 machines:** per machine, `ssh-keygen -t
   ed25519`, add the public key to that developer's GitHub account, set
   repo-local `git config user.name/user.email`, verify `ssh -T`.
   Output: three distinct committer identities (§12.4).
9. **Set merge methods to squash-only** in repo settings. Check: the
   GitHub UI on any test PR offers only "Squash and merge".
10. **Enable branch protection** on `main` per §4-T3's list. Check: the
    §7 behavioral tests below.
11. **Verify secret scanning + push protection** are on (Settings → Code
    security and analysis).
12. **Open the deferred-completion issue** (§4-T3) and a "trial PR"
    branch `chore/protection-smoke-test` making a trivial change (e.g.
    one README-less doc touch) to run the §7 checks end-to-end; merge it
    by squash after approval, confirming the whole loop works before 0.2
    starts.

---

## 6. Design Decisions

- **D1 — Bootstrap ordering (commit before protection).** Options: (a)
  create the GitHub repo first with auto-README, PR everything in; (b)
  local init + one direct push, then protect. **Chosen: (b).** (a) still
  requires protection to be off for the merge to have a reviewer-less
  approval (only one account exists per machine; self-approval of the
  bootstrap PR adds ceremony without review value) and creates an
  auto-README merge conflict. Trade-off: exactly one unreviewed commit on
  `main`; mitigated by it containing only hygiene files + docs already
  reviewed as documents.
- **D2 — Public repository.** Required by §14's $0 ground rule and Q8:
  free branch protection, free secret scanning/push protection, free
  Actions minutes (0.5). Trade-off: the code is public from day 0 —
  acceptable: it's a paper reimplementation on synthetic data; secrets
  hygiene (Q6/Q7) is the control that matters.
- **D3 — Phased branch protection.** §12.4's full protection references
  CODEOWNERS (0.4) and CI status checks (0.5) that don't exist yet.
  Options: (a) wait and enable everything at 0.5; (b) enable the
  enforceable subset now, complete later. **Chosen: (b)** — otherwise
  items 0.2–0.4 would merge into an unprotected `main`, contradicting
  "workflow from commit 1". Trade-off: two later touch-points to the
  settings, tracked by the §4-T3 issue.
- **D4 — Commit `.claude/` (except `settings.local.json`).** The
  planning command and plans are team-shared process assets referenced by
  this very workflow; local settings are machine-private. Alternative
  (ignore all of `.claude/`) would strand `Master_plan.md` outside
  version control — unacceptable for the project's roadmap document.
- **D5 — Ignore `*.pdf` globally** rather than the one filename: any
  future paper/reference dropped into the repo stays local by default;
  nothing in the planned build ever ships a PDF artifact. Trade-off:
  if a PDF ever *must* be committed, it needs an explicit `!` exception
  — fine, that's a deliberate act.
- **D6 — `ed25519` SSH keys.** Current GitHub-recommended algorithm;
  short keys, no known-weakness baggage. No real alternative worth
  weighing in 2026.
- **D7 — Repo name.** CLAUDE.md is internally inconsistent
  (`pyproject.toml` name `petrochem-xgboost-lstm-ta` §12.1 vs clone dir
  `fcc-xgboost-lstm-ta` §15). Not resolvable from documents alone —
  flagged to the team lead at step 6; default recommendation:
  `petrochem-xgboost-lstm-ta` (matches the package name; FCC is only 1
  of 4 processes). Whichever is chosen, do not edit CLAUDE.md within
  this item (out of scope; raise a `docs/*` PR later per §1's "gets
  updated via PR" rule).

---

## 7. Testing Strategy

No Python code exists in this item, so there are no `unit`/`integration`/
`pipeline`/`e2e` pytest tiers here (they start at 0.2). Verification is
behavioral, executed as part of step 12's trial PR:

| Check | Action | Expected outcome |
|---|---|---|
| Direct push blocked | `git commit --allow-empty -m test && git push` to `main` from a clone | push **rejected** by protection |
| PR required + approval | open the trial PR, attempt merge with 0 approvals | merge button disabled until 1 approval |
| Squash-only | on the approved trial PR, open the merge dropdown | only "Squash and merge" offered |
| Up-to-date rule | push a second commit to `main` (via another PR) while the trial PR is open | trial PR demands update/rebase before merge |
| LF enforcement | clone on the Windows machine, `git ls-files --eol` | all files `w/lf` (or `w/crlf` absent) |
| PDF exclusion | `git ls-files '*.pdf'` on a fresh clone | empty output |
| Secret push protection | push a canary dummy secret (e.g. a revoked-format test token) on a scratch branch | push blocked by push protection; delete the scratch branch after |
| Identity separation | one commit from each machine on the trial branch | `git log --format='%an %ae'` shows 3 distinct identities |

Failure handling: any failed check means the corresponding setting is
fixed and the check re-run before item 0.1 is declared done — none of
these are deferrable, they *are* the deliverable.

---

## 8. Acceptance Criteria

Restating Master_plan 0.1 and Phase 0's gate contribution as objective
checks:

1. `git rev-parse --abbrev-ref HEAD` in the project dir returns `main`;
   `git remote get-url origin` returns the GitHub SSH URL.
2. The GitHub repo is public; `main` shows the initial commit containing
   `CLAUDE.md`, `.claude/` planning assets, `.gitignore`,
   `.gitattributes` — and no PDF (`git ls-files '*.pdf'` empty).
3. All eight §7 behavioral checks pass, including from a second machine.
4. Secret scanning and push protection show **enabled** in repo settings.
5. The deferred-protection follow-up issue exists and names the 0.4 and
   0.5 completions.
6. All 3 machines can clone, commit (distinct identities), and push a
   branch over SSH.

(The Phase-0 gate as a whole — `uv sync` + pre-commit + green empty test
suite on 3 machines — is *not* claimable here; it needs 0.2/0.3.)

---

## 9. Pull Request Plan

Item 0.1 is the bootstrap: its substance cannot itself arrive by PR
(§6-D1). The honest breakdown:

| # | Vehicle | Title / message | Scope | Review focus |
|---|---|---|---|---|
| 1 | **Direct commit to `main`** (the one-time bootstrap exception) | `chore: initialize repository with git hygiene files and planning docs` | `.gitignore`, `.gitattributes`, `CLAUDE.md`, `.claude/commands/`, `.claude/plans/` | post-hoc: team lead eyeballs the pushed commit; PDF absent; ignore rules complete |
| 2 | Branch `chore/protection-smoke-test` → PR | `chore: verify branch protection with trivial doc touch` | one-line doc tweak; exists to execute §7's checks | the *process*, not the diff: approval gate, squash-only, up-to-date rule all observed working |

Manual (non-file) actions — GitHub repo creation, SSH keys, merge-method
and protection settings, scanning verification, the follow-up issue —
are recorded in PR 2's description as a completed checklist, giving the
settings work a reviewable, linkable record (§12.5's spirit applied to
configuration).

After PR 2 merges and §8 passes, item 0.1 is done; proceed to item 0.2
(tooling skeleton), which delivers the first real code-carrying PR.
