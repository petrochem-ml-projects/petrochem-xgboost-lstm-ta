"""Unit tests for ``data_generator.generators.transforms``."""

from __future__ import annotations

import numpy as np
import pytest

from data_generator.domain.spec import Nonlinearity
from data_generator.generators.transforms import apply_nonlinearity

pytestmark = pytest.mark.unit

_X = np.array([-2.0, 0.0, 1.0, 3.0])
_SCALE = 0.5
_DIVIDING_KINDS = (Nonlinearity.TANH, Nonlinearity.SQUARE, Nonlinearity.LOG1P)


def test_identity_returns_input_unchanged() -> None:
    for scale in (0.0, 0.5, 100.0):
        result = apply_nonlinearity(_X, Nonlinearity.IDENTITY, scale)
        assert np.array_equal(result, _X)


def test_tanh_matches_hand_computed_values() -> None:
    expected = np.tanh(_SCALE * _X) / _SCALE
    result = apply_nonlinearity(_X, Nonlinearity.TANH, _SCALE)
    assert np.allclose(result, expected)


def test_square_matches_hand_computed_values() -> None:
    expected = np.sign(_X) * (_SCALE * _X) ** 2 / _SCALE
    result = apply_nonlinearity(_X, Nonlinearity.SQUARE, _SCALE)
    assert np.allclose(result, expected)
    assert result[0] < 0.0
    assert result[-1] > 0.0


def test_log1p_matches_hand_computed_values() -> None:
    expected = np.sign(_X) * np.log1p(np.abs(_SCALE * _X)) / _SCALE
    result = apply_nonlinearity(_X, Nonlinearity.LOG1P, _SCALE)
    assert np.allclose(result, expected)


def test_sigmoid_matches_hand_computed_values() -> None:
    expected = 1 / (1 + np.exp(-_SCALE * _X))
    result = apply_nonlinearity(_X, Nonlinearity.SIGMOID, _SCALE)
    assert np.allclose(result, expected)
    assert np.all(result > 0.0)
    assert np.all(result < 1.0)


@pytest.mark.parametrize("kind", _DIVIDING_KINDS)
def test_dividing_kinds_guard_scale_zero(kind: Nonlinearity) -> None:
    guarded = apply_nonlinearity(_X, kind, 0.0)
    with np.errstate(all="raise"):
        reference = apply_nonlinearity(_X, kind, 1e-6)
    assert np.array_equal(guarded, reference)
    assert np.all(np.isfinite(guarded))


@pytest.mark.parametrize("kind", _DIVIDING_KINDS)
def test_dividing_kinds_negative_scale_clamps_like_zero(kind: Nonlinearity) -> None:
    at_zero = apply_nonlinearity(_X, kind, 0.0)
    at_negative = apply_nonlinearity(_X, kind, -5.0)
    assert np.array_equal(at_zero, at_negative)


def test_sigmoid_scale_zero_is_exactly_one_half() -> None:
    result = apply_nonlinearity(_X, Nonlinearity.SIGMOID, 0.0)
    assert np.array_equal(result, np.full_like(_X, 0.5))


@pytest.mark.parametrize("kind", list(Nonlinearity))
def test_output_shape_matches_input(kind: Nonlinearity) -> None:
    result = apply_nonlinearity(_X, kind, 1.0)
    assert result.shape == _X.shape


def test_vectorizes_over_multi_element_array() -> None:
    batched = apply_nonlinearity(_X, Nonlinearity.TANH, _SCALE)
    elementwise = np.array(
        [apply_nonlinearity(np.array([v]), Nonlinearity.TANH, _SCALE)[0] for v in _X]
    )
    assert np.allclose(batched, elementwise)


def test_unsupported_kind_raises_value_error() -> None:
    with pytest.raises(ValueError, match="unsupported Nonlinearity kind"):
        apply_nonlinearity(_X, "not_a_real_kind", 1.0)  # type: ignore[arg-type]
