"""Shared nonlinear transform for tag and target generators.

``apply_nonlinearity`` turns a linear combination of latent states into the
nonlinear signal every tag (``tags.py``) and target (``targets.py``) builder
applies before adding noise.
"""

from __future__ import annotations

import numpy as np

from data_generator.domain.spec import Nonlinearity


def apply_nonlinearity(x: np.ndarray, kind: Nonlinearity, scale: float) -> np.ndarray:
    """Apply one of the five configured nonlinear transforms.

    ``TANH``, ``SQUARE``, and ``LOG1P`` divide by ``scale``, so each guards
    against a near-zero or negative ``scale`` by substituting
    ``eff_scale = max(scale, 1e-6)`` everywhere ``scale`` appears in that
    formula. ``SIGMOID`` never divides by ``scale`` and is left unguarded;
    ``IDENTITY`` ignores ``scale`` entirely.

    Returns:
        Array of the same shape as ``x``.

    Raises:
        ValueError: If ``kind`` is not one of the five ``Nonlinearity``
            members.
    """
    if kind is Nonlinearity.IDENTITY:
        return x

    elif kind is Nonlinearity.TANH:
        eff_scale = max(scale, 1e-6)
        return np.tanh(eff_scale * x) / eff_scale

    elif kind is Nonlinearity.SQUARE:
        eff_scale = max(scale, 1e-6)
        return np.asarray(np.sign(x) * (eff_scale * x) ** 2 / eff_scale)

    elif kind is Nonlinearity.LOG1P:
        eff_scale = max(scale, 1e-6)
        return np.asarray(np.sign(x) * np.log1p(np.abs(eff_scale * x)) / eff_scale)

    elif kind is Nonlinearity.SIGMOID:
        eff_scale = max(scale, 1e-6)
        return 1 / (1 + np.exp(-scale * x))

    else:
        raise ValueError(f"unsupported Nonlinearity kind: {kind!r}")
