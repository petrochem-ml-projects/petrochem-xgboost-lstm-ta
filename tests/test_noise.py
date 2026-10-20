"""Unit tests for ``data_generator.generators.noise``."""

from __future__ import annotations

import numpy as np
import pytest

from data_generator.domain.interfaces import NoiseGenerator
from data_generator.generators.noise import AR1NoiseGenerator

pytestmark = pytest.mark.unit


def _innovations(n_samples: int, std: float, seed: int) -> np.ndarray:
    return np.random.default_rng(seed).normal(loc=0.0, scale=std, size=n_samples)


def _reference_ar1(innovations: np.ndarray, ar_coef: float) -> np.ndarray:
    expected = np.empty_like(innovations)
    if innovations.size == 0:
        return expected
    expected[0] = innovations[0]
    for t in range(1, innovations.size):
        expected[t] = ar_coef * expected[t - 1] + innovations[t]
    return expected


def test_output_shape_matches_n_samples() -> None:
    result = AR1NoiseGenerator().generate(n_samples=50, ar_coef=0.5, std=1.0, seed=7)
    assert result.shape == (50,)


def test_same_seed_produces_identical_output() -> None:
    gen = AR1NoiseGenerator()
    first = gen.generate(n_samples=200, ar_coef=0.6, std=2.0, seed=11)
    second = gen.generate(n_samples=200, ar_coef=0.6, std=2.0, seed=11)
    assert np.array_equal(first, second)


def test_different_seeds_produce_different_output() -> None:
    gen = AR1NoiseGenerator()
    first = gen.generate(n_samples=200, ar_coef=0.6, std=1.0, seed=1)
    second = gen.generate(n_samples=200, ar_coef=0.6, std=1.0, seed=2)
    assert not np.array_equal(first, second)


def test_first_sample_equals_first_innovation() -> None:
    result = AR1NoiseGenerator().generate(n_samples=100, ar_coef=0.9, std=1.0, seed=3)
    assert result[0] == _innovations(100, 1.0, 3)[0]


def test_recurrence_matches_reference_loop() -> None:
    innovations = _innovations(300, 1.5, 4)
    result = AR1NoiseGenerator().generate(n_samples=300, ar_coef=0.5, std=1.5, seed=4)
    assert np.array_equal(result, _reference_ar1(innovations, 0.5))


def test_zero_ar_coef_gives_white_noise() -> None:
    result = AR1NoiseGenerator().generate(n_samples=100, ar_coef=0.0, std=1.0, seed=5)
    assert np.array_equal(result, _innovations(100, 1.0, 5))


def test_zero_std_gives_all_zeros() -> None:
    result = AR1NoiseGenerator().generate(n_samples=100, ar_coef=0.8, std=0.0, seed=6)
    assert np.all(result == 0.0)


def test_single_sample_equals_first_innovation() -> None:
    result = AR1NoiseGenerator().generate(n_samples=1, ar_coef=0.8, std=1.0, seed=8)
    assert result.shape == (1,)
    assert result[0] == _innovations(1, 1.0, 8)[0]


def test_zero_samples_returns_empty_array() -> None:
    result = AR1NoiseGenerator().generate(n_samples=0, ar_coef=0.5, std=1.0, seed=9)
    assert result.shape == (0,)


def test_negative_std_raises_value_error() -> None:
    with pytest.raises(ValueError):
        AR1NoiseGenerator().generate(n_samples=10, ar_coef=0.5, std=-1.0, seed=10)


def test_lag1_autocorrelation_near_ar_coef() -> None:
    result = AR1NoiseGenerator().generate(n_samples=50_000, ar_coef=0.7, std=1.0, seed=12)
    lag1 = np.corrcoef(result[:-1], result[1:])[0, 1]
    assert abs(lag1 - 0.7) < 0.02


def test_long_run_variance_near_stationary_value() -> None:
    result = AR1NoiseGenerator().generate(n_samples=50_000, ar_coef=0.7, std=1.0, seed=13)
    second_half = result[25_000:]
    expected = 1.0 / (1.0 - 0.7**2)
    assert abs(second_half.var() - expected) / expected < 0.05


def test_satisfies_noise_generator_interface() -> None:
    gen: NoiseGenerator = AR1NoiseGenerator()
    result = gen.generate(n_samples=25, ar_coef=0.3, std=1.0, seed=14)
    assert result.shape == (25,)
