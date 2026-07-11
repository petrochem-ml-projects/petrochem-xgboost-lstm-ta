# Project Execution Plan

Derived from [CLAUDE.md](CLAUDE.md). Each phase is broken into PR-sized work
items (per the §12.4 squash-merge workflow), with dependencies and exit gates.

## Phase 0 — Repo bootstrap & team workflow (prerequisite to everything)

*Goal: a clean clone passes `uv sync` + pre-commit + empty test suite on all 3 machines.*

| # | Work item (≈1 PR each) | Key contents |
|---|---|---|
| 0.1 | `git init` + GitHub repo, branch protection | `main` protected: PR required, 1 approval, squash-only, required status checks; `.gitattributes` (force LF); `.gitignore` (`.env`, `.venv`, `reports/`, DVC cache) |
| 0.2 | Tooling skeleton | `pyproject.toml` with all extras from §12.1, `.python-version` (3.11), `uv.lock`, `.pre-commit-config.yaml`, ruff/mypy/pytest config (markers: `unit, integration, pipeline, e2e`) |
| 0.3 | Directory skeleton | §3 `mkdir` tree + `__init__.py` files; `config.py` stub; `.env.example` |
| 0.4 | GitHub process | `CODEOWNERS`, PR template (§12.5), labels + Milestones 1–7, Kanban board |
| 0.5 | CI pipeline v1 | `.github/workflows/ci.yml`: ruff → mypy → `pytest -m unit` (empty-pass) → docker build placeholders; weekly cross-platform matrix |

**Gate:** fresh clone → `uv sync --all-extras && pre-commit install && uv run pytest -m unit` green on macOS/Windows/Ubuntu.

---

## Phase 1 — `data_generator/` (§4)

*Goal: 4 synthetic processes in Postgres with recoverable lag structure.*

Build strictly in this order — each item is testable in isolation:

