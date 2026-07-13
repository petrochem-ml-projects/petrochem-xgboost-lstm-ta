# CLAUDE.md

Operating reference and **build guide** for this repository, covering the
full project end to end. Nothing in this repo exists yet — every phase
below is written as a from-zero implementation guide with precise
contracts, algorithms, and acceptance criteria, not a description of code
that's already there. Work through the phases in order; each depends only
on the ones before it.

If code ever conflicts with this document, this document wins (or gets
updated via PR if the decision genuinely changed).

## 1. What this project is

An end-to-end implementation of **"Efficient prediction framework for
large-scale nonlinear petrochemical process based on feature selection and
temporal-attention LSTM"** (Long et al., *Chemical Engineering Science* 301
(2025) 120733), on **synthetic** data (the paper's Sinopec data is
confidential).

Two core services plus a serving layer:
1. **`data_generator/`** — simulates 4 processes from the paper (FCC,
   Tennessee Eastman, Debutanizer Column, Solvent Deasphalting) with
   nonlinear, cross-correlated, regime-shifting, time-lagged synthetic
   sensor data. Writes to Postgres.
2. **`ml_pipeline/`** — EDA, XGBoost feature selection, LSTM + temporal
   attention (PyTorch *and* Keras), Optuna search, evaluation, MLOps.
3. **`serving/`** — FastAPI service exposing trained models for prediction.

Secondary goal: real Git/GitHub team-workflow practice across 3 machines
(§14) — the repo should be initialized under that workflow from commit 1,
not bolted on later.

## 2. Architecture principles (apply to every phase)

- **SOLID.** One class per concern, behind ABCs, concrete wiring isolated
  to small factory functions (e.g. `build_default_simulator()`).
- **Config-driven, not hardcoded.** One simulation engine driven by a
  `ProcessSpec`; a 5th process later means a new spec, not new engine code.
- **Repository pattern.** `ml_pipeline` never queries Postgres directly —
  always through a `ProcessDataRepository` interface, discovering
  tag/target roles from metadata tables, never hardcoded column lists.
- **Graceful degradation for MLOps.** Every pipeline stage takes an
  `ExperimentTracker`; a `NoOpExperimentTracker` lets everything run with
  zero MLflow infrastructure.
- **Dependency Inversion everywhere.** High-level orchestration code
  (`ConfigDrivenSimulator`, `EDAPipeline`, FastAPI routers) depends only on
  ABCs, never on concrete classes — this is also what makes FastAPI's
  `Depends()` system a natural fit later (Phase 6).
- **Framework-agnostic model boundary.** `BaseForecaster` operates on plain
  numpy arrays; training/evaluation/serving code never imports `torch` or
  `tensorflow` directly.

## 3. Prerequisites & environment setup (do this first)

Full tooling rationale and the one-command setup live in §12.1
(Standardized Development Environment) — this section is just the repo
skeleton, since it has to exist before `uv sync` has anything to install
against.

```bash
# 1. Install prerequisites (once per machine): Python 3.11 via uv, Docker Desktop
curl -LsSf https://astral.sh/uv/install.sh | sh   # macOS/Linux; see §12.1 for Windows
docker --version

# 2. Repo skeleton
mkdir -p data_generator/{domain,generators,specs,sinks} \
         ml_pipeline/{data_access,eda/analyzers,preprocessing,feature_selection,models/torch_backend,models/keras_backend,training,evaluation,mlops} \
         serving/routers \
         dags configs/processes scripts tests
touch $(find data_generator ml_pipeline serving -type d -printf '%p/__init__.py ')
touch tests/__init__.py

# 3. From here on, use the one-command setup in §12.1:
#    uv sync --all-extras && pre-commit install && docker compose --profile dev up -d
```

Create `.env` from `.env.example` (Postgres host/port/db/user/password;
`localhost`/`5432`/`petrochem`/`petrochem`/`petrochem` is fine for local
dev). Never commit `.env`. Naming conventions for env vars are in §12.14.

## 4. Phase 1 build guide — `data_generator/`

**Build order** (each step depends only on prior steps):

### 4.1 `data_generator/domain/spec.py` — the config contract

Pydantic v2 models. This is the single source of truth both the engine and
the Postgres schema manager read from.

- `Nonlinearity(str, Enum)`: `IDENTITY`, `TANH`, `SQUARE`, `LOG1P`, `SIGMOID`
- `TagSpec`: `name: str`, `unit: str = ""`, `description: str = ""`,
  `latent_weights: Dict[int, float] = {}` (latent index -> linear weight),
  `base_value: float = 0.0`, `nonlinearity: Nonlinearity = IDENTITY`,
  `nonlinear_scale: float = 1.0`, `ar_coef: float = 0.3` (AR(1)
  autocorrelation of sensor noise), `noise_std: float = 1.0`
- `TagContribution`: `tag: str`, `coef: float`, `lag_minutes: float = 0.0`
  — one input tag's weighted, time-lagged contribution to a target
- `TargetSpec`: `name`, `unit=""`, `description=""`, `base_value=0.0`,
  `sources: List[TagContribution] = []`, `nonlinearity=IDENTITY`,
  `nonlinear_scale=1.0`, `noise_std=0.1`, `min_value/max_value:
  Optional[float] = None` (post-hoc clip)
- `RegimeSpec`: `n_regimes=3`, `latent_mean_shift_scale=1.5`,
  `latent_var_scale_min=0.7`, `latent_var_scale_max=1.4`, `seed=0`
- `OutlierSpec`: `fraction=0.01`, `magnitude_std_multiplier=8.0`, `seed=1`
- `ProcessSpec`: `process_name`, `description=""`, `n_latent_states: int`,
  `latent_theta: float = 0.05` (OU mean-reversion speed), `latent_sigma:
  float = 1.0` (OU diffusion volatility), `sampling_interval_minutes:
  float`, `n_samples: int`, `start_timestamp: str = "2024-01-01T00:00:00"`,
  `tags: List[TagSpec]`, `targets: List[TargetSpec]`, `regimes: RegimeSpec
  = RegimeSpec()`, `outliers: OutlierSpec = OutlierSpec()`, `random_seed:
  int = 42`. Validate tag names are unique. Expose `.tag_names` and
  `.target_names` convenience properties.

**Acceptance**: instantiate a `ProcessSpec` with a couple of tags/targets
and confirm validation rejects duplicate tag names.

### 4.2 `data_generator/domain/interfaces.py` — the ABCs

Every generator implements exactly one of these (Interface Segregation —
each interface is narrow):

- `LatentStateGenerator.generate(spec, regime_labels: np.ndarray) ->
  np.ndarray` — shape `(n_samples, n_latent_states)`
- `RegimeScheduler`: `build_labels(spec) -> np.ndarray` (int array, shape
  `(n_samples,)`); `regime_latent_shift(spec, regime_id) -> np.ndarray`
  (shape `(n_latent_states,)`); `regime_latent_var_scale(spec, regime_id)
  -> float`
- `NoiseGenerator.generate(n_samples, ar_coef, std, seed) -> np.ndarray`
- `TagBuilder.build(spec, latents) -> pd.DataFrame` (columns = tag_names)
- `TargetBuilder.build(spec, tags_df) -> pd.DataFrame` (columns =
  target_names)
- `OutlierInjector.inject(spec, tags_df) -> pd.DataFrame`
- `ProcessSimulator.simulate(spec) -> pd.DataFrame` (full output:
  `ts`, `regime_label`, all tags, all targets)
- `DataSink`: `prepare(spec) -> None` (schema setup), `write(spec, df) ->
  int` (rows written)

### 4.3 `data_generator/generators/latent.py`

**`ContiguousBlockRegimeScheduler`**: splits `n_samples` into
`regimes.n_regimes` contiguous blocks via a seeded multinomial split (each
block >=5% of samples), returns the repeated-label array. Each regime's
`regime_latent_shift` is a seeded `N(0, latent_mean_shift_scale)` draw
*per latent dimension*, deterministic given `(spec.regimes.seed,
regime_id)` — i.e. call it twice with the same args, get the same answer.
Same determinism requirement for `regime_latent_var_scale` (seeded
`Uniform(var_scale_min, var_scale_max)`).

**`OUProcessLatentGenerator`**: takes a `RegimeScheduler` in its
constructor. Simulates each latent dimension as an Ornstein-Uhlenbeck
process, discretized with `dt = 1`:

```
state_0 ~ N(0, latent_sigma)
for t in 0..n_samples-1:
    mu = regime_scheduler.regime_latent_shift(spec, regime_labels[t])
    sigma_eff = latent_sigma * regime_scheduler.regime_latent_var_scale(spec, regime_labels[t])
    dw ~ N(0, sqrt(dt)), one draw per latent dim
    state = state + latent_theta * (mu - state) * dt + sigma_eff * dw
    x[t] = state
```

Seed the RNG once from `spec.random_seed` at the start of `generate()` (not
per-timestep) so the whole trajectory is reproducible from one seed.

**Acceptance**: same `ProcessSpec` (same seeds) -> identical latent array
across two calls.

### 4.4 `data_generator/generators/noise.py`

**`AR1NoiseGenerator`**: `e[0] = innovation[0]`; `e[t] = ar_coef * e[t-1] +
innovation[t]` for `t >= 1`, where `innovation ~ N(0, std)`, seeded RNG.

### 4.5 `data_generator/generators/transforms.py`

`apply_nonlinearity(x, kind, scale)`:
- `IDENTITY`: `x`
- `TANH`: `tanh(scale * x) / scale`
- `SQUARE`: `sign(x) * (scale * x)**2 / scale`
- `LOG1P`: `sign(x) * log1p(abs(scale * x)) / scale`
- `SIGMOID`: `1 / (1 + exp(-scale * x))`

Guard against `scale` near 0 (use `max(scale, 1e-6)` as divisor) so a
misconfigured spec can't divide by zero.

### 4.6 `data_generator/generators/tags.py`

