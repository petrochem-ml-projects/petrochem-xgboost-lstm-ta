"""Unit tests for ``data_generator.generators.targets``."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from data_generator.domain.interfaces import NoiseGenerator, TargetBuilder
from data_generator.domain.spec import (
    Nonlinearity,
    ProcessSpec,
    TagContribution,
    TagSpec,
    TargetSpec,
)
from data_generator.generators.noise import AR1NoiseGenerator
from data_generator.generators.tags import LinearNonlinearTagBuilder
from data_generator.generators.targets import (
    _TARGET_NOISE_AR_COEF,
    LaggedNonlinearTargetBuilder,
    _lag_forward,
)
from data_generator.generators.transforms import apply_nonlinearity

pytestmark = pytest.mark.unit


class _RecordingNoiseGenerator(NoiseGenerator):
    """Fake ``NoiseGenerator`` recording every call's arguments.

    Returns a caller-supplied fixed array if given, else zeros.
    """

    def __init__(self, fixed: np.ndarray | None = None) -> None:
        self.fixed = fixed
        self.calls: list[tuple[int, float, float, int]] = []

    def generate(self, n_samples: int, ar_coef: float, std: float, seed: int) -> np.ndarray:
        self.calls.append((n_samples, ar_coef, std, seed))
        if self.fixed is not None:
            return self.fixed
        return np.zeros(n_samples)


def _spec(
    tags: list[TagSpec],
    targets: list[TargetSpec],
    n_samples: int = 3,
    sampling_interval_minutes: float = 5.0,
    random_seed: int = 42,
) -> ProcessSpec:
    return ProcessSpec(
        process_name="dummy",
        n_latent_states=1,
        sampling_interval_minutes=sampling_interval_minutes,
        n_samples=n_samples,
        tags=tags,
        targets=targets,
        random_seed=random_seed,
    )


# ---------------------------------------------------------------------------
# _lag_forward
# ---------------------------------------------------------------------------


def test_lag_forward_shifts_values_into_the_future() -> None:
    values = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
    result = _lag_forward(values, 2)
    assert np.array_equal(result, [10.0, 10.0, 10.0, 20.0, 30.0])


def test_lag_forward_zero_lag_returns_copy_of_input() -> None:
    values = np.array([1.0, 2.0, 3.0])
    result = _lag_forward(values, 0)
    assert np.array_equal(result, values)
    result[0] = 999.0
    assert values[0] == 1.0


def test_lag_forward_oversized_lag_backfills_entirely() -> None:
    values = np.array([7.0, 8.0, 9.0, 10.0, 11.0])
    result = _lag_forward(values, 10)
    assert np.array_equal(result, np.full(5, 7.0))


def test_lag_forward_single_step_lag() -> None:
    values = np.array([1.0, 2.0, 3.0])
    result = _lag_forward(values, 1)
    assert np.array_equal(result, [1.0, 1.0, 2.0])


# ---------------------------------------------------------------------------
# LaggedNonlinearTargetBuilder.build
# ---------------------------------------------------------------------------


def test_output_columns_match_target_names_in_order() -> None:
    tags = [TagSpec(name="t1")]
    targets = [TargetSpec(name="c"), TargetSpec(name="a"), TargetSpec(name="b")]
    spec = _spec(tags, targets, n_samples=4)
    tags_df = pd.DataFrame({"t1": np.zeros(4)})
    builder = LaggedNonlinearTargetBuilder(_RecordingNoiseGenerator())
    df = builder.build(spec, tags_df)
    assert list(df.columns) == spec.target_names == ["c", "a", "b"]


def test_output_row_count_matches_n_samples() -> None:
    tags = [TagSpec(name="t1")]
    targets = [TargetSpec(name="y1")]
    spec = _spec(tags, targets, n_samples=6)
    tags_df = pd.DataFrame({"t1": np.zeros(6)})
    builder = LaggedNonlinearTargetBuilder(_RecordingNoiseGenerator())
    df = builder.build(spec, tags_df)
    assert len(df) == 6


def test_multi_source_target_matches_hand_computed_value() -> None:
    tags = [TagSpec(name="tag_a"), TagSpec(name="tag_b")]
    target = TargetSpec(
        name="y1",
        base_value=5.0,
        sources=[
            TagContribution(tag="tag_a", coef=2.0, lag_minutes=0.0),
            TagContribution(tag="tag_b", coef=0.5, lag_minutes=5.0),
        ],
    )
    spec = _spec(tags, [target], n_samples=3, sampling_interval_minutes=5.0)
    tags_df = pd.DataFrame({"tag_a": [1.0, 2.0, 3.0], "tag_b": [10.0, 20.0, 30.0]})
    builder = LaggedNonlinearTargetBuilder(_RecordingNoiseGenerator(fixed=np.zeros(3)))
    df = builder.build(spec, tags_df)
    assert np.allclose(df["y1"].to_numpy(), [12.0, 14.0, 21.0])


def test_zero_sources_target_depends_only_on_base_value_and_noise() -> None:
    tags = [TagSpec(name="t1")]
    target = TargetSpec(name="y1", base_value=3.0, sources=[])
    spec = _spec(tags, [target], n_samples=4)
    tags_df = pd.DataFrame({"t1": np.arange(4, dtype=float)})
    builder = LaggedNonlinearTargetBuilder(_RecordingNoiseGenerator(fixed=np.zeros(4)))
    df = builder.build(spec, tags_df)
    assert np.array_equal(df["y1"].to_numpy(), np.full(4, 3.0))


def test_nonlinearity_is_delegated_not_reimplemented() -> None:
    tags = [TagSpec(name="t1")]
    target = TargetSpec(
        name="y1",
        sources=[TagContribution(tag="t1", coef=1.5, lag_minutes=0.0)],
        nonlinearity=Nonlinearity.TANH,
        nonlinear_scale=0.5,
    )
    spec = _spec(tags, [target], n_samples=3)
    tags_df = pd.DataFrame({"t1": [1.0, -1.0, 3.0]})
    builder = LaggedNonlinearTargetBuilder(_RecordingNoiseGenerator(fixed=np.zeros(3)))
    df = builder.build(spec, tags_df)

    linear = 1.5 * tags_df["t1"].to_numpy()
    expected = apply_nonlinearity(linear, Nonlinearity.TANH, 0.5)
    assert np.allclose(df["y1"].to_numpy(), expected)


def test_zero_lag_source_sees_same_timestep_tag_value() -> None:
    tags = [TagSpec(name="t1")]
    target = TargetSpec(name="y1", sources=[TagContribution(tag="t1", coef=1.0, lag_minutes=0.0)])
    spec = _spec(tags, [target], n_samples=4)
    tags_df = pd.DataFrame({"t1": [1.0, 2.0, 3.0, 4.0]})
    builder = LaggedNonlinearTargetBuilder(_RecordingNoiseGenerator(fixed=np.zeros(4)))
    df = builder.build(spec, tags_df)
    assert np.array_equal(df["y1"].to_numpy(), tags_df["t1"].to_numpy())


def test_negative_lag_steps_raises_value_error() -> None:
    tags = [TagSpec(name="t1")]
    target = TargetSpec(name="y1", sources=[TagContribution(tag="t1", coef=1.0, lag_minutes=-20.0)])
    spec = _spec(tags, [target], n_samples=3, sampling_interval_minutes=5.0)
    tags_df = pd.DataFrame({"t1": [1.0, 2.0, 3.0]})
    builder = LaggedNonlinearTargetBuilder(_RecordingNoiseGenerator())
    with pytest.raises(ValueError, match="y1"):
        builder.build(spec, tags_df)


def test_small_negative_lag_minutes_that_rounds_to_zero_does_not_raise() -> None:
    tags = [TagSpec(name="t1")]
    target = TargetSpec(name="y1", sources=[TagContribution(tag="t1", coef=1.0, lag_minutes=-0.3)])
    spec = _spec(tags, [target], n_samples=3, sampling_interval_minutes=5.0)
    tags_df = pd.DataFrame({"t1": [1.0, 2.0, 3.0]})
    builder = LaggedNonlinearTargetBuilder(_RecordingNoiseGenerator(fixed=np.zeros(3)))
    df = builder.build(spec, tags_df)
    assert np.array_equal(df["y1"].to_numpy(), tags_df["t1"].to_numpy())


def test_noise_uses_fixed_ar_coef_regardless_of_target_spec() -> None:
    tags = [TagSpec(name="t1")]
    targets = [TargetSpec(name="y1", noise_std=1.0), TargetSpec(name="y2", noise_std=9.0)]
    spec = _spec(tags, targets, n_samples=3)
    tags_df = pd.DataFrame({"t1": np.zeros(3)})
    fake = _RecordingNoiseGenerator()
    LaggedNonlinearTargetBuilder(fake).build(spec, tags_df)
    assert all(call[1] == _TARGET_NOISE_AR_COEF for call in fake.calls)


def test_distinct_targets_receive_distinct_seeds() -> None:
    tags = [TagSpec(name="t1")]
    targets = [TargetSpec(name="y1"), TargetSpec(name="y2"), TargetSpec(name="y3")]
    spec = _spec(tags, targets, n_samples=3)
    tags_df = pd.DataFrame({"t1": np.zeros(3)})
    fake = _RecordingNoiseGenerator()
    LaggedNonlinearTargetBuilder(fake).build(spec, tags_df)
    seeds = [call[3] for call in fake.calls]
    assert len(set(seeds)) == len(seeds)


def test_target_seeds_do_not_collide_with_tag_seeds() -> None:
    tags = [TagSpec(name="t1"), TagSpec(name="t2")]
    targets = [TargetSpec(name="y1"), TargetSpec(name="y2")]
    spec = _spec(tags, targets, n_samples=3, random_seed=100)
    tags_df = pd.DataFrame({"t1": np.zeros(3), "t2": np.zeros(3)})
    fake = _RecordingNoiseGenerator()
    LaggedNonlinearTargetBuilder(fake).build(spec, tags_df)
    target_seeds = [call[3] for call in fake.calls]
    assert target_seeds == [102, 103]
    tag_seed_range = range(100, 100 + len(tags))
    assert all(seed not in tag_seed_range for seed in target_seeds)


def test_seed_derivation_is_deterministic_across_calls() -> None:
    tags = [TagSpec(name="t1")]
    targets = [TargetSpec(name="y1"), TargetSpec(name="y2")]
    spec = _spec(tags, targets, n_samples=3)
    tags_df = pd.DataFrame({"t1": np.zeros(3)})

    first_fake = _RecordingNoiseGenerator()
    LaggedNonlinearTargetBuilder(first_fake).build(spec, tags_df)
    second_fake = _RecordingNoiseGenerator()
    LaggedNonlinearTargetBuilder(second_fake).build(spec, tags_df)
    assert [c[3] for c in first_fake.calls] == [c[3] for c in second_fake.calls]

    real_builder = LaggedNonlinearTargetBuilder(AR1NoiseGenerator())
    first_df = real_builder.build(spec, tags_df)
    second_df = real_builder.build(spec, tags_df)
    pd.testing.assert_frame_equal(first_df, second_df)


def test_clip_applies_both_bounds() -> None:
    tags = [TagSpec(name="t1")]
    target = TargetSpec(
        name="y1",
        sources=[TagContribution(tag="t1", coef=1.0, lag_minutes=0.0)],
        min_value=-1.0,
        max_value=1.0,
    )
    spec = _spec(tags, [target], n_samples=3)
    tags_df = pd.DataFrame({"t1": [-10.0, 0.0, 10.0]})
    builder = LaggedNonlinearTargetBuilder(_RecordingNoiseGenerator(fixed=np.zeros(3)))
    df = builder.build(spec, tags_df)
    assert np.array_equal(df["y1"].to_numpy(), [-1.0, 0.0, 1.0])


def test_clip_applies_one_bound() -> None:
    tags = [TagSpec(name="t1")]
    target = TargetSpec(
        name="y1",
        sources=[TagContribution(tag="t1", coef=1.0, lag_minutes=0.0)],
        max_value=5.0,
    )
    spec = _spec(tags, [target], n_samples=3)
    tags_df = pd.DataFrame({"t1": [-10.0, 0.0, 10.0]})
    builder = LaggedNonlinearTargetBuilder(_RecordingNoiseGenerator(fixed=np.zeros(3)))
    df = builder.build(spec, tags_df)
    assert np.array_equal(df["y1"].to_numpy(), [-10.0, 0.0, 5.0])


def test_clip_applies_no_bounds() -> None:
    tags = [TagSpec(name="t1")]
    target = TargetSpec(name="y1", sources=[TagContribution(tag="t1", coef=1.0, lag_minutes=0.0)])
    spec = _spec(tags, [target], n_samples=3)
    tags_df = pd.DataFrame({"t1": [-10.0, 0.0, 10.0]})
    builder = LaggedNonlinearTargetBuilder(_RecordingNoiseGenerator(fixed=np.zeros(3)))
    df = builder.build(spec, tags_df)
    assert np.array_equal(df["y1"].to_numpy(), [-10.0, 0.0, 10.0])


def test_noise_generator_is_injected_not_hardcoded() -> None:
    tags = [TagSpec(name="t1")]
    target = TargetSpec(name="y1", sources=[])
    spec = _spec(tags, [target], n_samples=3)
    tags_df = pd.DataFrame({"t1": np.zeros(3)})

    zeros_builder = LaggedNonlinearTargetBuilder(_RecordingNoiseGenerator(fixed=np.zeros(3)))
    ones_builder = LaggedNonlinearTargetBuilder(_RecordingNoiseGenerator(fixed=np.ones(3)))

    zeros_df = zeros_builder.build(spec, tags_df)
    ones_df = ones_builder.build(spec, tags_df)
    assert np.allclose(ones_df["y1"].to_numpy() - zeros_df["y1"].to_numpy(), 1.0)


def test_satisfies_target_builder_interface() -> None:
    builder: TargetBuilder = LaggedNonlinearTargetBuilder(_RecordingNoiseGenerator())
    tags = [TagSpec(name="t1")]
    target = TargetSpec(name="y1", sources=[])
    spec = _spec(tags, [target], n_samples=4)
    tags_df = pd.DataFrame({"t1": np.zeros(4)})
    df = builder.build(spec, tags_df)
    assert df.shape == (4, 1)


def test_integration_with_real_tag_builder_and_noise_generator_is_finite() -> None:
    tags = [
        TagSpec(name="temp_1", latent_weights={0: 1.0}, ar_coef=0.3, noise_std=0.5),
        TagSpec(name="press_1", latent_weights={0: -0.5}, ar_coef=0.2, noise_std=0.3),
    ]
    targets = [
        TargetSpec(
            name="yield_1",
            base_value=10.0,
            sources=[
                TagContribution(tag="temp_1", coef=1.2, lag_minutes=10.0),
                TagContribution(tag="press_1", coef=-0.4, lag_minutes=5.0),
            ],
            nonlinearity=Nonlinearity.TANH,
            nonlinear_scale=0.1,
            noise_std=0.2,
        )
    ]
    spec = _spec(tags, targets, n_samples=50, sampling_interval_minutes=5.0)
    latents = np.random.default_rng(0).normal(size=(50, 1))
    tags_df = LinearNonlinearTagBuilder(AR1NoiseGenerator()).build(spec, latents)

    builder = LaggedNonlinearTargetBuilder(AR1NoiseGenerator())
    df = builder.build(spec, tags_df)
    assert df.shape == (50, 1)
    assert list(df.columns) == ["yield_1"]
    assert np.isfinite(df.to_numpy()).all()
