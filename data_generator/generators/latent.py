"""Concrete regime scheduler and latent-state generator.

``ContiguousBlockRegimeScheduler`` and ``OUProcessLatentGenerator`` are
the first concrete collaborators in the simulation engine -- every
downstream generator (tags, targets, outliers) samples from the latent
trajectory this file produces.
"""

from __future__ import annotations

import numpy as np

from data_generator.domain.interfaces import LatentStateGenerator, RegimeScheduler
from data_generator.domain.spec import ProcessSpec


class ContiguousBlockRegimeScheduler(RegimeScheduler):
    """Assigns timesteps to contiguous regime blocks.

    Also describes each regime's effect on the latent process.
    """

    def build_labels(self, spec: ProcessSpec) -> np.ndarray:
        """Split timesteps into contiguous, minimum-5%-sized regime blocks.

        Returns:
            Int array of shape ``(n_samples,)``, non-decreasing, covering
            exactly ``{0, ..., n_regimes - 1}``.
        """
        n_regimes = spec.regimes.n_regimes
        # Integer ceiling division avoids float-precision edge cases that
        # `math.ceil(0.05 * n_samples)` could introduce near block boundaries.
        min_block = -(-5 * spec.n_samples // 100)
        if min_block * n_regimes > spec.n_samples:
            raise ValueError(
                f"cannot split n_samples={spec.n_samples} into "
                f"n_regimes={n_regimes} with every block >= 5% of samples"
            )

        remaining = spec.n_samples - min_block * n_regimes
        rng = np.random.default_rng((spec.regimes.seed, 0))
        extra = rng.multinomial(remaining, [1 / n_regimes] * n_regimes)
        block_sizes = min_block + extra
        return np.repeat(np.arange(n_regimes), block_sizes)

    def regime_latent_shift(self, spec: ProcessSpec, regime_id: int) -> np.ndarray:
        """Mean shift applied to the latent state while in this regime.

        Deterministic given ``(spec.regimes.seed, regime_id)``.

        Returns:
            Array of shape ``(n_latent_states,)``.
        """
        rng = np.random.default_rng((spec.regimes.seed, 1, regime_id))
        return rng.normal(
            loc=0.0, scale=spec.regimes.latent_mean_shift_scale, size=spec.n_latent_states
        )

    def regime_latent_var_scale(self, spec: ProcessSpec, regime_id: int) -> float:
        """Multiplier applied to latent diffusion volatility in this regime.

        Deterministic given ``(spec.regimes.seed, regime_id)``.
        """
        rng = np.random.default_rng((spec.regimes.seed, 2, regime_id))
        return float(
            rng.uniform(
                low=spec.regimes.latent_var_scale_min, high=spec.regimes.latent_var_scale_max
            )
        )


class OUProcessLatentGenerator(LatentStateGenerator):
    """Simulates the shared latent-state trajectory.

    Modeled as a regime-modulated Ornstein-Uhlenbeck process.
    """

    def __init__(self, regime_scheduler: RegimeScheduler) -> None:
        """Store the regime scheduler this generator composes.

        Args:
            regime_scheduler: Supplies per-timestep regime ids and each
                regime's latent mean shift/variance scale.
        """
        self._regime_scheduler = regime_scheduler

    def generate(self, spec: ProcessSpec, regime_labels: np.ndarray) -> np.ndarray:
        """Simulate the latent-state trajectory via OU discretization at dt=1.

        The RNG is seeded once, here, from ``spec.random_seed`` -- never
        re-seeded inside the timestep loop -- so the whole trajectory is
        reproducible from one seed.

        Returns:
            Array of shape ``(n_samples, n_latent_states)``.
        """
        rng = np.random.default_rng(spec.random_seed)
        state = rng.normal(loc=0.0, scale=spec.latent_sigma, size=spec.n_latent_states)
        x = np.empty((spec.n_samples, spec.n_latent_states))

        for t in range(spec.n_samples):
            regime_id = int(regime_labels[t])
            mu = self._regime_scheduler.regime_latent_shift(spec, regime_id)
            var_scale = self._regime_scheduler.regime_latent_var_scale(spec, regime_id)
            sigma_eff = spec.latent_sigma * var_scale
            dw = rng.normal(loc=0.0, scale=1.0, size=spec.n_latent_states)
            state = state + spec.latent_theta * (mu - state) + sigma_eff * dw
            x[t] = state

        return x
