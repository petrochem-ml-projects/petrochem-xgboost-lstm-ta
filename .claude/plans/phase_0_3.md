# Phase 0 · Item 0.3 implementation plan — Directory skeleton

Authoritative sources: `.claude/plans/Master_plan.md` Phase 0, work item
0.3; `CLAUDE.md` §3 (repo skeleton), §4.15 (`config.py` Settings), §12.14
(env-var naming / secrets), §12.7 (coding standards), §12.13 (docstring
standards), §12.8 (test tiers).

Scope note: Master_plan item 0.3 covers exactly — the §3 `mkdir` tree +
`__init__.py` files, a `config.py` stub, and `.env.example`. CODEOWNERS /
PR template / labels / Milestones are 0.4; CI is 0.5; any real generator
or pipeline code is Phase 1+.

---

## 1. Objective

**Purpose.** Turn the tooling shell (0.2) into an *importable codebase*:
every package the seven phases will fill in exists from day one, `import
data_generator`, `import ml_pipeline`, `import serving` all succeed, and
the settings/secrets pattern (`config.py` + `.env.example`, never `.env`)
is established before any code needs it.

**Business objective.** Later phases start with `touch <module>.py` and
writing code, not with directory-layout decisions. The Phase-0 exit gate
(fresh clone → `uv sync --all-extras && pre-commit install && uv run
pytest -m unit` green on all 3 machines) becomes fully claimable once
this item merges — 0.3 is the last code-shaped item the gate depends on.

**Deliverables.**
- Package tree per §3: `data_generator/{domain,generators,specs,sinks}`,
  `ml_pipeline/{data_access, eda/analyzers, preprocessing,
  feature_selection, models/torch_backend, models/keras_backend,
  training, evaluation, mlops}`, `serving/routers` — each directory in
  those three trees carrying an `__init__.py` with a one-line module
  docstring.
- Non-package directories: `dags/`, `configs/processes/`, `scripts/` —
  kept in git via `.gitkeep` (no `__init__.py`; they are not Python
  packages).
- `tests/__init__.py`.
- `config.py` at repo root: `Settings(BaseSettings)` per §4.15 with the
  five Postgres fields + `mlflow_tracking_uri`, and a `.database_url`
  property. (`airflow_api_url` deferred to Phase 5, per §4.15's own
  wording.)
- `.env.example` with the §3 local-dev defaults, names per §12.14.
- `tests/test_config.py` — unit tests for `Settings`.

**Scope.** Only the above.

**Out of scope.** Any behavior inside the packages (Phase 1+);
`docker-compose.yml` / Dockerfiles (Phase 1, §4.17); CODEOWNERS/PR
template (0.4); CI (0.5); `airflow_api_url` and any Airflow config
(Phase 5).

---

## 2. Repository Assessment

Verified 2026-07-16 (post-0.2, post-org-transfer):

