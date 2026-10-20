"""Concrete AR(1) sensor-noise generator.

``AR1NoiseGenerator`` produces the autocorrelated noise every tag adds to its
clean signal. Each reading is pulled toward the previous one, so the noise
has short-term persistence rather than being independent per sample.
"""

from __future__ import annotations

import numpy as np

from data_generator.domain.interfaces import NoiseGenerator


class AR1NoiseGenerator(NoiseGenerator):
    """Generates AR(1) noise.

    Each sample is ``ar_coef`` times the previous sample plus a fresh innovation.
    """

    def generate(self, n_samples: int, ar_coef: float, std: float, seed: int) -> np.ndarray:
        """Simulate an AR(1) noise series.

        The recurrance is ``e[0] = innovation[0]`` and
        ``e[t] = ar_coef * e[t-1] + innovation[t]``,
        with innovation drawn from ``N(0,std)`` by one rng seeded from ``seed``.

        Returns:
            Float array of shape ``(n_samples,)``.
        """
        rng = np.random.default_rng(seed)
        innovations = rng.normal(loc=0.0, scale=std, size=n_samples)
        noise = np.empty(n_samples, dtype=np.float64)

        if n_samples == 0:
            return noise

        noise[0] = innovations[0]
        for t in range(1, n_samples):
            noise[t] = noise[t - 1] * ar_coef + innovations[t]

        return noise