**`LinearNonlinearTagBuilder(noise_generator)`**: for each `TagSpec`,
compute `linear = latents[:, latent_weight_indices] @ weights` (zero
vector if no `latent_weights`), then `tag_value = base_value +
apply_nonlinearity(linear, nonlinearity, nonlinear_scale) +
noise_generator.generate(n_samples, ar_coef, noise_std, seed=<derived per
tag>)`. Derive a distinct, deterministic seed per tag (e.g. combine
`spec.random_seed` with the tag's index) so tags don't share identical
noise.

### 4.7 `data_generator/generators/targets.py`

**`LaggedNonlinearTargetBuilder(noise_generator)`**: for each `TargetSpec`,
for each `TagContribution` in `.sources`: `lag_steps =
round(lag_minutes / spec.sampling_interval_minutes)`; shift the source
tag's series forward by `lag_steps` (i.e. `target[t]` sees `tag[t -
lag_steps]`), back-filling the first `lag_steps` values with the tag's
first observed value (no NaNs). Sum `coef * lagged_series` across all
sources -> `linear`. Then `target_value = base_value +
apply_nonlinearity(linear, ...) + noise`, clipped to `[min_value,
max_value]` if set. **This lag mechanic is the single most important piece
of the whole synthetic dataset** — it's what gives temporal-attention
models something real to exploit that a memoryless model can't. Get the
direction right: a *later* target value depends on an *earlier* tag value.

**Acceptance** (do this check yourself once Phase 1 is complete — it's the
project's core validation): generate a spec, and for a target's dominant
source tag, sweep lag steps 0..N and compute
`np.corrcoef(tag_shifted_by_lag, target)`; confirm the lag that maximizes
`|corr|` lands close to the configured `lag_minutes`. Expect most but not
necessarily all targets to recover cleanly — targets with several
similarly-weighted lagged sources are genuinely ambiguous from correlation
alone, which is fine (even useful — it's what Phase 3's feature selection
should resolve better than naive correlation).

### 4.8 `data_generator/generators/outliers.py`

**`RandomSpikeOutlierInjector`**: pick `fraction * n_rows * n_cols` random
`(row, col)` cells among tag columns (seeded), add `+/-magnitude_std_multiplier
* column_std` to each selected cell. This models sensor faults — it's what
gives the EDA outlier analyzer and Phase 3's `OneClassSVM` denoiser
something real to find.

### 4.9 `data_generator/generators/simulator.py`

**`ConfigDrivenSimulator`** — constructor takes all 5 collaborators
(`RegimeScheduler`, `LatentStateGenerator`, `TagBuilder`, `TargetBuilder`,
`OutlierInjector`) by interface. `simulate(spec)`:
1. `regime_labels = regime_scheduler.build_labels(spec)`
2. `latents = latent_generator.generate(spec, regime_labels)`
3. `clean_tags_df = tag_builder.build(spec, latents)`
4. `targets_df = target_builder.build(spec, clean_tags_df)` — **targets
   are derived from the clean signal**, not the outlier-corrupted one (a
   sensor fault shouldn't retroactively change how much product was made)
5. `observed_tags_df = outlier_injector.inject(spec, clean_tags_df)`
6. Build `ts` via `pd.date_range(start=spec.start_timestamp,
   periods=spec.n_samples, freq=Timedelta(minutes=sampling_interval_minutes))`
7. Concatenate `ts`, `regime_label`, `observed_tags_df`, `targets_df` into
   one DataFrame and return it.

Also write `build_default_simulator()` — a factory function wiring the
concrete classes above, so callers never import concrete generator classes
directly (only this one function needs to change if you swap an
implementation).

### 4.10 `data_generator/specs/_builder_utils.py` — procedural spec building

Hand-writing 52+ `TagSpec` entries doesn't scale. Write two seeded helper
functions:
- `make_tags(n_tags, n_latent, seed, name_prefix, max_latents_per_tag=3) ->
  List[TagSpec]`: each tag depends on 1..max_latents_per_tag randomly
  chosen latents with random weights, random nonlinearity, random
  `ar_coef`/`noise_std` within sane ranges.
- `make_target_sources(relevant_tags, relevant_lags_minutes,
  all_tag_names, seed, n_weak_random=4) -> List[TagContribution]`: strong
  coefficients (e.g. `Uniform(0.8, 2.0)` x random sign) for the
  "genuinely relevant" tags at their specified lags, plus a handful of
  near-negligible coefficients (e.g. `Uniform(0.02, 0.15)`) on random
  *other* tags — this is what makes feature selection meaningful later:
  there's a real, recoverable importance ranking to check against.

### 4.11 `data_generator/specs/{fcc,te,dc,sda}.py`

One `build_<name>_spec(n_samples=..., sampling_interval_minutes=...) ->
ProcessSpec` function per process, using `make_tags`/`make_target_sources`.
Match the paper's stated dimensions and delays:

| Process | Tags | Targets | Default n_samples | Interval | Notes |
|---|---|---|---|---|---|
| `fcc` | 52 | 8: `gasoline_yield`(~50min lag), `diesel_yield`(~10min), `slurry_yield`(~15min), `liquefied_gas_yield`(~30min), `dry_gas_yield`(~20min), `nox_content`/`co2_content`/`so2_content`(~18min each) | 2,600 | 5 min | Lags per paper Section 2.2; jitter each source tag's lag +/-20% around the nominal value |
| `te` | 28 | 1: `purge_c` | 28,800 | 0.6 min | `regime_label` doubles as the paper's 4 operating modes (`RegimeSpec(n_regimes=4)`) |
| `dc` | 7 | 1: `c4_yield` | 2,394 | 10 min | |
| `sda` | 65 | 1: `dao_yield` | 25,000 | 5 min | |

### 4.12 `data_generator/specs/registry.py`

`SPEC_BUILDERS: Dict[str, Callable[..., ProcessSpec]]` mapping process name
-> builder function; `get_spec(process_name, **overrides) -> ProcessSpec`
raising `KeyError` with the available names listed if unknown. This is the
one file that knows about all 4 processes — everything else only ever
sees a `ProcessSpec`.

### 4.13 `data_generator/sinks/postgres_sink.py`

**`PostgresDataSink(database_url)`** implementing `DataSink`:

- `prepare(spec)`: creates (if not exists) two **shared** metadata tables
  and one **per-process** wide table:
  - `process_registry(process_name PK, description, sampling_interval_minutes,
    n_latent_states, n_tags, n_targets)` — upserted per process
  - `process_variable_catalog(process_name, variable_name, role
    CHECK IN ('input','target'), unit, description, PK(process_name,
    variable_name))` — one row per tag and per target, upserted
  - `{process_name}_data(id BIGSERIAL PK, ts TIMESTAMPTZ, regime_label
    INT, <one DOUBLE PRECISION column per tag+target>, UNIQUE(ts))` plus
    an index on `ts`. Sanitize column/table identifiers (replace any
    non-alphanumeric/underscore character with `_`) before building DDL —
    never string-interpolate raw user/spec input into SQL otherwise.
- `write(spec, df)`: bulk insert via `df.to_sql(table, engine,
  if_exists="append", method="multi", chunksize=1000)`, return row count.

**Acceptance**: after `prepare()` + `write()`, `SELECT count(*) FROM
{process}_data` matches `len(df)`, and `process_variable_catalog` has
exactly `n_tags + n_targets` rows for that process.

### 4.14 `data_generator/cli.py`

Typer app, 3 commands:
- `generate --process <name> [--n-samples N] [--database-url URL]` — build
  spec (override `n_samples` if given), simulate, `prepare()` + `write()`.
- `generate-all [--n-samples N] [--database-url URL]` — loop over
  `SPEC_BUILDERS`.
- `stream --process <name> [--batch-size 50] [--interval-seconds 5.0]
  [--n-batches 0]` — daemon mode: repeatedly simulate a small batch, re-anchor
  its timestamps so the last row lands at "now" (`offset = now -
  df.ts.iloc[-1]`, then `df.ts += offset`), write, sleep. `n_batches=0`
  means run forever. Note in a comment that AR-noise/latent continuity
  across batch boundaries is only approximate — acceptable for demoing a
  live pipeline, not for exact reproducibility.

### 4.15 `config.py` (repo root)

`Settings(BaseSettings)` (pydantic-settings, reads `.env`):
`postgres_host/port/db/user/password`, `mlflow_tracking_uri`,
`airflow_api_url` (add when Phase 5 needs it). Expose a `.database_url`
property building the `postgresql+psycopg2://...` SQLAlchemy URL.

### 4.16 `tests/test_generator.py`

Parametrize over `SPEC_BUILDERS.keys()`, small `n_samples` (e.g. 200) for
speed:
- **spec builds**: `get_spec(name, n_samples=N)` returns a valid spec;
  tag names unique.
- **shape & finiteness**: `simulate()` output has `N` rows, contains
  `ts`, `regime_label`, all tag/target columns; every tag/target value is
  finite (no NaN/inf); `ts` is strictly evenly spaced; `regime_label`
  values are within `[0, n_regimes)`.
- **reproducibility**: two calls to `get_spec()` + `simulate()` with the
  same process/args produce identical target arrays (same seeds means
  deterministic).
- **target clipping**: any target with `min_value` set never goes below it
  in the output.

### 4.17 Docker

`data_generator/Dockerfile` — slim Python base with `uv` installed, copy
`pyproject.toml` + `uv.lock` + `config.py` + `data_generator/`, run `uv
sync --extra generator --no-dev --frozen` (installs only the `generator`
extra defined in §12.1 — keeps this image lean, no torch/tensorflow/etc.
bleeding into it), entrypoint `uv run python -m data_generator.cli`.

`docker-compose.yml` — `postgres` (official image, env-driven
user/pass/db, named volume, healthcheck, `profiles: ["dev","test","full"]`
per §12.2), `data-generator` (build from the Dockerfile above,
`depends_on: postgres` with `condition: service_healthy`, default command
`generate-all`). `mlflow` and `minio` join later (§12.2 has the full
profile-by-service table) — they're inert
until something uses them.

### Phase 1 — Definition of Done

- [ ] All 4 processes generate into Postgres without error, correct
      tag/target counts per Section 4.11's table
- [ ] `pytest tests/test_generator.py -v` — all green
- [ ] Manual lag-recovery check (Section 4.7 acceptance) shows the injected
      delay recovered (within ~1 sampling interval) for the majority of
      FCC targets
- [ ] `docker compose up data-generator` works from a clean clone

## 5. Phase 2 build guide — `ml_pipeline/` (EDA)

**Build order:**

### 5.1 `ml_pipeline/data_access/interfaces.py`

`ProcessMeta` (frozen dataclass): `process_name, description,
sampling_interval_minutes, n_latent_states, n_tags, n_targets`.