| Item | Status |
|---|---|
| Item 0.2 (pyproject/lockfile/pre-commit/sanity test) | **done** — PR #5 squash-merged; rollout verified on all 3 machines (PR #5 comment) |
| Repo home | transferred to org `petrochem-ml-projects`; Mac remote updated; branch ruleset active on `main` (PR + 1 approval, no force-push/deletion) |
| Known protection gap | ruleset still allows merge/squash/rebase — squash-only pending (Team Lead UI action; tracked under 0.4's protection hardening, not a 0.3 blocker) |
| Team accounts | Pritam1026 = Senior Dev (Mac), PritamK518 = Team Lead (HP/Windows), JuhiPreet143 = Developer (Ubuntu) — identities + SSH configured |
| `tests/` | exists with `test_sanity.py`; **no `__init__.py` yet** (0.3 adds it) |
| `data_generator/`, `ml_pipeline/`, `serving/`, `dags/`, `configs/`, `scripts/` | **all missing** — this item creates them |
| `config.py`, `.env.example` | **missing** — this item creates them |
| `.gitignore` | already ignores `.env`; stale plan-file lines already cleaned up — no change needed |
| Plans convention | `.claude/plans/*.md` are committed (Master_plan, 0.1, 0.2 all tracked) — this plan file rides along in the 0.3 PR |

**Blockers.** None. **Technical debt.** The squash-only gap above;
mirrors-mypy hook may need `additional_dependencies: [pydantic,
pydantic-settings]` once `config.py` exists (0.2 plan's D7 foresaw
this) — resolve in this PR if the hook fails on `config.py`.

---

## 3. Requirements

From Master_plan 0.3 and CLAUDE.md (no invention):

- **Q1 (§3)** Directory tree exactly as §3's `mkdir -p` command lists;
  `__init__.py` in every directory under `data_generator/`,
  `ml_pipeline/`, `serving/`; plus `tests/__init__.py`.
- **Q2 (§4.15)** `config.py` at repo root: `Settings(BaseSettings)`
  (pydantic-settings, reads `.env`) with `postgres_host`, `postgres_port`,
  `postgres_db`, `postgres_user`, `postgres_password`,
  `mlflow_tracking_uri`; a `.database_url` property returning the
  `postgresql+psycopg2://user:pass@host:port/db` SQLAlchemy URL.
- **Q3 (§3, §12.14)** `.env.example` committed; `.env` gitignored and
  never committed. Local-dev defaults: `localhost` / `5432` / `petrochem`
  / `petrochem` / `petrochem`. Names `UPPER_SNAKE_CASE`, prefixed by
  owning system (`POSTGRES_*`, `MLFLOW_*`).
- **Q4 (§12.13, §12.7)** Every public module needs a module docstring —
  ruff's `D104` (package docstring) applies to each `__init__.py`, `D100`
  to `config.py`. Type hints on all public functions
  (`disallow_untyped_defs` applies to `config.py`).
- **Q5 (§12.8)** New tests carry the `unit` marker; no external services.
- **Q6 (Master_plan Phase-0 gate)** After merge: fresh clone → `uv sync
  --all-extras && pre-commit install && uv run pytest -m unit` green on
  all three machines — with 0.1/0.2 done, 0.3 completes the gate's
  preconditions.
- **Q7 (§12.15)** Nothing OS-specific; note §3's `find -printf` one-liner
  is GNU-only and does not run on macOS/BSD — the plan uses a portable
  equivalent (see §6-D5).

---

## 4. Detailed Implementation Plan

Three tasks, strictly ordered.

### T1 — Package tree + `__init__.py` files
- **Creates:** the three package trees (Q1), one `__init__.py` per
  directory — each containing only a one-line docstring naming the
  package's future purpose (e.g. `"""Synthetic process data generator."""`
  for `data_generator/__init__.py`); `tests/__init__.py` (empty docstring
  not required — `tests/**` is exempt from `D` per pyproject, but add a
  one-liner anyway for consistency); `.gitkeep` in `dags/`,
  `configs/processes/`, `scripts/`.
- **Modifies:** nothing.
- **Package inventory (19 `__init__.py` files):**
  `data_generator/` + `domain, generators, specs, sinks` (5);
  `ml_pipeline/` + `data_access, eda, eda/analyzers, preprocessing,
  feature_selection, models, models/torch_backend, models/keras_backend,
  training, evaluation, mlops` (12); `serving/` + `routers` (2);
  plus `tests/__init__.py`.
- **Validation:** `uv run python -c "import data_generator, ml_pipeline,
  serving"` exits 0; `git status` shows every new file (none swallowed by
  ignore rules); `uv run ruff check .` passes (docstrings satisfy D104).

### T2 — `config.py` + `.env.example`
- **Creates:** `config.py` (repo root), `.env.example` (repo root).
- **`config.py` contents:** module docstring; `Settings(BaseSettings)`
  with `model_config = SettingsConfigDict(env_file=".env")`; six fields
  with the Q3 defaults (`postgres_host="localhost"`, `postgres_port=5432`,
  `postgres_db="petrochem"`, `postgres_user="petrochem"`,
  `postgres_password="petrochem"`,
  `mlflow_tracking_uri="http://localhost:5000"`); `database_url` as a
  `@property` returning the assembled `postgresql+psycopg2://` URL, fully
  type-annotated. Pydantic-settings maps lowercase field names to
  `POSTGRES_HOST` etc. case-insensitively — no aliases needed.
- **`.env.example` contents:** the six variables in `UPPER_SNAKE_CASE`
  with the same defaults, one comment line pointing at §12.14 for naming
  rules. No secrets — the example *is* the local-dev value set.
- **Validation:** `uv run python -c "from config import Settings;
  print(Settings().database_url)"` prints
  `postgresql+psycopg2://petrochem:petrochem@localhost:5432/petrochem`;
  `uv run mypy .` passes.

