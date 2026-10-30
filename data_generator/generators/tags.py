"""Concrete tag builder turning the shared latent trajectory into sensor tags.

``LinearNonlinearTagBuilder`` is the first file that produces an actual
column of the synthetic dataset: for each ``TagSpec`` it composes a
linear combination of latent states, 1.5's nonlinear transform, and 1.4's
autocorrelated noise generator into one observed tag series.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from data_generator.domain.interfaces import NoiseGenerator, TagBuilder
from data_generator.domain.spec import ProcessSpec
from data_generator.generators.transforms import apply_nonlinearity


class LinearNonlinearTagBuilder(TagBuilder):
    """Builds every tag's clean value series from the latent trajectory."""

    def __init__(self, noise_generator: NoiseGenerator) -> None:
        """Store the noise generator this builder composes.

        Args:
            noise_generator: Supplies each tag's autocorrelated sensor
                noise, seeded distinctly per tag.
        """
        self._noise_generator = noise_generator

    def build(self, spec: ProcessSpec, latents: np.ndarray) -> pd.DataFrame:
        """Build every tag's value series as linear + nonlinear + noise.

        Each tag's seed is ``spec.random_seed + index``, where ``index``
        is the tag's 0-based position in ``spec.tags`` -- distinct within
        one call, deterministic given the spec.

        Returns:
            DataFrame with columns equal to ``spec.tag_names``, in order,
            each of length ``spec.n_samples``.
        """
        columns: dict[str, np.ndarray] = {}

        for index, tag in enumerate(spec.tags):
            indices = list(tag.latent_weights.keys())
            weights = np.array(list(tag.latent_weights.values()), dtype=np.float64)
            linear = latents[:, indices] @ weights

            nonlinear = apply_nonlinearity(linear, tag.nonlinearity, tag.nonlinear_scale)

            seed = spec.random_seed + index
            noise = self._noise_generator.generate(spec.n_samples, tag.ar_coef, tag.noise_std, seed)

            columns[tag.name] = tag.base_value + nonlinear + noise

        return pd.DataFrame(columns)
