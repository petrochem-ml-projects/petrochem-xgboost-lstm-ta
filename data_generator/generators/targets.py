"""Concrete target builder turning the clean tag signal into process targets.

``LaggedNonlinearTargetBuilder`` is the first real caller of ``tags.py``'s
output: for every ``TargetSpec`` it builds one observed target series as a
time-lagged, coefficient-weighted sum of its source tags, pushed through
the target's configured nonlinearity, plus noise, clipped to a configured
range. The lag direction implemented by ``_lag_forward`` -- a later
target value sees an earlier tag value, never the reverse -- is this
project's single most important mechanic (CLAUDE.md Section 4.7): it is
what gives a temporal-attention model something real to exploit that a
memoryless model cannot.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from data_generator.domain.interfaces import NoiseGenerator, TargetBuilder
from data_generator.domain.spec import ProcessSpec
from data_generator.generators.transforms import apply_nonlinearity

_TARGET_NOISE_AR_COEF = 0.0


def _lag_forward(values: np.ndarray, lag_steps: int) -> np.ndarray:
    """Shift a series forward in time by ``lag_steps``, back-filling the start.

    ``result[t] == values[t - lag_steps]`` for ``t >= lag_steps``; the
    first ``lag_steps`` entries are back-filled with ``values[0]`` rather
    than left as ``NaN``. If ``lag_steps`` is at least ``len(values)``,
    every entry is back-filled with ``values[0]``.

    Args:
        values: One source tag's clean value series.
        lag_steps: Number of timesteps to shift forward. Must be
            non-negative -- the caller is responsible for that guarantee
            (see ``LaggedNonlinearTargetBuilder.build``).

    Returns:
        Array of the same shape as ``values``.
    """
    if lag_steps == 0:
        return values.copy()

    lagged = np.empty_like(values)
    lagged[:lag_steps] = values[0]
    lagged[lag_steps:] = values[:-lag_steps]
    return lagged


class LaggedNonlinearTargetBuilder(TargetBuilder):
    """Builds every target's value series from the clean tag signal."""

    def __init__(self, noise_generator: NoiseGenerator) -> None:
        """Store the noise generator this builder composes.

        Args:
            noise_generator: Supplies each target's noise, seeded
                distinctly per target and never colliding with a tag's
                seed from the same spec.
        """
        self._noise_generator = noise_generator

    def build(self, spec: ProcessSpec, tags_df: pd.DataFrame) -> pd.DataFrame:
        """Build every target's value series as lagged-linear + nonlinear + noise.

        Each target's noise seed is ``spec.random_seed + len(spec.tags) +
        index``, where ``index`` is the target's 0-based position in
        ``spec.targets`` -- distinct from every other target's seed and
        from every tag's seed in the same spec.

        Returns:
            DataFrame with columns equal to ``spec.target_names``, in
            order, each of length ``spec.n_samples``.

        Raises:
            ValueError: If any source's ``lag_minutes`` resolves to a
                negative number of lag steps -- that would make a target
                depend on a future tag value, inverting this file's core
                mechanic.
        """
        columns: dict[str, np.ndarray] = {}
        n_tags = len(spec.tags)

        for target_index, target in enumerate(spec.targets):
            linear = np.zeros(spec.n_samples, dtype=np.float64)

            for contribution in target.sources:
                lag_steps = round(contribution.lag_minutes / spec.sampling_interval_minutes)

                if lag_steps < 0:
                    raise ValueError(
                        f"target {target.name!r}: source {contribution.tag!r} "
                        f"resolves to a negative lag_steps ({lag_steps}) from "
                        f"lag_minutes={contribution.lag_minutes}; a target may "
                        "only depend on the past"
                    )

                values = tags_df[contribution.tag].to_numpy(dtype=np.float64)
                lagged = _lag_forward(values, lag_steps)
                linear += contribution.coef * lagged

            nonlinear = apply_nonlinearity(linear, target.nonlinearity, target.nonlinear_scale)

            seed = spec.random_seed + n_tags + target_index
            noise = self._noise_generator.generate(
                spec.n_samples, _TARGET_NOISE_AR_COEF, target.noise_std, seed
            )

            target_value = target.base_value + nonlinear + noise
            columns[target.name] = np.clip(target_value, target.min_value, target.max_value)

        return pd.DataFrame(columns)