### T3 — `tests/test_config.py`
- **Creates:** `tests/test_config.py`, all tests `@pytest.mark.unit`.
- **Test cases:**
  1. Defaults: `Settings()` (with env cleared via `monkeypatch.delenv` /
     constructing with `_env_file=None`) yields the Q3 defaults.
  2. `database_url` composition: exact expected string for known field
     values.
  3. Env override: `monkeypatch.setenv("POSTGRES_PASSWORD", "s3cret")` →
     reflected in `Settings().database_url`.
- **Validation:** `uv run pytest -m unit` → 4 passed (1 sanity + 3 new).

---

## 5. Detailed Step-by-Step Execution

1. **Issue:** create the 0.3 GitHub issue in the org repo (labels
   `type:chore`, `phase:0`), assignee = Senior Dev (Pritam1026).
2. **Branch:** `feature/<issue#>-directory-skeleton` off up-to-date
   `main`, authored on the Mac as Pritam1026.
3. **T1 directories:** create the tree with portable `mkdir -p` calls;
   write each `__init__.py` with its one-line docstring; add the three
   `.gitkeep`s. Check: import triple succeeds; `ruff check` green.
4. **T2 config:** write `config.py`, then `.env.example`. Check: the
   `database_url` one-liner prints the expected URL; mypy green. If the
   mirrors-mypy *hook* fails on pydantic imports at commit time, add
   `additional_dependencies: ["pydantic", "pydantic-settings"]` to the
   mypy hook in `.pre-commit-config.yaml` in this same PR (predicted by
   0.2-plan D7).
5. **T3 tests:** write `tests/test_config.py`. Check: `pytest -m unit`
   → 4 passed; no unknown-marker warnings.
6. **Full local gate:** `uv run ruff check .`, `uv run ruff format
   --check .`, `uv run mypy .`, `uv run pytest -m unit`, `uv run
   pre-commit run --all-files` — all green.
7. **Commit + push** (hooks fire; pre-push runs the 4-test unit suite).
   This plan file (`.claude/plans/phase_0_3.md`) is committed in the same
   branch per the established plans-are-tracked convention.
8. **PR** from Pritam1026, titled per §9, body `Closes #<issue>`,
   requesting review — **approved by PritamK518** (Team Lead), the first
   PR where author ≠ approver is structurally enforced.
9. **Squash-merge** (Team Lead), issue auto-closes.
10. **Post-merge, other two machines:** `git pull && uv sync --all-extras
    && uv run pytest -m unit` (hooks already installed from 0.2) —
    4 passed each. Comment results on the PR.
11. **Claim the Phase-0 gate** in the 0.3 issue/PR thread: fresh clone →
    the full §12.9 sequence green on all three machines (0.4/0.5 refine
    process/CI but the gate as written in Master_plan is now met).

---

## 6. Design Decisions

- **D1 — Docstring-bearing `__init__.py`, not empty files.** Ruff's `D104`
  (enabled via the `D` rule set) fails on empty package inits outside
  `tests/**`. Options: (a) per-file-ignore D104 for `**/__init__.py`;
  (b) one-line docstrings. **Chosen: (b)** — zero config churn, and the
  docstring doubles as the §12.13-mandated module documentation. Cost:
  19 one-liners.
- **D2 — `.gitkeep` for `dags/`, `configs/processes/`, `scripts/`.** Git
  cannot track empty directories. Options: (a) defer creating them until
  they have content; (b) `.gitkeep` placeholders. **Chosen: (b)** — §3
  names them as part of the skeleton and having them present keeps later
  phases' diffs content-only. They get no `__init__.py`: DAG files are
  loaded by Airflow's parser, `configs/` holds YAML, `scripts/` holds
  standalone entry points — none are importable packages.
- **D3 — `config.py` is a real Settings class, not a placeholder comment.**
  Master_plan says "stub", §4.15 specifies actual fields and a property.
  The full §4.15 surface minus `airflow_api_url` (§4.15 itself defers it
  to Phase 5) is ~25 lines — implementing it now is cheaper than a
  placeholder plus a second PR, and it gives 0.3 something real to test.