1. **`domain/spec.py`** — Pydantic v2 models (`Nonlinearity`, `TagSpec`, `TagContribution`, `TargetSpec`, `RegimeSpec`, `OutlierSpec`, `ProcessSpec` with unique-tag-name validation, `.tag_names`/`.target_names`). Unit tests: duplicate-name rejection, defaults.
2. **`domain/interfaces.py`** — the 8 ABCs (§4.2). No logic, but everything downstream imports these.
3. **`generators/latent.py`** — `ContiguousBlockRegimeScheduler` (seeded multinomial blocks ≥5%, deterministic per-regime shift/var-scale) + `OUProcessLatentGenerator` (OU discretization, single RNG seed at start). Test: identical latents across two calls.
4. **`generators/noise.py` + `transforms.py`** — `AR1NoiseGenerator`; `apply_nonlinearity` with the 5 kinds and `max(scale, 1e-6)` guard. Test each transform numerically.
5. **`generators/tags.py`** — `LinearNonlinearTagBuilder`, per-tag derived seeds (`random_seed` ⊕ tag index).
6. **`generators/targets.py`** — `LaggedNonlinearTargetBuilder`. ⚠️ **Most critical code in the project**: `lag_steps = round(lag_minutes / interval)`, target[t] sees tag[t − lag], back-fill first values, clip to min/max. Test the lag direction explicitly with a hand-built 2-tag spec.
7. **`generators/outliers.py`** — `RandomSpikeOutlierInjector` (seeded cells, ±k·column_std).
8. **`generators/simulator.py`** — `ConfigDrivenSimulator` (5 collaborators injected; targets from **clean** tags, outliers injected after) + `build_default_simulator()` factory.
9. **`specs/_builder_utils.py`** — `make_tags()` / `make_target_sources()` (strong coefs 0.8–2.0 for relevant tags, weak 0.02–0.15 decoys — this is what Phase 3's ground-truth test scores against).
10. **`specs/{fcc,te,dc,sda}.py` + `registry.py`** — 4 builders matching §4.11's table (FCC: 52 tags/8 targets/5-min, lags 10–50 min ±20% jitter; TE: 28/1 with 4 regimes; DC: 7/1; SDA: 65/1); `SPEC_BUILDERS` + `get_spec()`.
11. **`sinks/postgres_sink.py`** — `prepare()` (registry + variable catalog + per-process wide table, sanitized identifiers) and `write()` (chunked `to_sql`). Integration test via testcontainers.
12. **`cli.py` + `config.py`** — Typer `generate` / `generate-all` / `stream`; `Settings` with `.database_url`.
13. **`tests/test_generator.py`** — parametrized over all 4 specs: shape/finiteness/even spacing/regime range, reproducibility, clipping.
14. **Docker** — `data_generator/Dockerfile` (`--extra generator` only), `docker-compose.yml` with `postgres` + `data-generator`, profiles `dev/test/full`.
15. **Manual lag-recovery validation** (§4.7 acceptance) — sweep lags on FCC targets, confirm injected delays recovered within ~1 sampling interval for most targets. Document results in the PR.

**Gate (§4 DoD):** all 4 processes load into Postgres with correct counts; tests green; lag check passes; `docker compose up data-generator` works from clean clone. Tag `v0.1.0`.

---

## Phase 2 — EDA pipeline (§5)

*Depends on: Phase 1 data in Postgres.*

1. **`data_access/`** — `ProcessMeta` + `ProcessDataRepository` ABC, then `PostgresProcessDataRepository` (reads the Phase-1 metadata tables; never hardcodes columns). Integration test.
2. **`mlops/` foundation** — `RunLogger`/`ExperimentTracker` ABCs, `NoOpExperimentTracker`, lazy `MLflowExperimentTracker`, `build_tracker()` with fall-back-on-failure. Test: bad tracking URI → no exception.
3. **`eda/plotting.py` + `eda/interfaces.py`** — Agg backend module; `AnalyzerResult` dataclass + `Analyzer` ABC with `input_columns`/`target_columns` helpers.
4. **7 analyzers**, one PR each or batched 2–3: Missingness, IQROutlier (multiplier 3.0), Distribution (target histograms only), Stationarity (ADF on 3000-row tail, skip near-constant cols), Correlation (input-input + input-target heatmaps, top-k table), **LagRecovery** (the paper-specific one — top-15 candidates by zero-lag corr, sweep 0–40 lag steps, `lag_gain` table; must use only `df/catalog/meta`, no generator imports), Regime. Each with a unit test on a small hand-built DataFrame + fake catalog.
5. **`eda/report.py`** — single self-contained HTML, base64-embedded PNGs, one section per analyzer.
6. **`eda/pipeline.py` + `eda/cli.py`** — `EDAPipeline` (repo + analyzers + report + tracker injected), `build_default_analyzers()`, Typer `run`/`run-all`.
7. **Validation** — run `run-all`, eyeball all 4 reports; confirm LagRecovery shows positive `lag_gain` on FCC (cross-check against Phase 1's known lags — manually, not in code).

**Gate (§5 DoD):** 4 rendering reports; ≥80% coverage on `ml_pipeline/eda/`; MLflow-optional verified. Tag `v0.2.0`.

---

## Phase 3 — Preprocessing & feature selection (§6)

*Depends on: Phase 2's repository. MLflow still optional.*

1. **`preprocessing/interfaces.py`** — `Transformer` ABC (fit/transform/fit_transform, picklable) + separate `WindowBuilder` ABC.
2. **`OneClassSVMDenoiser`** — internal StandardScaler → OneClassSVM(rbf, nu=0.05) → flag rows → **interpolate, don't drop**; `outlier_mask_` attribute. Test: plant obvious spikes, assert flagged + smoothed, timeline length unchanged.
3. **`StandardScalerTransformer`** — with the anti-leak test (fitted mean == train-slice mean exactly, ≠ full-dataset mean).
4. **`SlidingWindowTransformer`** — `X[i] = features[i:i+w]`, `y[i] = target[i+w]`. Test shapes and the past→future direction with a ramp series.
5. **`preprocessing/schemas.py`** — pandera schemas (raw + post-denoise no-NaN); test that corrupted frames are rejected.
6. **`feature_selection/`** — `FeatureSelector` ABC + `XGBoostFeatureSelector` (`importance_type="gain"`, full ranked table exposed).
7. **`PreprocessingPipeline`** — denoise → scale → select → window composition; `save()`/`load()` via joblib. Test: round-trip produces identical `transform()` output.
8. **Ground-truth test** (§6.8) — the *one* module allowed to import `data_generator.specs`: recall@10 of true source tags ≥0.6 on FCC targets. This is the phase's core validation.

**Gate (§6 DoD):** all four component test suites + round-trip + ground-truth recall green. Tag `v0.3.0`.

---

## Phase 4 — Models, dual backend, Optuna (§7)

*Depends on: Phase 3. MLflow now **required** (`test` profile).*

1. **`models/interfaces.py`** — `BaseForecaster` ABC (numpy-only I/O, save/load, `backend_name`).
2. **`torch_backend/lstm_ta.py`** — encoder LSTM → Bahdanau attention (`v^T tanh(W_h h_i + W_d d)`) → context ⊕ final hidden → dense scalar. Adam/MSE, early stopping on val, `state_dict` save/load.
3. **`keras_backend/lstm_ta.py`** — same architecture and hyperparameter surface via functional API + `AdditiveAttention`/custom layer, `EarlyStopping(restore_best_weights=True)`.
4. **`models/factory.py`** — `ModelFactory.build(backend, **hp)`; only file importing both backends.
5. **`training/splits.py`** — `chronological_split(0.70/0.15)`, never shuffled.
6. **`mlops/` extension** — `ModelRegistry` ABC + `MLflowModelRegistry` using **aliases** (`@champion`), not deprecated stages.
7. **`training/optuna_search.py`** — search space (hidden_size {64…256}, window_size {6,12,18,24}, dropout 0–0.5, log-uniform LR), MedianPruner, nested MLflow runs.
8. **`training/trainer.py`** — full orchestration: load → split → fit preprocessing on train → Optuna vs. val → refit best → evaluate on test (first touch) → register model + companion preprocessing artifact.
9. **`tests/test_model_conformance.py`** — parametrized over both backends: shape, save/load round-trip, beats predict-the-mean baseline. This is the Liskov check.
10. **Sanity run** — both backends, same seed/hyperparams, on DC (smallest: 7 tags, 2,394 rows) — compare loss curves for degenerate-backend bugs before scaling to FCC/SDA.

**Gate (§7 DoD):** conformance green both backends; Optuna beats defaults; `Trainer.run()` registers a model with test metrics. Tag `v0.4.0`.

---

## Phase 5 — MLOps: metrics, DVC, Airflow (§8)

*Depends on: Phase 4. Full compose stack lands here.*

1. **`evaluation/metrics.py` first** — MSE/RMSE/MAE/MAPE/R², the *only* implementation anywhere; retrofit Phase 4's Optuna objective and Trainer to call it. Unit test against sklearn reference values.
2. **`evaluation/visuals.py`** — radar, error boxplots, fit curves, R² scatter, parametrized over `(name, y_true, y_pred)` so torch/keras/naive plot together.
3. **DVC** — `params.yaml`, `dvc.yaml` stages (`generate → eda → preprocess → select_features → train[foreach] → evaluate`), MinIO local remote, R2 remote with `--local` creds.
4. **Airflow** — `dags/petrochem_dag_factory.py` (`build_dag(process)` looped over `SPEC_BUILDERS`); tasks call existing CLIs, no logic in DAG files; LocalExecutor + separate metadata DB.
5. **Full `docker-compose.yml`** — add mlflow/minio/airflow×2/pipeline services under `profiles: ["full"]`.
6. **CI additions** — nightly `pipeline`-tier job (`dvc repro` smoke).

**Gate (§8 DoD):** `dvc repro` reproducible from clean clone (byte-identical second run); one DAG green unattended; comparison visuals for all 4 processes. Tag `v0.5.0`.

---

## Phase 6 — Serving + RAG (§9)

*Depends on: a registered `@champion` model (Phase 4/5).*

**Serving track:**

1. `serving/schemas.py` — `PredictRequest` (raw readings XOR `use_latest`, model-validator enforced) + `PredictResponse`.
2. `serving/dependencies.py` — `Depends()` factories reusing existing ABCs.
3. `routers/predict.py` — resolve window → `get_by_alias(..., "champion")` → load companion `PreprocessingPipeline` → `ModelFactory`/`BaseForecaster.load` → predict. One code path for both input modes.
4. `routers/processes.py` + `routers/models.py` + `main.py` (`/health`, Prometheus `Instrumentator` one-liner).
5. `tests/serving/test_predict.py` — TestClient + `dependency_overrides` fakes, zero infra.

**RAG track (parallelizable):**

6. `ml_pipeline/rag/interfaces.py` — `Chunk`, `DocumentChunker`, `EmbeddingModel`, `VectorStore`, `AnswerGenerator`.
7. Chunkers (`MarkdownSectionChunker`, `EdaResultChunker` reusing `AnalyzerResult` objects), `SentenceTransformerEmbedder` (all-MiniLM-L6-v2), `PgVectorStore` (`rag_chunks`, upsert-on-source idempotent).
8. `rag/cli.py` (`index`, `index-docs`) + `routers/ask.py` (`OllamaAnswerGenerator`, answers cite sources).

**Infra:** swap postgres image → `pgvector/pgvector:pg16`; add `ollama` service + `llama3.2:3b` pull; serving Dockerfile (`serving+preprocessing+rag` extras); Prometheus + Grafana services and a request-rate/latency panel.

**Gate (§9 DoD):** both predict modes work; `/models` reflects registry; `/metrics` scraped into a Grafana panel; `/ask` answers 3 test questions with citations; API tests pass without infra. Tag `v0.6.0`.

---

## Phase 7 (stretch) — Feast (§10)

Only after 1–6 are solid: `feast[postgres]` as offline+online store+registry on the existing Postgres; `FeatureView`s over Phase-3-selected features; point `predict.py`'s `use_latest` mode at the online store. Tag `v0.7.0`.

---

## Cross-cutting rules to hold every PR to

- **Dependency direction:** concrete classes only in factories (`build_default_simulator`, `build_default_analyzers`, `ModelFactory`, `serving/dependencies.py`); everything else imports ABCs.
- **Ground-truth firewall:** only `tests/test_feature_selection_ground_truth.py` may import both `data_generator.specs` and `ml_pipeline` — enforce in review.
- **One metrics implementation, one split function, one preprocessing artifact** shared between train and serve.
- **Per-PR DoD** (§12.18): tests at the right tier, ruff/mypy/CI green, docs updated, squash-merged with a Conventional-Commit title.

**Critical path:** 0 → 1 → 2 → 3 → 4 → 5 → 6; the riskiest items are Phase 1 item 6 (lag direction — everything downstream validates against it) and Phase 4 items 2–3 (attention correctness in two frameworks). Phase 2's analyzers, Phase 6's RAG track, and all Docker work are the natural parallelization points for the 3-person split (§12.3).
