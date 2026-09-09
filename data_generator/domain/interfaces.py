"""Domain contracts for the data generator's collaborators.

The 8 Interface-Segregated ABCs every concrete generator in
``data_generator/generators/`` and ``data_generator/sinks/`` implements
exactly one of. Each ABC is a pure contract -- method signatures and
docstring-documented input/output shapes, no logic. This is what makes
``ConfigDrivenSimulator`` (subsection 8) constructor-injectable and
testable with fakes instead of concrete classes, and what lets Postgres
be swapped for another ``DataSink`` later without touching engine code.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
import pandas as pd

from data_generator.domain.spec import ProcessSpec


class LatentStateGenerator(ABC):
    """Generates the shared latent-state trajectory a process's tags are built from."""

    @abstractmethod
    def generate(self, spec: ProcessSpec, regime_labels: np.ndarray) -> np.ndarray:
        """Simulate the latent-state trajectory.

        Args:
            spec: The process specification driving the simulation.
            regime_labels: Int array of shape ``(n_samples,)`` giving
                each timestep's regime id.

        Returns:
            Array of shape ``(n_samples, n_latent_states)``.
        """


class RegimeScheduler(ABC):
    """Assigns timesteps to regimes and describes their perturbation of the latent process."""

    @abstractmethod
    def build_labels(self, spec: ProcessSpec) -> np.ndarray:
        """Assign a regime id to every timestep.

        Returns:
            Int array of shape ``(n_samples,)``.
        """

    @abstractmethod
    def regime_latent_shift(self, spec: ProcessSpec, regime_id: int) -> np.ndarray:
        """Mean shift applied to the latent state while in this regime.

        Returns:
            Array of shape ``(n_latent_states,)``.
        """

    @abstractmethod
    def regime_latent_var_scale(self, spec: ProcessSpec, regime_id: int) -> float:
        """Multiplier applied to latent diffusion volatility in this regime."""


class NoiseGenerator(ABC):
    """Generates autocorrelated sensor noise."""

    @abstractmethod
    def generate(self, n_samples: int, ar_coef: float, std: float, seed: int) -> np.ndarray:
        """Simulate a noise series.

        Returns:
            Array of shape ``(n_samples,)``.
        """


class TagBuilder(ABC):
    """Builds observed tag (sensor) values from the latent state."""

    @abstractmethod
    def build(self, spec: ProcessSpec, latents: np.ndarray) -> pd.DataFrame:
        """Build every tag's clean value series.

        Args:
            spec: The process specification.
            latents: Array of shape ``(n_samples, n_latent_states)``.

        Returns:
            DataFrame with columns equal to ``spec.tag_names``.
        """


class TargetBuilder(ABC):
    """Builds target (process-output) values from the clean tag signal."""

    @abstractmethod
    def build(self, spec: ProcessSpec, tags_df: pd.DataFrame) -> pd.DataFrame:
        """Build every target's value series.

        Args:
            spec: The process specification.
            tags_df: Clean (pre-outlier) tag values, columns equal to
                ``spec.tag_names``.

        Returns:
            DataFrame with columns equal to ``spec.target_names``.
        """


class OutlierInjector(ABC):
    """Corrupts a fraction of tag observations to model sensor faults."""

    @abstractmethod
    def inject(self, spec: ProcessSpec, tags_df: pd.DataFrame) -> pd.DataFrame:
        """Return a copy of ``tags_df`` with outliers injected.

        Returns:
            DataFrame with the same shape and columns as ``tags_df``.
        """


class ProcessSimulator(ABC):
    """Orchestrates the full simulation pipeline for one process."""

    @abstractmethod
    def simulate(self, spec: ProcessSpec) -> pd.DataFrame:
        """Run the full simulation.

        Returns:
            DataFrame containing ``ts``, ``regime_label``, every tag
            column, and every target column.
        """


class DataSink(ABC):
    """Persists a simulated process dataset."""

    @abstractmethod
    def prepare(self, spec: ProcessSpec) -> None:
        """Create/verify whatever schema this sink needs for ``spec``."""

    @abstractmethod
    def write(self, spec: ProcessSpec, df: pd.DataFrame) -> int:
        """Persist ``df`` for ``spec``.

        Returns:
            Number of rows written.
        """