- **D4 — Module-level `settings` singleton NOT created.** Only the class
  is exported; callers instantiate (`Settings()`) or later phases add DI
  wiring. A global instance at import time would read `.env` on *any*
  import of `config`, making unit tests order-dependent. Trade-off: one
  extra parenthesis pair for callers.
- **D5 — Portable directory creation.** §3's
  `touch $(find ... -printf '%p/__init__.py ')` is GNU-find-only (fails
  on macOS/BSD find — no `-printf`). The execution uses plain `mkdir -p`
  plus explicit file writes. No CLAUDE.md change needed (§3 describes
  intent; §12.15 makes portability the overriding rule).
- **D6 — `tests/__init__.py` included.** §3 lists it; it also prevents
  any future test-module name collision ambiguity under pytest's
  rootdir-based collection. `tests/**` stays `D`-exempt per pyproject.
- **D7 — `.env.example` carries real local-dev values.** Since local dev
  values are non-secret by design (§3 says `petrochem`×3 is fine), the
  example file is directly copyable (`cp .env.example .env`) — the §12.9
  onboarding stays one-command-per-step. GitHub push protection continues
  to guard against real secrets landing anywhere.

---

## 7. Testing Strategy

| Tier | Content in this item |
|---|---|
| `unit` | `tests/test_config.py` (3 tests: defaults, URL composition, env override — §4-T3). Failure modes covered: broken pydantic-settings wiring, malformed URL assembly, env vars not being read. |
| `integration` / `pipeline` / `e2e` | none — nothing in this item touches external services (correct until Phase 1's Postgres sink). |

Behavioral checks (part of §5 steps 3–6):

| Check | Action | Expected |
|---|---|---|
| Importability | `python -c "import data_generator, ml_pipeline, serving"` | exit 0 |
| Deep imports | `python -c "import ml_pipeline.models.torch_backend"` | exit 0 (every nested package has its init) |
| Settings URL | `python -c "from config import Settings; print(Settings().database_url)"` | the exact §4-T2 URL |
| Secrets hygiene | `git check-ignore .env` / `git status` after `cp .env.example .env` | `.env` ignored, never listed |
| Gate parity | full §5-step-6 command set | all green, 4 unit tests passed |

---

## 8. Acceptance Criteria

1. All 19 `__init__.py` files + 3 `.gitkeep`s + `config.py` +
   `.env.example` + `tests/test_config.py` on `main` via a squash-merged
   PR authored by Pritam1026 and approved by PritamK518.
2. `uv run python -c "import data_generator, ml_pipeline, serving"` and
   the deep-import check exit 0 on a fresh clone.
3. `Settings().database_url` ==
   `postgresql+psycopg2://petrochem:petrochem@localhost:5432/petrochem`
   with defaults; env override test proves `.env`/environment wins.
4. `uv run pytest -m unit` → **4 passed**; ruff / ruff-format / mypy /
   `pre-commit run --all-files` all green.
5. `.env` remains gitignored (`git check-ignore .env` exits 0);
   `.env.example` is tracked.
6. Rollout: both other machines pull and report 4 passed (comment on the
   PR). The Master_plan **Phase-0 gate** is then claimed explicitly in
   the issue thread.

---

## 9. Pull Request Plan

One PR — Master_plan sizes 0.3 as ≈1 PR; the tree, config, and tests are
one reviewable unit (a tree without importability proof, or config
without its tests, would be un-reviewable halves):

| # | Branch → PR title | Scope | Review focus (PritamK518) |
|---|---|---|---|
| 1 | `feature/<issue#>-directory-skeleton` → `chore: add package skeleton, Settings config, and .env.example` | 19 `__init__.py`, 3 `.gitkeep`, `config.py`, `.env.example`, `tests/test_config.py`, this plan file | tree matches §3 exactly (names and nesting); every init has a docstring (D104); `Settings` fields/defaults match §4.15+§3; `.database_url` format correct; `.env.example` names match §12.14; no `.env` committed; tests are `unit`-marked and infra-free; if the mypy hook gained `additional_dependencies`, that change is justified in the PR body |

The PR body carries: `Closes #<issue>`, the behavioral-check results
(§7's table with observed outputs), the rollout results per machine, and
— once merged and verified — the explicit Phase-0 gate claim.

After merge, proceed to 0.4 (GitHub process: CODEOWNERS with the three
real usernames, PR template, labels/Milestones, squash-only hardening) —
which now has real teeth given the three-account setup.
