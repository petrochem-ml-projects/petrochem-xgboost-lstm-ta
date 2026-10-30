"""Unit tests for ``data_generator.generators.tags``."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from data_generator.domain.interfaces import NoiseGenerator, TagBuilder
from data_generator.domain.spec import Nonlinearity, ProcessSpec, TagSpec
from data_generator.generators.noise import AR1NoiseGenerator
from data_generator.generators.tags import LinearNonlinearTagBuilder
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


def _spec(tags: list[TagSpec], n_samples: int = 2, random_seed: int = 42) -> ProcessSpec:
    return ProcessSpec(
        process_name="dummy",
        n_latent_states=2,
        sampling_interval_minutes=1.0,
        n_samples=n_samples,
        tags=tags,
        targets=[],
        random_seed=random_seed,
    )


def test_output_columns_match_tag_names_in_order() -> None:
    tags = [TagSpec(name="c"), TagSpec(name="a"), TagSpec(name="b")]
    spec = _spec(tags, n_samples=5)
    latents = np.zeros((5, 2))
    builder = LinearNonlinearTagBuilder(_RecordingNoiseGenerator())
    df = builder.build(spec, latents)
    assert list(df.columns) == spec.tag_names == ["c", "a", "b"]


def test_output_row_count_matches_n_samples() -> None:
    tags = [TagSpec(name="t1")]
    spec = _spec(tags, n_samples=7)
    latents = np.zeros((7, 2))
    builder = LinearNonlinearTagBuilder(_RecordingNoiseGenerator())
    df = builder.build(spec, latents)
    assert len(df) == 7


def test_linear_combination_matches_hand_computed_value() -> None:
    tag = TagSpec(name="t1", latent_weights={0: 2.0, 1: -1.0}, base_value=0.0)
    spec = _spec([tag], n_samples=2)
    latents = np.array([[1.0, 2.0], [3.0, 4.0]])
    builder = LinearNonlinearTagBuilder(_RecordingNoiseGenerator(fixed=np.zeros(2)))
    df = builder.build(spec, latents)
    assert np.allclose(df["t1"].to_numpy(), [0.0, 2.0])


def test_empty_latent_weights_gives_zero_linear_component() -> None:
    tag = TagSpec(name="t1", latent_weights={}, base_value=5.0)
    spec = _spec([tag], n_samples=4)
    latents = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0], [7.0, 8.0]])
    builder = LinearNonlinearTagBuilder(_RecordingNoiseGenerator(fixed=np.zeros(4)))
    df = builder.build(spec, latents)
    assert np.array_equal(df["t1"].to_numpy(), np.full(4, 5.0))


def test_nonlinearity_is_delegated_not_reimplemented() -> None:
    tag = TagSpec(
        name="t1",
        latent_weights={0: 1.5, 1: 0.5},
        base_value=0.0,
        nonlinearity=Nonlinearity.TANH,
        nonlinear_scale=0.5,
    )
    spec = _spec([tag], n_samples=3)
    latents = np.array([[1.0, 2.0], [-1.0, 0.5], [3.0, -2.0]])
    builder = LinearNonlinearTagBuilder(_RecordingNoiseGenerator(fixed=np.zeros(3)))
    df = builder.build(spec, latents)

    linear = latents[:, [0, 1]] @ np.array([1.5, 0.5])
    expected = apply_nonlinearity(linear, Nonlinearity.TANH, 0.5)
    assert np.allclose(df["t1"].to_numpy(), expected)


def test_full_formula_matches_hand_computed_example() -> None:
    tag = TagSpec(name="t1", latent_weights={0: 2.0, 1: -1.0}, base_value=10.0)
    spec = _spec([tag], n_samples=2)
    latents = np.array([[1.0, 2.0], [3.0, 4.0]])
    noise = np.array([0.5, -0.5])
    builder = LinearNonlinearTagBuilder(_RecordingNoiseGenerator(fixed=noise))
    df = builder.build(spec, latents)
    assert np.allclose(df["t1"].to_numpy(), [10.5, 11.5])


def test_distinct_tags_receive_distinct_seeds() -> None:
    tags = [
        TagSpec(name="t1", ar_coef=0.3, noise_std=1.0),
        TagSpec(name="t2", ar_coef=0.3, noise_std=1.0),
        TagSpec(name="t3", ar_coef=0.3, noise_std=1.0),
    ]
    spec = _spec(tags, n_samples=3)
    latents = np.zeros((3, 2))
    fake = _RecordingNoiseGenerator()
    LinearNonlinearTagBuilder(fake).build(spec, latents)
    seeds = [call[3] for call in fake.calls]
    assert len(set(seeds)) == len(seeds)


def test_seed_derivation_is_deterministic_across_calls() -> None:
    tags = [TagSpec(name="t1"), TagSpec(name="t2")]
    spec = _spec(tags, n_samples=3)
    latents = np.zeros((3, 2))

    first_fake = _RecordingNoiseGenerator()
    LinearNonlinearTagBuilder(first_fake).build(spec, latents)
    second_fake = _RecordingNoiseGenerator()
    LinearNonlinearTagBuilder(second_fake).build(spec, latents)

    assert [call[3] for call in first_fake.calls] == [call[3] for call in second_fake.calls]

    real_builder = LinearNonlinearTagBuilder(AR1NoiseGenerator())
    first_df = real_builder.build(spec, latents)
    second_df = real_builder.build(spec, latents)
    pd.testing.assert_frame_equal(first_df, second_df)


def test_seed_matches_documented_formula() -> None:
    tags = [TagSpec(name="t1"), TagSpec(name="t2"), TagSpec(name="t3")]
    spec = _spec(tags, n_samples=2, random_seed=100)
    latents = np.zeros((2, 2))
    fake = _RecordingNoiseGenerator()
    LinearNonlinearTagBuilder(fake).build(spec, latents)
    assert [call[3] for call in fake.calls] == [100, 101, 102]


def test_noise_generator_is_injected_not_hardcoded() -> None:
    tag = TagSpec(name="t1", latent_weights={}, base_value=0.0)
    spec = _spec([tag], n_samples=3)
    latents = np.zeros((3, 2))

    zeros_builder = LinearNonlinearTagBuilder(_RecordingNoiseGenerator(fixed=np.zeros(3)))
    ones_builder = LinearNonlinearTagBuilder(_RecordingNoiseGenerator(fixed=np.ones(3)))

    zeros_df = zeros_builder.build(spec, latents)
    ones_df = ones_builder.build(spec, latents)

    assert np.allclose(ones_df["t1"].to_numpy() - zeros_df["t1"].to_numpy(), 1.0)


def test_satisfies_tag_builder_interface() -> None:
    builder: TagBuilder = LinearNonlinearTagBuilder(_RecordingNoiseGenerator())
    tag = TagSpec(name="t1")
    spec = _spec([tag], n_samples=4)
    latents = np.zeros((4, 2))
    df = builder.build(spec, latents)
    assert df.shape == (4, 1)


def test_multi_tag_spec_produces_independent_columns() -> None:
    tags = [
        TagSpec(name="t1", latent_weights={0: 1.0}, base_value=0.0),
        TagSpec(
            name="t2",
            latent_weights={1: 2.0},
            base_value=5.0,
            nonlinearity=Nonlinearity.SIGMOID,
            nonlinear_scale=1.0,
        ),
        TagSpec(name="t3", latent_weights={}, base_value=-3.0),
    ]
    spec = _spec(tags, n_samples=3)
    latents = np.array([[1.0, 2.0], [-1.0, 0.5], [3.0, -2.0]])
    builder = LinearNonlinearTagBuilder(_RecordingNoiseGenerator(fixed=np.zeros(3)))
    df = builder.build(spec, latents)

    assert np.allclose(df["t1"].to_numpy(), latents[:, 0])
    expected_t2 = 5.0 + apply_nonlinearity(latents[:, 1] * 2.0, Nonlinearity.SIGMOID, 1.0)
    assert np.allclose(df["t2"].to_numpy(), expected_t2)
    assert np.array_equal(df["t3"].to_numpy(), np.full(3, -3.0))


def test_out_of_range_latent_index_raises_index_error() -> None:
    tag = TagSpec(name="t1", latent_weights={5: 1.0})
    spec = _spec([tag], n_samples=3)
    latents = np.zeros((3, 2))
    builder = LinearNonlinearTagBuilder(_RecordingNoiseGenerator())
    with pytest.raises(IndexError):
        builder.build(spec, latents)


def test_integration_with_real_ar1_noise_generator_is_finite() -> None:
    tags = [
        TagSpec(name="t1", latent_weights={0: 1.0, 1: -0.5}, ar_coef=0.4, noise_std=0.2),
        TagSpec(
            name="t2",
            latent_weights={1: 2.0},
            nonlinearity=Nonlinearity.LOG1P,
            ar_coef=0.1,
            noise_std=0.5,
        ),
    ]
    spec = _spec(tags, n_samples=50)
    latents = np.random.default_rng(0).normal(size=(50, 2))
    builder = LinearNonlinearTagBuilder(AR1NoiseGenerator())
    df = builder.build(spec, latents)
    assert df.shape == (50, 2)
    assert list(df.columns) == ["t1", "t2"]
    assert np.isfinite(df.to_numpy()).all()