`ProcessDataRepository` ABC:
- `list_processes() -> List[str]`
- `get_metadata(process_name) -> ProcessMeta`
- `get_variable_catalog(process_name) -> pd.DataFrame` (columns:
  `variable_name, role, unit, description`)
- `load_data(process_name, columns=None, limit=None, offset=None) ->
  pd.DataFrame` (returns `ts, regime_label` + requested/all tag+target
  columns, ordered by `ts` ascending)
- `row_count(process_name) -> int`

### 5.2 `ml_pipeline/data_access/postgres_repository.py`

`PostgresProcessDataRepository(database_url)` implementing the above by
querying the tables Phase 1's sink created (`process_registry`,
`process_variable_catalog`, `{process}_data`). Same identifier-sanitizing
discipline as Section 4.13. Drop the `id` column from `load_data()`'s
result if present (internal PK, not analytically useful).

### 5.3 `ml_pipeline/eda/plotting.py`

One-liner setup module: `import matplotlib; matplotlib.use("Agg"); import
matplotlib.pyplot as plt` plus a couple of `rcParams` tweaks. **Every**
analyzer module imports `plt` from here, never straight from matplotlib —
this environment has no display.

### 5.4 `ml_pipeline/eda/interfaces.py`

`AnalyzerResult` (dataclass): `name: str, title: str, tables:
Dict[str, pd.DataFrame] = {}, figures: Dict[str, Figure] = {}, summary:
Dict[str, Any] = {}` (small scalars, safe to log as MLflow metrics),
`notes: str = ""`.

`Analyzer` ABC: `analyze(df, catalog, meta) -> AnalyzerResult`. Add two
`@staticmethod` helpers every analyzer will use: `input_columns(catalog)`
and `target_columns(catalog)` (filter `catalog` by `role`).

### 5.5 `ml_pipeline/eda/analyzers/` — implement each as its own class

| Analyzer | What it computes |
|---|---|
| `MissingnessAnalyzer` | `%` missing per column; bar chart of nonzero columns; note that ~0% is expected by design (this synthetic data models sensor *faults*, not dropout) |
| `IQROutlierAnalyzer` | Per column: IQR fence with a **wide** multiplier (default 3.0) so only genuine spikes count, not ordinary process variance; `n_outliers`/`pct_outliers` table, top-20 bar chart |
| `DistributionAnalyzer` | mean/std/min/max/skew/kurtosis per column (`scipy.stats.skew`/`kurtosis`); histogram grid for **target columns only** (inputs can number in the dozens) |
| `StationarityAnalyzer` | ADF test (`statsmodels.tsa.stattools.adfuller`, `autolag="AIC"`) per column, run on the **tail** of the series (cap e.g. 3000 rows) for tractability; skip columns with `nunique() < 5`; `is_stationary = pvalue < 0.05`; pie chart of stationary vs not |
| `CorrelationAnalyzer` | Input-input Pearson correlation heatmap (no per-cell annotation — can be 50x50+); input-target heatmap (annotated ticks); top-k (default 10) correlation-ranked tags per target table |
| `LagRecoveryAnalyzer` | **The paper-specific one.** For each target: rank input tags by absolute zero-lag correlation, take the top N (default 15) as candidates; for each candidate, sweep lag steps `0..max_lag_steps` (default 40), compute `corrcoef(tag_shifted_by_lag, target)` at each, record the lag that maximizes the absolute correlation; table of `target, tag, best_lag_minutes, best_corr, corr_at_lag0, lag_gain` (`lag_gain = abs(best_corr) - abs(corr_at_lag0)`); line-plot the top 5 tags' correlation-vs-lag curves per target. **Must not access the data generator's ground truth** — this has to work the same way it would on real plant data, using only `(df, catalog, meta)` |
| `RegimeAnalyzer` | Rows-per-regime counts/pct + bar chart; target-by-regime boxplots; per-target `max_regime_mean_shift` table |

Each `analyze()` returns figures as real `matplotlib.figure.Figure`
objects (don't call `plt.show()` — the report builder embeds them).

### 5.6 `ml_pipeline/eda/report.py`

`HtmlEDAReportBuilder.build(process_name, meta, df, results:
List[AnalyzerResult], output_dir) -> Path`. Produces **one self-contained
HTML file** (`eda_report_{process_name}.html`) — no external JS/CSS, every
figure embedded as base64 PNG (`fig.savefig(buf, format="png"); base64
.b64encode(buf.getvalue())`). Header shows process/meta summary; one
`<section>` per analyzer with: summary-metric badges, notes callout,
figures, then tables (`df.to_html()`). This makes the report trivially
loggable as a single MLflow artifact.

### 5.7 `ml_pipeline/mlops/` — experiment tracking abstraction

`interfaces.py`: `RunLogger` ABC (`log_param`, `log_metric(key, value,
step=None)`, `log_artifact(local_path)`); `ExperimentTracker` ABC
(`start_run(experiment_name, run_name=None)` — a **context manager**
yielding a `RunLogger`).

`noop_tracker.py`: `NoOpExperimentTracker` — Null Object; every method is a
no-op. Lets every pipeline stage run and be unit-tested without any MLflow
infrastructure.

`mlflow_tracker.py`: `MLflowExperimentTracker(tracking_uri)` — lazily
imports `mlflow` inside `__init__` (keep it an optional dependency),
`start_run` wraps `mlflow.set_experiment` + `mlflow.start_run` as a
`@contextmanager`.

`factory.py`: `build_tracker(tracking_uri, enabled=True) ->
ExperimentTracker` — tries to build the MLflow tracker, falls back to
`NoOpExperimentTracker` on any import/connection error (log a warning, but
never crash the pipeline over unreachable MLOps infra).

### 5.8 `ml_pipeline/eda/pipeline.py`

`EDAPipeline(repository, analyzers: List[Analyzer], report_builder=None,
tracker=None)`. `run(process_name, output_dir, row_limit=None) -> Path`:
1. Load `meta`, `catalog`, `df` from the repository
2. Run every analyzer, collect `List[AnalyzerResult]`
3. Build the HTML report
4. Inside `tracker.start_run(f"eda_{process_name}")`: log basic params
   (`process_name`, `n_rows`, `n_tags`, `n_targets`), log every analyzer's
   `summary` dict as metrics (fall back to `log_param` if a value isn't
   numeric), log the report file as an artifact
5. Return the report path

`build_default_analyzers() -> List[Analyzer]` — factory wiring all 7
analyzers from Section 5.5 (Open/Closed: add an 8th analyzer here later
without touching `EDAPipeline`).

### 5.9 `ml_pipeline/eda/cli.py`

Typer app: `run --process <name> [--output-dir ./reports] [--row-limit 0]
[--database-url URL] [--track/--no-track]` and `run-all` (loops
`repository.list_processes()`).

### Phase 2 — Definition of Done

- [ ] `python -m ml_pipeline.eda.cli run-all` produces a rendering HTML
      report for all 4 processes with no errors
- [ ] Every analyzer has a unit test (small synthetic DataFrame + fake
      catalog, no DB needed) — target >=80% coverage on `ml_pipeline/eda/`
- [ ] `LagRecoveryAnalyzer`'s output is sane on the FCC data: at least
      several targets show a positive `lag_gain` for their top candidate
      tag
- [ ] Pipeline runs identically whether or not MLflow is reachable
      (`NoOpExperimentTracker` fallback verified by a test that points at
      a bad tracking URI and confirms no exception)

## 6. Phase 3 build guide — Preprocessing & Feature Selection

**Build order:**

### 6.1 `ml_pipeline/preprocessing/interfaces.py`

`Transformer` ABC (scikit-learn-style, but explicit about our own
contract): `fit(df, catalog, meta) -> Transformer` (mutates and returns
`self`, stores fitted state as instance attributes), `transform(df) ->
pd.DataFrame`, and a default `fit_transform(df, catalog, meta) ->
pd.DataFrame` calling both. Every `Transformer` must be picklable
(`joblib`-serializable) — this is what lets a *fitted* pipeline be bundled
as a model-registry artifact in Phase 6 and reused unchanged at serving
time.

Separately, `WindowBuilder` ABC (different shape of contract — not a
`Transformer`, Interface Segregation applies): `build(df, feature_cols,
target_col, window_size) -> Tuple[np.ndarray, np.ndarray]` returning `X`
of shape `(n_samples - window_size, window_size, n_features)` and `y` of
shape `(n_samples - window_size,)`.

### 6.2 `ml_pipeline/preprocessing/outlier_denoiser.py`

**`OneClassSVMDenoiser(Transformer)`** — per the paper's own approach
("one-support vector machines (SVM) is employed for identifying and
eliminate anomalies"). Internally: scale first (`StandardScaler`, since
SVM's RBF kernel is distance-based and unscaled tag magnitudes would
dominate), fit `sklearn.svm.OneClassSVM(kernel="rbf", nu=0.05,
gamma="scale")` (both `nu`/`gamma` as constructor params with these
defaults) on all input+target columns. `transform()`: run
`decision_function`/`predict` to flag outlier rows (`-1` = outlier), then
**interpolate** those rows' values (`df.interpolate(method="linear")`
restricted to flagged rows) rather than dropping them — dropping would
break the evenly-spaced timeline the windowing step depends on. Store an
`outlier_mask_` attribute after fitting for inspection/testing.

### 6.3 `ml_pipeline/preprocessing/scaler.py`

**`StandardScalerTransformer(Transformer)`** — thin wrapper around
`sklearn.preprocessing.StandardScaler`. Critical detail: **fit only on the
training split**, then `transform()` is applied unchanged to validation
and test splits (and later, to live serving requests) using the
training-set statistics. Fitting on the full dataset (including
validation/test) is a data leak — don't do it, and write a test that
would catch it (e.g. assert the fitted mean matches the train slice's mean
exactly, not the full dataset's).

### 6.4 `ml_pipeline/preprocessing/sliding_window.py`

**`SlidingWindowTransformer(WindowBuilder)`** — for a given `window_size`
(in time steps, one of the paper's tuned hyperparameters, candidates
`{6, 12, 18, 24}`): `X[i] = features[i : i+window_size]`, `y[i] =
target[i+window_size]` — i.e. a window of *past* selected-feature values
predicts the *next* target value. Note this is a deliberate simplification
of the paper's full autoregressive encoder-decoder (which also feeds past
*target* values `y_{t-1}` back into the decoder, Eq. 15-16) — we predict
from exogenous input history only. This keeps the implementation
tractable while still directly testing the paper's core claim (does
temporal attention over a window beat a memoryless model), which is the
part of the paper this project is built to validate.

