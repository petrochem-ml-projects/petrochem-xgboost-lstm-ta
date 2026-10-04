"""Unit tests for ``data_generator.generators.latent``."""

from __future__ import annotations

import numpy as np
import pytest

from data_generator.domain.interfaces import RegimeScheduler
from data_generator.domain.spec import ProcessSpec, RegimeSpec
from data_generator.generators.latent import (
    ContiguousBlockRegimeScheduler,
    OUProcessLatentGenerator,
)


def _spec(n_samples: int = 100, n_regimes: int = 3, n_latent_states: int = 2) -> ProcessSpec:
    return ProcessSpec(
        process_name="dummy",
        n_latent_states=n_latent_states,
        sampling_interval_minutes=1.0,
        n_samples=n_samples,
        tags=[],
        targets=[],
        regimes=RegimeSpec(n_regimes=n_regimes),
    )


def test_build_labels_respects_minimum_block_size() -> None:
    spec = _spec(n_samples=100, n_regimes=3)
    labels = ContiguousBlockRegimeScheduler().build_labels(spec)
    min_block = -(-5 * spec.n_samples // 100)
    counts = np.bincount(labels, minlength=spec.regimes.n_regimes)
    assert (counts >= min_block).all()


def test_build_labels_covers_all_samples_in_ascending_contiguous_blocks() -> None:
    spec = _spec(n_samples=100, n_regimes=3)
    labels = ContiguousBlockRegimeScheduler().build_labels(spec)
    assert labels.shape == (100,)
    assert (np.diff(labels) >= 0).all()
    assert set(labels.tolist()) == {0, 1, 2}


def test_build_labels_raises_when_regimes_cannot_satisfy_minimum() -> None:
    spec = _spec(n_samples=10, n_regimes=21)
    with pytest.raises(ValueError, match="n_samples"):
        ContiguousBlockRegimeScheduler().build_labels(spec)


def test_build_labels_is_deterministic_given_same_seed() -> None:
    spec = _spec(n_samples=100, n_regimes=3)
    scheduler = ContiguousBlockRegimeScheduler()
    first = scheduler.build_labels(spec)
    second = scheduler.build_labels(spec)
    assert np.array_equal(first, second)


def test_regime_latent_shift_is_deterministic() -> None:
    spec = _spec(n_latent_states=4)
    scheduler = ContiguousBlockRegimeScheduler()
    first = scheduler.regime_latent_shift(spec, 0)
    second = scheduler.regime_latent_shift(spec, 0)
    assert np.array_equal(first, second)
    assert first.shape == (4,)


def test_regime_latent_shift_differs_across_regime_ids() -> None:
    spec = _spec()
    scheduler = ContiguousBlockRegimeScheduler()
    shift_0 = scheduler.regime_latent_shift(spec, 0)
    shift_1 = scheduler.regime_latent_shift(spec, 1)
    assert not np.array_equal(shift_0, shift_1)


def test_regime_latent_var_scale_is_deterministic_and_in_range() -> None:
    spec = _spec()
    scheduler = ContiguousBlockRegimeScheduler()
    first = scheduler.regime_latent_var_scale(spec, 0)
    second = scheduler.regime_latent_var_scale(spec, 0)
    assert first == second
    assert spec.regimes.latent_var_scale_min <= first <= spec.regimes.latent_var_scale_max


def test_ou_generator_output_shape() -> None:
    spec = _spec(n_samples=50, n_latent_states=3)
    scheduler = ContiguousBlockRegimeScheduler()
    regime_labels = scheduler.build_labels(spec)
    result = OUProcessLatentGenerator(scheduler).generate(spec, regime_labels)
    assert result.shape == (50, 3)


def test_ou_generator_is_deterministic_given_same_spec() -> None:
    spec = _spec(n_samples=50, n_latent_states=3)
    scheduler = ContiguousBlockRegimeScheduler()
    regime_labels = scheduler.build_labels(spec)
    generator = OUProcessLatentGenerator(scheduler)
    first = generator.generate(spec, regime_labels)
    second = generator.generate(spec, regime_labels)
    assert np.array_equal(first, second)


def test_ou_generator_rng_seeded_once_matches_across_separate_runs() -> None:
    spec = _spec(n_samples=50, n_latent_states=3)
    scheduler = ContiguousBlockRegimeScheduler()
    regime_labels = scheduler.build_labels(spec)
    first = OUProcessLatentGenerator(scheduler).generate(spec, regime_labels)
    second = OUProcessLatentGenerator(scheduler).generate(spec, regime_labels)
    assert np.array_equal(first, second)


def test_ou_generator_constructor_takes_regime_scheduler_by_interface() -> None:
    class FakeRegimeScheduler(RegimeScheduler):
        def build_labels(self, spec: ProcessSpec) -> np.ndarray:
            return np.zeros(spec.n_samples, dtype=int)

        def regime_latent_shift(self, spec: ProcessSpec, _regime_id: int) -> np.ndarray:
            return np.zeros(spec.n_latent_states)

        def regime_latent_var_scale(self, _spec: ProcessSpec, _regime_id: int) -> float:
            return 1.0

    spec = _spec(n_samples=10, n_latent_states=2)
    fake = FakeRegimeScheduler()
    regime_labels = fake.build_labels(spec)
    result = OUProcessLatentGenerator(fake).generate(spec, regime_labels)
    assert result.shape == (10, 2)