### 6.5 `ml_pipeline/preprocessing/pipeline.py`

**`PreprocessingPipeline`** — composes `OneClassSVMDenoiser` ->
`StandardScalerTransformer` -> (feature selection, Section 6.6) ->
`SlidingWindowTransformer` into one fit-once, reuse-everywhere object.
`fit(train_df, catalog, meta, target_col)`, `transform(df) -> (X, y)`.
Add `save(path)` / `load(path)` (classmethod) via `joblib.dump`/`load` —
this exact serialized object is what gets logged as an MLflow artifact
alongside the trained model (Phase 4/6) so serving applies *identical*
preprocessing to what training used.

### 6.6 `ml_pipeline/feature_selection/interfaces.py`

`FeatureSelector` ABC: `select(df, catalog, target_col, k) -> List[str]`
— returns the top-`k` input tag names, ranked by importance.

### 6.7 `ml_pipeline/feature_selection/xgboost_selector.py`

**`XGBoostFeatureSelector(FeatureSelector)`** — per the paper's Eq. 2-5:
fit `xgboost.XGBRegressor(importance_type="gain", ...)` per target on
**all** candidate input tags (train split only), then rank by
`.feature_importances_` (with `importance_type="gain"` this already
matches the paper's `Feature Gains[f] / Feature Counts[f]` — average gain
per split), return the top-`k` tag names. Expose the full ranked
importance table too (not just the top-k), for the EDA-style feature
importance chart from Fig. 5 of the paper.

### 6.8 Ground-truth validation test (special — allowed to peek)

`tests/test_feature_selection_ground_truth.py` — the **one** test module
allowed to import both `data_generator.specs` (for the true
`TargetSpec.sources`) and `ml_pipeline.feature_selection`. For each of a
few targets: run `XGBoostFeatureSelector.select(..., k=10)`, compute
recall against the true relevant tag names from the spec, assert recall
exceeds a threshold (e.g. >=0.6). This is the project's core Phase-3
validation — feature selection should meaningfully outperform chance at
recovering the tags that were actually built to matter. Everything else in
`ml_pipeline` must stay agnostic to the generator's ground truth (this is
the one deliberate, documented exception).

### 6.9 `pandera` schemas

`ml_pipeline/preprocessing/schemas.py` — a `pandera.DataFrameSchema` for
raw process data (expected dtypes, `ts` non-null, `regime_label` in
range) and one for post-denoising output (no NaNs remaining). Validate at
each stage boundary (`schema.validate(df)`) so a broken upstream stage
fails loudly and immediately rather than corrupting a downstream model
run silently.

### Phase 3 — Definition of Done

- [ ] `OneClassSVMDenoiser` + `StandardScalerTransformer` +
      `SlidingWindowTransformer` each unit-tested independently
- [ ] `PreprocessingPipeline` round-trips through `save()`/`load()` with
      identical `transform()` output before and after
- [ ] `XGBoostFeatureSelector` ground-truth recall test (Section 6.8)
      passes for FCC
- [ ] pandera schemas reject a deliberately-corrupted test DataFrame (e.g.
      a NaN injected post-denoising)

## 7. Phase 4 build guide — Models (dual backend + Optuna)

**Build order:**

### 7.1 `ml_pipeline/models/interfaces.py`

`BaseForecaster` ABC — the framework-agnostic boundary everything else
depends on:
- `fit(X_train, y_train, X_val, y_val, **hyperparams) -> BaseForecaster`
- `predict(X: np.ndarray) -> np.ndarray`
- `save(path) -> None`
- `load(path) -> BaseForecaster` (classmethod)
- `.backend_name` property (`"torch"` or `"keras"`)

All I/O is plain numpy: `X` shape `(n_samples, window_size, n_features)`,
`y` shape `(n_samples,)`.

### 7.2 The temporal-attention architecture (implement identically in both backends)

Simplified single-step version of the paper's Eq. 6-17 (encoder LSTM +
Bahdanau-style attention; see Section 6.4's note on why this is a
deliberate, documented simplification of the paper's full autoregressive
decoder):

1. **Encoder**: an LSTM consumes the window `x_1..x_T`, producing hidden
   states `h_1..h_T` (one per time step) plus the final hidden/cell state.
2. **Attention**: a learned compatibility function scores each `h_i`
   against the final decoder-side state: `score_i = v^T tanh(W_h h_i +
   W_d d)` (paper Eq. 12, `d` = the query state). Softmax over `i` gives
   attention weights `beta_i` (Eq. 13). Context vector `c = sum_i beta_i
   h_i` (Eq. 14).
3. **Output head**: concatenate `c` with the encoder's final hidden state,
   pass through a small dense layer to a scalar prediction (paper Eq. 17,
   simplified to one step).

Constructor hyperparameters for both backends (matching the paper's tuned
set): `input_size` (n_features), `hidden_size` (candidates `{64, 128, 192,
256}`), `window_size` (candidates `{6, 12, 18, 24}`), `dropout`
(`0.0-0.5`), `learning_rate`.

### 7.3 `ml_pipeline/models/torch_backend/lstm_ta.py`

**`TorchLSTMTemporalAttention(BaseForecaster)`** — wraps an internal
`torch.nn.Module` (`nn.LSTM` for the encoder, a small attention module,
`nn.Linear` output head). `fit()`: standard loop — `Adam` optimizer, `MSE`
loss (matching the paper), early stopping on `X_val/y_val` loss with a
configurable `patience` (stop when validation loss hasn't improved for
`patience` epochs), `max_epochs` cap. `predict()`: `model.eval()` +
`torch.no_grad()`. `save/load`: `torch.save(state_dict, path)` /
reconstruct architecture from stored hyperparameters + `load_state_dict`.

### 7.4 `ml_pipeline/models/keras_backend/lstm_ta.py`

**`KerasLSTMTemporalAttention(BaseForecaster)`** — same hyperparameter
surface, built with the `tf.keras` functional API (`layers.LSTM(...,
return_sequences=True)` for the encoder, a custom attention layer or
`layers.AdditiveAttention`, `layers.Dense` output head).
`model.compile(optimizer="adam", loss="mse")`, `model.fit(...,
callbacks=[EarlyStopping(patience=..., restore_best_weights=True)])`.
`save/load`: `model.save(path)` / `tf.keras.models.load_model(path)`.

### 7.5 `ml_pipeline/models/factory.py`

`ModelFactory.build(backend: Literal["torch", "keras"], **hyperparams) ->
BaseForecaster` — the one place that imports both backend modules; every
other file imports only `BaseForecaster`.

### 7.6 `ml_pipeline/training/splits.py`

`chronological_split(df, train_frac=0.70, val_frac=0.15) -> Tuple[pd.DataFrame,
pd.DataFrame, pd.DataFrame]` — strict time-order slicing (never shuffle).
Written once, used everywhere a split is needed (training, evaluation) so
the split logic can't drift between call sites.

### 7.7 `ml_pipeline/mlops/interfaces.py` (extend from Phase 2)

Add `ModelRegistry` ABC (introduced here because `Trainer` needs it; used
more heavily in Phase 6):
- `register(model_path: str, name: str) -> str` (returns new version)
- `set_alias(name: str, version: str, alias: str) -> None`
- `get_by_alias(name: str, alias: str) -> str` (returns a local path/URI to
  load from — actual model reconstruction goes through `ModelFactory` +
  `BaseForecaster.load()`, the registry only manages versions/pointers)
- `list_versions(name: str) -> List[dict]`

`ml_pipeline/mlops/mlflow_model_registry.py`: `MLflowModelRegistry`
implementing the above via `mlflow.register_model`,
`MlflowClient().set_registered_model_alias`,
`get_model_version_by_alias`. **Use aliases, not the deprecated
stage-transition API** (MLflow deprecated Staging/Production/Archived
stages in 2.9 — aliases like `@champion` are the current mechanism, and
multiple aliases can point at different versions simultaneously, useful
for A/B comparisons between backends later).

### 7.8 `ml_pipeline/training/optuna_search.py`

`OptunaSearch` — defines the search space (`hidden_size`, `window_size`,
`dropout`, `learning_rate` — log-uniform for the learning rate), an
objective function that builds a `BaseForecaster` via `ModelFactory`,
fits on train, evaluates validation MSE, and returns it.
`optuna.create_study(direction="minimize")` with a pruner (e.g.
`MedianPruner`) so unpromising trials stop early. Log every trial as a
nested MLflow run via the `ExperimentTracker` from Phase 2 — params,
validation MSE, and (for the best trial) the model artifact.

### 7.9 `ml_pipeline/training/trainer.py`

**`Trainer`** — orchestrates one full `(process, target, backend)` run:
1. Load data via `ProcessDataRepository` (Phase 2)
2. `chronological_split` (Section 7.6)
3. Fit `PreprocessingPipeline` (Phase 3) on train only, transform all
   three splits
4. Run `OptunaSearch` against validation
5. Refit the best-hyperparameter model
6. Evaluate on the held-out **test** split (touched for the first time
   here — never during the Optuna search) via the shared metrics module
   (Section 8.1)
7. Register the model (Section 7.7) and log the fitted
   `PreprocessingPipeline` as a companion artifact on the same version

### 7.10 `tests/test_model_conformance.py`

Parametrized over both backends, small synthetic dataset (a couple hundred
windows is enough): fit both, assert `predict()` output shape matches
`y_val`'s shape, assert `save()`/`load()` round-trips to identical
predictions, assert both beat a naive "predict the training mean"
baseline on validation MSE. This is what actually verifies the Liskov
Substitution claim — both backends are drop-in interchangeable through
`BaseForecaster`, not just nominally implementing the same method names.

### Phase 4 — Definition of Done

- [ ] `tests/test_model_conformance.py` passes for both backends
- [ ] `OptunaSearch` runs end-to-end for at least one `(process, target)`
      pair and improves validation MSE over a single default-hyperparameter
      run
- [ ] `Trainer.run()` completes for at least one process, registers a
      model, and the registered model's test-split metrics are logged
- [ ] Both backends, given the same hyperparameters and seed, produce
      broadly comparable (not necessarily identical) validation loss
      curves — sanity-check there isn't a bug making one backend degenerate

## 8. Phase 5 build guide — MLOps (Airflow, DVC, evaluation visuals)

**Build order:**

### 8.1 `ml_pipeline/evaluation/metrics.py`

`compute_metrics(y_true, y_pred) -> Dict[str, float]` — implements the
paper's five metrics exactly (Eq. 18-22): MSE, RMSE, MAE, MAPE, R².
**This is the only place these formulas are implemented** — both backends'
evaluation and the Optuna objective all call this function, never a
framework-native metric, so there's no risk of PyTorch's and Keras's
built-in metric implementations subtly disagreeing.

### 8.2 `ml_pipeline/evaluation/visuals.py`

Reproduces the paper's comparison figures (Fig. 8-14 style), parametrized
over a set of `(model_name, y_true, y_pred)` tuples so both backends plus
a naive baseline can be plotted together:
- Radar chart: MAE/RMSE/MSE/MAPE/R² across models
- Box plots of absolute error per model
- Fit curves: predicted vs. actual over the test period
- R² scatter (predicted vs. actual)

### 8.3 DVC pipeline

`params.yaml` — all tunable paths/hyperparameter-search ranges in one
place. `dvc.yaml` stages, each with explicit `deps`/`outs`/`params`:
`generate` (data_generator CLI, output = a tracked parquet export per
process) -> `eda` -> `preprocess` -> `select_features` -> `train`
(foreach over process/target/backend) -> `evaluate`. `dvc repro`
reproduces the whole thing from scratch given the same params. DVC remote:
`dvc remote add -d storage s3://<bucket>` pointed at Cloudflare R2,
credentials via `dvc remote modify --local` (never committed).

### 8.4 Airflow DAGs

`dags/petrochem_dag_factory.py` — a **DAG factory function**
(`build_dag(process_name) -> DAG`), looped over `SPEC_BUILDERS.keys()` to
generate one DAG per process (mirrors the config-driven-spec pattern from
Phase 1 — one factory, N processes, not N hand-written DAGs). Each DAG:
`ingest -> eda -> preprocess -> select_features -> train (incl. Optuna) ->
evaluate -> register`, tasks calling the same CLI entry points/pipeline
classes already built (don't duplicate logic into the DAG file — DAGs
orchestrate, they don't reimplement). `LocalExecutor`, Postgres-backed
Airflow metadata DB (separate database from the app's `petrochem`/
`mlflow` databases).

### 8.5 Full `docker-compose.yml`

Bring together `postgres`, `mlflow`, `airflow-webserver` +
`airflow-scheduler` (own metadata DB), `minio` (optional local DVC remote
for testing without touching R2), and a `pipeline` service (image built
via `uv sync --extra eda --extra preprocessing --extra torch --extra keras
--extra training --no-dev --frozen`, the full `ml_pipeline/` codebase).
All of these carry `profiles: ["full"]` — see §12.2/§12.10 for the
complete profile scheme and which services are mandatory this early vs.
deferred until now.

### Phase 5 — Definition of Done

- [ ] `dvc repro` runs the full pipeline end-to-end from a clean clone (via
      the local MinIO remote) and produces byte-identical outputs on a
      second run with no upstream changes
- [ ] At least one process's Airflow DAG completes unattended, all tasks
      green, in the Airflow UI
- [ ] Evaluation visuals render for all 4 processes, comparing both
      backends against a naive baseline
- [ ] `docker compose up` (full stack) succeeds from a fresh clone

## 9. Phase 6 build guide — Serving (FastAPI + Model Registry)

**Build order:**

### 9.1 `serving/dependencies.py`

FastAPI-`Depends()`-compatible factory functions, reusing the exact
interfaces built in earlier phases — no new architecture, just wiring:
`get_repository() -> ProcessDataRepository`, `get_model_registry() ->
ModelRegistry`, `get_tracker() -> ExperimentTracker`.

### 9.2 `serving/schemas.py`

Pydantic request/response models:
- `PredictRequest`: `readings: Optional[List[Dict[str, float]]] = None`
  (raw window, most-recent-last) **or** `use_latest: bool = True` (pull
  the most recent `window_size` rows for this process from Postgres via
  the repository) — both paths supported, mutually exclusive, validated
  with a Pydantic model validator (exactly one mode active).
- `PredictResponse`: `prediction: float`, `model_version: str`, `backend:
  str`, `served_at: datetime`.

### 9.3 `serving/routers/predict.py`

`POST /predict/{process}/{target}`:
1. Resolve input window per `PredictRequest` mode (raw body or latest-N
   from Postgres)
2. `ModelRegistry.get_by_alias(f"{process}__{target}__{backend}",
   "champion")` to resolve the serving version's path
3. Load the companion `PreprocessingPipeline` artifact (Section 6.5) for
   that exact version and `.transform()` the input window
4. `BaseForecaster.load(...)` (via `ModelFactory`, backend read from the
   registry's stored model metadata) and `.predict()`
5. Return `PredictResponse`

One code path regardless of which input mode was used — both converge on
the same preprocessing artifact + model before prediction, so there is
exactly one place "prediction logic" lives.

### 9.4 `serving/routers/processes.py` and `serving/routers/models.py`

- `GET /processes`, `GET /processes/{name}/variables` — thin wrappers over
  `ProcessDataRepository` (already built in Phase 2, reused unchanged)
- `GET /models/{process}/{target}` — registry metadata for the currently
  `@champion`-aliased version (version id, aliases, logged test-split
  metrics) — an observability endpoint essentially free given
  `ModelRegistry.list_versions()`

### 9.5 `serving/main.py`

FastAPI app instance, includes all routers, `GET /health`. Auto-generated
docs at `/docs` (FastAPI default, no extra work).

### 9.6 Testing

`tests/serving/test_predict.py` using `fastapi.testclient.TestClient`,
with `app.dependency_overrides[get_model_registry] = lambda: FakeRegistry()`
(and similarly for the repository) — fast unit tests of the API layer
alone, no real Postgres/MLflow needed.

### 9.7 Retrieval-augmented Q&A — `ml_pipeline/rag/` (indexing)

A small, deliberately scoped RAG system answering natural-language
questions over the EDA reports (Phase 2) and the project's own
documentation (`CLAUDE.md`, `README.md`). Scope boundary, stated
explicitly: this indexes and retrieves over *documents*, not a
tool-calling agent that queries Postgres/MLflow live — keep it a
straightforward retrieve-then-generate pipeline, not an agentic system.
Everything here stays open source and self-hosted, consistent with the
project's $0-cost ground rules (§14) — no paid embedding or completion
API.

**Interfaces** (`ml_pipeline/rag/interfaces.py`):
- `Chunk` (dataclass): `text: str`, `source: str` (e.g.
  `"eda:fcc:lag_recovery"` or `"claude_md:section_9"`), `metadata: dict`
- `DocumentChunker.chunk(text, source) -> List[Chunk]`
- `EmbeddingModel.embed(texts: List[str]) -> np.ndarray` (shape
  `(n_texts, embedding_dim)`)
- `VectorStore.upsert(chunks, embeddings) -> None`,
  `search(query_embedding, top_k) -> List[Chunk]`
- `AnswerGenerator.generate(question, context_chunks) -> str`

**Concrete implementations:**
- `MarkdownSectionChunker(DocumentChunker)` — splits on `##`/`###`
  headers (this document's own structure is already naturally
  chunk-sized per subsection — no need for anything fancier at this
  corpus size).
- `EdaResultChunker(DocumentChunker)` — takes the same `List[AnalyzerResult]`
  the Phase 2 report builder consumes, and chunks each analyzer's
  `.notes` plus a flattened text rendering of `.summary` into one `Chunk`
  per analyzer per process (source tagged `eda:{process}:{analyzer.name}`)
  — reuses Phase 2's objects directly, no HTML re-parsing.
- `SentenceTransformerEmbedder(EmbeddingModel)` — wraps
  `sentence-transformers` (`all-MiniLM-L6-v2`: small, CPU-friendly,
  384-dim, free, runs identically on all 3 team machines).
- `PgVectorStore(VectorStore)` — a new `rag_chunks` table (`id`, `source`,
  `text`, `embedding vector(384)`, `metadata jsonb`) in the **same**
  Postgres instance everything else already uses — via the `pgvector`
  extension, following the exact same "reuse Postgres instead of adding a
  service" reasoning already used for the Phase 7 Feast decision.

`ml_pipeline/rag/cli.py` — `index --process <name>` (runs
`EdaResultChunker` over that process's EDA analyzers + embeds + upserts)
and `index-docs --path CLAUDE.md` (runs `MarkdownSectionChunker` over a
given file). Re-running indexing for a source is idempotent — upsert on
`(source)`, not append.

### 9.8 Retrieval-augmented Q&A — `serving/routers/ask.py` (query time)

`POST /ask`, request `{"question": str, "top_k": int = 5}`, response
`{"answer": str, "sources": List[str]}` — sources are always returned
alongside the answer so a caller can verify what it was grounded in,
rather than trusting an unverifiable synthesized answer.

1. Embed the question via the same `SentenceTransformerEmbedder` used at
   index time (embedding model must match between indexing and querying —
   this is the RAG-specific version of Phase 3's "fit on train, apply
   unchanged at serving" consistency requirement).
2. `PgVectorStore.search(query_embedding, top_k)` — cosine-distance
   nearest neighbors via `pgvector`'s native operator.
3. `OllamaAnswerGenerator.generate(question, chunks)` — calls a
   **self-hosted** Ollama instance (`ollama/ollama` Docker image, a small
   open-source model such as `llama3.2:3b`, sized to run on the team's
   12-16GB machines) over its local HTTP API, with a prompt that requires
   the model to answer only from the provided chunks and cite which
   source(s) it used. Swappable for a paid API later via the same
   `AnswerGenerator` interface — but Ollama is the default, matching
   "keep everything open source."
4. Return the answer plus the `source` field from each retrieved chunk.

`get_vector_store()`/`get_answer_generator()` join `serving/dependencies.py`
(§9.1) as more `Depends()`-injected interfaces — same pattern as every
other router, no new architectural idea introduced here.

### 9.9 Docker & observability

`serving/Dockerfile` built via `uv sync --extra serving --extra
preprocessing --extra rag --no-dev --frozen` (the `serving` extra defined
in §12.1 covers `fastapi`, `uvicorn[standard]`,
`prometheus-fastapi-instrumentator`; the new `rag` extra covers
`sentence-transformers`, `pgvector`). Runs locally via
`docker-compose.yml`, port 8000, `profiles: ["full"]`.

Two additions to the compose stack for RAG specifically:
- Swap the `postgres` service's image from `postgres:16` to
  `pgvector/pgvector:pg16` — a drop-in replacement (same Postgres engine
  plus the `vector` extension pre-installed), no data migration needed for
  anything built in Phases 1-5.
- Add an `ollama` service (`ollama/ollama` image, `profiles: ["full"]`,
  named volume for pulled models). One-time setup per machine: `docker
  compose exec ollama ollama pull llama3.2:3b`.

Add Prometheus instrumentation in `serving/main.py`:
`Instrumentator().instrument(app).expose(app)` — exposes `/metrics` for
free (request counts, latency histograms, including `/ask` and
`/predict` separately). §12.2 covers the `prometheus`/`grafana` services
that scrape and visualize it; this is the one line of application code
that makes serving scrapable.

### Phase 6 — Definition of Done

- [ ] `POST /predict/{process}/{target}` returns a prediction via both
      input modes (raw readings and latest-from-Postgres) for at least one
      process/target with a registered `@champion` model
- [ ] `GET /models/{process}/{target}` reflects the actual registered
      version's metrics
- [ ] `GET /metrics` exposes Prometheus-format metrics; a Grafana panel
      shows request rate/latency for at least one `/predict` call
- [ ] `POST /ask` retrieves relevant source chunks and returns a cited
      answer for at least 3 test questions spanning both an EDA report
      (e.g. "what lag does gasoline yield show in the FCC data?") and
      `CLAUDE.md` content (e.g. "what's the chronological split ratio?")
- [ ] API tests pass using dependency overrides, no live infra required
- [ ] `docker compose --profile full up serving` works from a clean clone
      alongside the rest of the stack

## 10. Phase 7 (stretch) — Feast

Not built until Phases 1-6 work end-to-end — a feature store only pays for
itself once the training->serving loop is already solid. When it's time:
Feast's community Postgres connector (`feast[postgres]`) supports Postgres
as **offline store, online store, and registry simultaneously** — no new
infrastructure required, reusing the same Postgres instance everything
else already runs on. Scope: define `FeatureView`s over the
Phase-3-selected features, materialize to the Postgres online store, and
have `serving/routers/predict.py`'s "pull latest from Postgres" mode query
Feast's online store instead of the repository directly.

## 11. Data generated per process (reference)

| Process | Tags | Targets | Default samples | Sampling interval |
|---|---|---|---|---|
| `fcc` | 52 | 8 (5 yields + CO2/SO2/NOx) | 2,600 | 5 min |
| `te`  | 28 | 1 (purge component C) | 28,800 (4x7,200 modes) | 0.6 min |
| `dc`  | 7  | 1 (C4/butane yield) | 2,394 | 10 min |
| `sda` | 65 | 1 (DAO yield) | 25,000 | 5 min |


## 12. Developer Experience & Team Collaboration

Everything above defines *what* gets built. This chapter defines *how*
three developers, on three different operating systems, build it together
without stepping on each other — with the same rigor as any phase build
guide. It supersedes and absorbs what would otherwise be scattered
"coding standards" / "git workflow" / "secrets" notes: those topics live
here now, as one coherent operating model, not as disconnected reference
sections.

### 12.1 Standardized Development Environment

Every developer — MacBook (Developer 1), HP/Windows (Team Lead),
HP/Ubuntu (Developer 2) — runs the *identical* toolchain, regardless of
host OS. The mechanism is `uv` (Astral's Python package/project manager):
it manages the Python interpreter itself, the virtual environment, and
dependency resolution/locking, from one `pyproject.toml` — no developer
manually `pip install`s anything, ever.

**Files that define the environment:**
- `pyproject.toml` — single source of truth for dependencies, split into
  optional-dependency extras so each service only pulls what it needs:

  ```toml
  [project]
  name = "petrochem-xgboost-lstm-ta"
  requires-python = ">=3.11,<3.12"
  dependencies = [
      "pydantic>=2.6", "pydantic-settings>=2.2", "pandas>=2.1", "numpy>=1.26",
      "sqlalchemy>=2.0", "psycopg2-binary>=2.9", "typer>=0.12",
  ]

  [project.optional-dependencies]
  generator   = []                                   # covered by core deps
  eda         = ["matplotlib", "scipy", "statsmodels"]
  preprocessing = ["scikit-learn", "xgboost", "pandera"]
  torch       = ["torch"]
  keras       = ["tensorflow"]
  training    = ["optuna", "mlflow"]
  orchestration = ["apache-airflow"]
  serving     = ["fastapi", "uvicorn[standard]", "prometheus-fastapi-instrumentator"]
  rag         = ["sentence-transformers", "pgvector"]
  dev         = ["pytest", "pytest-cov", "ruff", "mypy", "pre-commit",
                  "testcontainers", "interrogate"]
  ```

  A service's Dockerfile installs only the extras it needs (e.g.
  `data_generator` never pulls in `torch`); a developer's local machine
  runs `uv sync --all-extras` to get everything.

- `.python-version` — contains `3.11`. `uv` reads this automatically and
  will *install that exact Python version itself* if it isn't already on
  the machine — a developer does not need Python pre-installed at all,
  which is what actually makes "identical environment regardless of OS"
  true rather than aspirational.
- `uv.lock` — committed, cross-platform lockfile (resolves correctly on
  Windows/macOS/Linux from the same file — this is `uv`'s main advantage
  over plain `pip freeze`, which produces OS-specific pins).
- `.pre-commit-config.yaml`:

  ```yaml
  repos:
    - repo: https://github.com/astral-sh/ruff-pre-commit
      rev: v0.6.0
      hooks:
        - id: ruff        # lint
        - id: ruff-format  # format
    - repo: https://github.com/pre-commit/mirrors-mypy
      rev: v1.11.0
      hooks:
        - id: mypy
    - repo: https://github.com/pre-commit/pre-commit-hooks
      rev: v4.6.0
      hooks:
        - id: trailing-whitespace
        - id: end-of-file-fixer
        - id: check-yaml
        - id: check-added-large-files
        - id: mixed-line-ending
          args: ["--fix=lf"]     # matches .gitattributes, keeps Windows checkouts LF
    - repo: local
      hooks:
        - id: pytest-unit
          name: pytest (unit tests only)
          entry: uv run pytest -m unit
          language: system
          pass_filenames: false
          stages: [pre-push]     # fast hooks on every commit; full unit suite on push, not every commit
  ```

**One-command setup** (this is the literal onboarding command — see also
§12.9):

```bash
git clone <repo-url> && cd fcc-xgboost-lstm-ta
uv sync --all-extras
pre-commit install --hook-type pre-commit --hook-type pre-push
docker compose --profile dev up -d
```

No developer manually installs a dependency, activates a venv by hand, or
configures a linter locally — it's all driven by the two committed files
(`pyproject.toml`, `.pre-commit-config.yaml`).

### 12.2 Local Infrastructure

Everything runs through Docker Compose — no service is ever installed
directly on a developer's host OS. Full service inventory:

| Service | Purpose | Mandatory from |
|---|---|---|
| PostgreSQL (`pgvector/pgvector:pg16` from Phase 6 onward — §9.9) | System of record for all process data, plus vector storage for RAG | Phase 1 |
| MLflow | Experiment tracking + model registry | Optional (Phase 2, via `NoOpExperimentTracker`) / **required** Phase 4 (Optuna logging, model registry) |
| MinIO | Local S3-compatible DVC remote for testing | Phase 5 |
| Airflow (webserver + scheduler) | Pipeline orchestration | Phase 5 |
| FastAPI (`serving`) | Model serving + RAG Q&A | Phase 6 |
| Ollama | Self-hosted LLM for `/ask` answer generation | Phase 6 |
| Prometheus | Scrapes `serving`'s `/metrics` | Phase 6 |
| Grafana | Visualizes Prometheus metrics | Phase 6 |

Every service declares `profiles:` in `docker-compose.yml` (see §12.10 for
the exact profile-to-service mapping) so a Phase-1 developer isn't forced
to boot Airflow/Grafana just to generate data.

### 12.3 Repository Structure Ownership

| Owner | Module |
|---|---|
| Developer 1 (MacBook) | `data_generator/` |
| **Team Lead** (HP/Windows) | `ml_pipeline/` (largest, most cross-cutting — anchors architecture decisions that other modules depend on) |
| Developer 2 (HP/Ubuntu) | `serving/` |
| Shared, no single owner | `configs/`, `tests/`, `dags/`, `docker-compose.yml`, root docs (`README.md`, `CLAUDE.md`) |

Ownership determines **default reviewer routing** (via `CODEOWNERS`,
below) — it does **not** replace the branch-protection rule from §12.4
requiring the Team Lead's approval on *every* PR regardless of which
module it touches. In practice this means: a PR to `serving/` auto-requests
Developer 2 as a domain reviewer *and* still requires the Team Lead's sign-off
to merge (branch protection's required-reviewer count stays at 1, satisfied
specifically by the Lead — the module owner's review is a genuine practice,
not a technically-enforced second gate; bump `required_approving_review_count`
to 2 later if you want both to be a hard gate).

```
# .github/CODEOWNERS
data_generator/**   @dev1-account
ml_pipeline/**      @team-lead-account
serving/**          @dev2-account
dags/**             @team-lead-account
configs/**          @team-lead-account
tests/**            @team-lead-account @dev1-account @dev2-account
*.md                @team-lead-account
*                    @team-lead-account   # catch-all: also the required-approval account
```

### 12.4 Git Workflow

Branch prefixes (broader set than Conventional Commit types, since branch
names and PR-title commit types serve different purposes — see below):

`feature/*` `fix/*` `refactor/*` `docs/*` `test/*` `experiment/*` `release/*`

`experiment/*` branches are for spikes/prototyping and are not expected to
merge as-is (rebase into a proper `feature/*` branch first if the
experiment pans out). `release/*` branches are short-lived and specific to
§12.12's release process, not a parallel long-lived branch model — `main`
remains the single integration branch (GitHub Flow), this is not GitFlow.

**Full workflow:**

```
Issue -> Branch -> Development -> Unit Tests -> Lint -> Push ->
Pull Request -> Code Review -> Approval -> Merge
```

Concretely: pick up a GitHub Issue (§12.17) -> branch off `main` using the
matching prefix (e.g. `feature/xgboost-feature-selector`, ideally
including the issue number: `feature/42-xgboost-feature-selector`) ->
implement -> run unit tests + `ruff`/`mypy` locally (pre-commit enforces
this automatically, §12.16) -> push -> open a PR (template in §12.5,
auto-links the issue via `Closes #42`) -> CI runs (§12.11) -> Team Lead (+
module owner) reviews (§12.6) -> approval -> **squash merge only** -> both
other machines `git pull`.

Branch protection on `main` (unchanged from earlier, restated here as the
canonical location): PR required, 1 approval via `CODEOWNERS`, required CI
status checks, branches must be up to date, squash merge only. Conventional
Commits (`feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `ci`, `build`,
`perf`) enforced on the **PR title** only — that title becomes the squash
commit on `main`, so individual in-branch commits are unconstrained. Each
machine keeps its own SSH key + matching `git config user.name/email` for
its GitHub identity.

### 12.5 Pull Request Standards

`.github/pull_request_template.md`:

```markdown
## Purpose
What problem does this PR solve? Link the issue (`Closes #N`).

## Implementation summary
What changed, and why this approach.

## Testing performed
- [ ] Unit tests added/updated
- [ ] Ran `uv run pytest -m unit` locally
- [ ] Ran `uv run pytest -m integration` locally (if applicable)
- [ ] Manually verified: <describe>

## Screenshots (if applicable)
<EDA report renders, Grafana panel, API response, etc.>

## Checklist
- [ ] `ruff check` / `ruff format --check` pass
- [ ] `mypy` passes
- [ ] Docs updated (docstrings, README/CLAUDE.md if architecture changed — §12.13)
- [ ] No secrets committed
```

Required to pass before merge (enforced by branch protection, §12.4):
Ruff, MyPy, pytest, and the full GitHub Actions pipeline (§12.11).

### 12.6 Code Review Guidelines

Reviewers (Team Lead always; module owner when relevant) check, in this
order — architecture first, style last:

1. **Architecture** — does this fit the existing module boundaries and
   ABCs, or does it quietly bypass them (e.g. a new class that talks to
   Postgres directly instead of going through `ProcessDataRepository`)?
2. **SOLID** — single responsibility per class, dependencies injected not
   hardcoded, interfaces not widened just to fit one caller.
3. **Naming** — matches §12.7's conventions.
4. **Type hints** — present and accurate, not `Any`-as-an-escape-hatch.
5. **Documentation** — docstrings present per §12.13, non-obvious
   decisions explained in comments.
6. **Test coverage** — new logic has tests; coverage didn't regress.
7. **Performance** — no obviously quadratic loops over data that could be
   vectorized, no N+1 query patterns against Postgres.
8. **Security** — no string-interpolated SQL, no committed secrets, no
   overly broad exception swallowing that would hide real failures.
9. **Backward compatibility** — does this change a public interface
   (`BaseForecaster`, `ProcessDataRepository`, etc.) in a way that breaks
   other modules' assumptions?

Reviews focus on maintainability, not personal style preference — if
Ruff/mypy don't flag it, it's very likely not worth a review comment
unless it affects one of the 9 points above.

### 12.7 Coding Standards

**Tooling** (enforced automatically, not a matter of review discussion):
Ruff only (formatter + linter, replaces Black+isort+flake8), line length
100, rule set `E F I UP B C4 SIM D ARG RUF` (Google-style docstrings via
`D`). Type hints required on all public functions; `from __future__ import
annotations` in every module. `mypy` in CI with gradual strictness
(`disallow_untyped_defs`, `warn_return_any` — not full `--strict`, which
fights numpy/pandas stubs unproductively).

**Design-level conventions** (what reviewers actually enforce, per
§12.6):

- **Naming**: `snake_case` functions/variables, `PascalCase` classes,
  `UPPER_SNAKE_CASE` constants (standard PEP 8) — no abbreviations that
  aren't domain-standard (`cfg` no, `spec` yes, since `ProcessSpec` is a
  first-class domain term throughout this codebase).
- **File organization**: one class per file when the class has real
  behavior (e.g. `outlier_denoiser.py` contains `OneClassSVMDenoiser`);
  small, closely-related data classes can share a file (e.g. all of
  `TagSpec`/`TargetSpec`/`RegimeSpec` in `spec.py`).
- **Maximum module size**: ~400 lines. Past that, it's a signal the
  module has more than one responsibility — split it (this has come up
  nowhere yet because every phase guide above was already scoped per
  class/concern from the start; treat a module blowing past 400 lines as
  a sign the phase guide's boundaries were violated, not just a style nit).
- **Class responsibilities**: one reason to change per class — this is
  why `data_generator/generators/` has 6 separate small classes instead
  of one `Simulator` god-class.
- **Dependency injection over hardcoding**: every generator/analyzer/model
  class receives its collaborators through `__init__`, never constructs
  them internally. Example (already the pattern throughout Phases 1-2):

  ```python
  # Yes — dependencies passed in, swappable, testable in isolation
  class ConfigDrivenSimulator(ProcessSimulator):
      def __init__(self, regime_scheduler: RegimeScheduler,
                   latent_generator: LatentStateGenerator, ...):
          self._regimes = regime_scheduler

  # No — hardcoded, can't test without the real OU process, can't swap
  class ConfigDrivenSimulator(ProcessSimulator):
      def __init__(self):
          self._regimes = ContiguousBlockRegimeScheduler()
  ```
- **Composition over inheritance**: no class hierarchies beyond
  "implements one ABC." `TorchLSTMTemporalAttention` does not subclass a
  shared `LSTMBase` that also gets subclassed by the Keras version — they
  each independently implement `BaseForecaster` and share behavior (if
  any) via composed helper functions, not a shared parent class.
- **Configuration over hardcoding**: any numeric threshold, file path, or
  environment-specific value lives in a `Settings`/`*Spec` Pydantic model
  or `params.yaml` (§8.3), never inline as a magic number in logic code.
- **Explicit interfaces**: every cross-module boundary is an ABC in an
  `interfaces.py` — a new collaborator is always added by implementing an
  existing interface, never by a caller reaching into another module's
  concrete class internals.

### 12.8 Testing Workflow

Four tiers, registered as pytest markers in `pyproject.toml`
(`[tool.pytest.ini_options] markers = ["unit", "integration", "pipeline",
"e2e"]`):

```
Unit Tests -> Integration Tests -> Pipeline Tests -> End-to-End Tests
```

| Tier | What it covers | Needs | Runs |
|---|---|---|---|
| `unit` | Individual classes in isolation (generators, analyzers, transformers, model conformance) | Nothing external | Every CI push; locally before every push (pre-commit `pre-push` stage, §12.1) |
| `integration` | `ProcessDataRepository`/`PostgresDataSink` against a real DB | Ephemeral Postgres via `testcontainers-python` | Every PR, in CI |
| `pipeline` | `dvc repro` end-to-end, one Airflow DAG dry-run | Docker Compose (`test`/`full` profile) | Nightly scheduled CI + before cutting a `release/*` branch |
| `e2e` | Full stack up, real HTTP call through `serving`'s `/predict`, checked against a known registered model | Full Docker Compose stack | Release branches only (§12.12), not every PR — too slow for the everyday loop |

Coverage: `unit` + `integration` combined must stay >=80% overall, >=90%
on core domain logic (`data_generator/generators/`, `ml_pipeline/eda/`,
`ml_pipeline/models/`). `pipeline`/`e2e` are smoke tests by nature (does it
run end-to-end, not line coverage) and aren't held to a coverage number.

### 12.9 Developer Onboarding

From a completely fresh machine to a passing test suite in under 30
minutes:

```
Clone repository
      |
Install uv (one curl/powershell command, §12.1)
      |
uv sync --all-extras
      |
docker compose --profile dev up -d
      |
Run pytest (uv run pytest -m unit)
      |
Run sample pipeline (python -m data_generator.cli generate --process dc --n-samples 500)
      |
Verify reports (python -m ml_pipeline.eda.cli run --process dc; open the HTML report)
      |
Ready for development
```

Every step above is a single command copy-pasted from this document —
nowhere in onboarding should a new developer need to ask "what do I run
next."

### 12.10 Local Development Profiles

Three named `docker compose --profile <name> up -d` profiles, composed
from the service table in §12.2:

| Profile | Services | Use when |
|---|---|---|
| `dev` | `postgres` | Working on Phases 1-2 (data generation, EDA) |
| `test` | `postgres`, `mlflow` | Working on Phases 3-4 (preprocessing, feature selection, model training/Optuna — needs experiment tracking + registry) |
| `full` | Everything (`postgres`, `mlflow`, `minio`, `airflow-webserver`, `airflow-scheduler`, `serving`, `prometheus`, `grafana`) | Phases 5-6 onward, or reproducing the entire system end-to-end |

Switching profiles is additive-safe (`docker compose --profile full up -d`
after already running `dev` just starts the additional services) — no
need to tear down between profiles during normal day-to-day work.

### 12.11 Continuous Integration

`.github/workflows/ci.yml`, ordered to fail fast (cheap checks block
expensive ones):

1. `ruff check` + `ruff format --check` (seconds)
2. `mypy` (seconds)
3. `pytest -m unit` (fast, no infra)
4. `pytest -m integration` (spins up ephemeral Postgres via
   `testcontainers-python` in the same job)
5. Coverage report — `coverage.py` HTML report uploaded as a workflow
   artifact + a PR comment summary (no paid SaaS required to keep
   everything open source per project ground rules; Codecov's free tier
   for public repos is a fine optional upgrade later, not required)
6. `docker build` — matrix over `{data_generator, pipeline, serving}`
   Dockerfiles, validates each actually builds
7. Documentation validation — `interrogate` (open-source docstring
   coverage checker) enforces a minimum docstring coverage threshold
8. Artifact upload — built wheels/images tagged with the commit SHA, for
   traceability into the release process (§12.12)

**Cross-platform check** (separate from the above, since Windows/macOS
GitHub-hosted runners are slower and Docker-in-CI is awkward on them):
a weekly scheduled workflow matrix (`ubuntu-latest`, `macos-latest`,
`windows-latest`) running just `uv sync --all-extras` + `pytest -m unit`
(no Docker, no integration tests) — catches platform-specific dependency
or path-handling bugs early without slowing down every-day PR CI.

### 12.12 Release Process

```
Feature Complete -> Release Branch -> Regression Testing -> Version Tag ->
Release Notes -> Merge to Main -> Deployment
```

"Feature complete" means a Milestone's (= a Phase's, §12.17) Definition of
Done checklist is fully checked. Cut a short-lived `release/phaseN` branch
from `main` -> run the `pipeline` and `e2e` test tiers (§12.8) against it,
fix anything that surfaces directly on that branch -> tag
`vX.Y.Z` (minor version bump per completed phase, e.g. `v0.3.0` = Phase 3
done) -> generate release notes from `git log` between tags, grouped by
Conventional Commit type (trivial since every squash-merge commit on
`main` already has a typed title, §12.4) -> merge `release/phaseN` back
into `main` (should be a fast-forward — no new feature work happens on a
release branch, only fixes surfaced by regression testing) -> "deployment"
for this project means the GitHub Release's tag becomes the version
referenced by `docker-compose.yml` image tags. This is a lightweight
addition on top of GitHub Flow (§12.4), not a return to long-lived GitFlow
branches — `main` stays the only permanent branch.

### 12.13 Documentation Standards

Every public module requires: a module-level docstring (what this module
is for, one paragraph), Google-style docstrings on every public
class/function (enforced by Ruff's `D` rules, §12.7), full type hints, and
a short usage example in the docstring for anything that isn't obvious
from the signature (e.g. `ProcessSpec` construction, `BaseForecaster`
subclassing).

Architecture diagrams are Mermaid, embedded directly in `README.md` — text-based,
diffable, reviewed in the same PR as the code that changes them (unlike a
separate drawing-tool file, which goes stale silently). Starter diagram:

```mermaid
flowchart LR
    DG[data_generator] -->|writes| PG[(PostgreSQL)]
    PG -->|reads| ML[ml_pipeline]
    ML -->|logs to| MLF[MLflow]
    MLF -->|@champion alias| SV[serving / FastAPI]
    PG -->|latest window| SV
    SV -->|/metrics| PROM[Prometheus]
    PROM --> GRAF[Grafana]
```

If a PR changes module boundaries or data flow, updating this diagram is
part of that PR — called out explicitly in the PR template checklist
(§12.5), since it isn't something CI can enforce automatically.

### 12.14 Secrets Management

`.env` gitignored everywhere; `.env.example` is the committed template.
Each machine keeps its own local `.env` — never synced via git or DVC.

**Naming convention**: `UPPER_SNAKE_CASE`, prefixed by the owning system —
`POSTGRES_*`, `MLFLOW_*`, `AIRFLOW_*`, `DVC_*` (e.g. `POSTGRES_PASSWORD`,
`MLFLOW_TRACKING_URI`) — so it's immediately obvious from the name alone
which service a variable configures.

- DVC remote (Cloudflare R2) credentials: `dvc remote modify --local`
  (DVC's built-in mechanism for keeping credentials out of the committed
  `.dvc/config`); R2 token scoped to one bucket only.
- Cross-machine secret sharing (3 machines, one person): a password
  manager (1Password/Bitwarden) — never plaintext file copying, never a
  secret pasted into Slack/chat/commit message.
- GitHub Actions secrets: the repo's built-in Encrypted Secrets. The
  CI-only ephemeral MinIO instance (§8.3) can use fixed dummy credentials
  since nothing in it persists past the workflow run.
- GitHub secret scanning + push protection: on by default, free on public
  repos — a real safety net, not just a formality, given this repo is
  public.
- A new secret is only ever introduced alongside an `.env.example` update
  in the same PR that needs it — never added silently.

### 12.15 Multi-Platform Support

The project must run correctly on Windows, macOS, and Linux — this isn't
aspirational, it's a direct consequence of the 3-machine team (§12.3).

- **Docker is the primary execution environment** for anything beyond
  writing/testing individual Python functions — it makes the runtime
  identical across all three OSes, sidestepping most platform issues
  entirely.
- All file paths in code use `pathlib.Path`, never raw string
  concatenation with `/` or `\` — this is a review-blocking issue
  (§12.6), not a style nit, since it's the single most common source of
  "works on my machine" bugs on a mixed-OS team.
- `.gitattributes` forces `LF` line endings on every checked-out file
  (already specified at repo init) — `pre-commit`'s `mixed-line-ending`
  hook (§12.1) backstops this locally.
- No OS-specific packages (e.g. nothing depending on `pywin32`) — if a
  dependency only works on one OS, it doesn't go in `pyproject.toml`'s
  shared dependency list.
- The weekly cross-platform CI matrix (§12.11) is the automated backstop
  for anything the above misses.

### 12.16 Developer Quality Gates

**Before every commit** (automatic, via `pre-commit`, §12.1):
- Ruff (lint + format)
- MyPy

**Before every push** (automatic, via `pre-commit`'s `pre-push` stage):
- `pytest -m unit` — deliberately *not* a pre-commit-stage hook, since
  running the full unit suite on every single commit would be slow enough
  to encourage `--no-verify` bypassing; pre-push is the right cadence.

**Before every PR is mergeable** (enforced by branch protection + CI,
§12.4/§12.11):
- All CI checks passing (Ruff, MyPy, pytest unit + integration, Docker
  build, docs validation)
- Documentation updated where relevant (§12.13)
- Tests added for new logic
- Coverage did not regress below the §12.8 thresholds

### 12.17 Project Management

**GitHub Projects** is the primary planning tool (a Kanban board:
Backlog / In Progress / In Review / Done).

- **Milestones** map 1:1 to Phases 1-7 — each Milestone's description
  links to that phase's "Definition of Done" checklist in this document,
  and the Milestone closes when every box is checked.
- **Labels**:
  - Type: `type:feature`, `type:bug`, `type:docs`, `type:refactor`,
    `type:test`, `type:chore`
  - Priority: `priority:p0` (blocking) through `priority:p3` (nice to
    have)
  - Phase: `phase:1` through `phase:7`
  - (Status is handled by the Projects board's columns, not a label —
    avoids two overlapping taxonomies saying the same thing.)
- **Roadmap**: the Phase 1-7 table (§ referenced throughout this
  document) *is* the roadmap — Milestones + due dates in GitHub Projects
  are just that table made interactive.
- **Release planning**: a release (§12.12) is cut when its Milestone
  closes — no separate release-planning process to maintain.

### 12.18 Definition of Done for Development

This is a **project-wide, per-task** Definition of Done — distinct from
each phase's own Definition of Done (§4-§10), which defines when an
entire *phase* is functionally/architecturally complete. This one applies
to every individual PR, regardless of which phase it belongs to.

A task is complete only if:
- [ ] Implementation finished
- [ ] Tests written (correct tier per §12.8)
- [ ] Documentation updated (§12.13)
- [ ] Lint passes (Ruff)
- [ ] Type checking passes (MyPy)
- [ ] CI passes (§12.11)
- [ ] Reviewed (§12.6) and approved (§12.4)
- [ ] Merged (squash, into `main`)

## 13. Model evaluation protocol

Strictly chronological 70/15/15 train/val/test split (Section 7.6), never
shuffled. Optuna tunes only against validation; the test split is touched
exactly once, at final evaluation. Both backends: identical architecture
spec, optimizer (Adam), loss (MSE), early-stopping criterion, evaluated
through the one shared metrics module (Section 8.1) — never a
framework-native metric function. Both logged to the same MLflow
experiment, tagged by `backend`, for direct comparison. Exact bit-for-bit
reproducibility across frameworks is not expected even with identical
seeds. Metrics: MSE, RMSE, MAE, MAPE, R² (matching the paper).

## 14. Full tech stack (all phases)

Python 3.11, `uv` (package/env/interpreter management), Pydantic v2,
NumPy/Pandas, Typer, PostgreSQL 16 (as `pgvector/pgvector:pg16` from Phase
6 onward) + SQLAlchemy Core, Matplotlib/SciPy/statsmodels, scikit-learn,
XGBoost, pandera, PyTorch **and** TensorFlow/Keras, Optuna, MLflow
(tracking + model registry), Apache Airflow (LocalExecutor), DVC (MinIO in
CI, Cloudflare R2 persistent remote), FastAPI + Uvicorn +
`prometheus-fastapi-instrumentator`, `sentence-transformers` + `pgvector`
+ Ollama (self-hosted RAG for `/ask`, §9.7-9.9), Prometheus, Grafana,
Docker/Docker Compose, GitHub + GitHub Actions, pytest, ruff, mypy,
pre-commit, `testcontainers-python`, `interrogate`. Feast noted as a
Phase 7 stretch addition (Section 10), not part of the core stack yet.

**Cost: $0/month** at project scope — everything above is open source or
inside a permanent free tier, including the RAG addition (self-hosted
embedding model + self-hosted Ollama LLM, no paid completion API).
Training is local/self-hosted only (no cloud GPU, including Colab —
evaluated and deliberately out of scope). Public deployment of the
FastAPI service (e.g. Render/Railway free tier) is an optional later
step, not required.

## 15. Quickstart (target end state, once all phases are built)

```bash
git clone <repo-url> && cd fcc-xgboost-lstm-ta
uv sync --all-extras
pre-commit install --hook-type pre-commit --hook-type pre-push

docker compose --profile dev up -d       # Phases 1-2
uv run python -m data_generator.cli generate-all
uv run python -m ml_pipeline.eda.cli run-all --output-dir ./reports
uv run pytest -m unit

docker compose --profile test up -d      # Phases 3-4 (adds MLflow)
docker compose --profile full up -d      # Phases 5-6 (adds Airflow, MinIO, serving, Ollama, Prometheus/Grafana)
docker compose exec ollama ollama pull llama3.2:3b   # one-time per machine

dvc repro
curl -X POST localhost:8000/predict/fcc/gasoline_yield -d '{"use_latest": true}'
uv run python -m ml_pipeline.rag.cli index --process fcc
uv run python -m ml_pipeline.rag.cli index-docs --path CLAUDE.md
curl -X POST localhost:8000/ask -d '{"question": "what lag does gasoline yield use?"}'
open http://localhost:3000   # Grafana
```
