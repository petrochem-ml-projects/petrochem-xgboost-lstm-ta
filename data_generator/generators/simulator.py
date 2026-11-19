"""Orchestrates the five generator collaborators into one process simulation."""

from __future__ import annotations

import pandas as pd

from data_generator.domain.interfaces import (
    LatentStateGenerator,
    OutlierInjector,
    ProcessSimulator,
    RegimeScheduler,
    TagBuilder,
    TargetBuilder,
)
from data_generator.domain.spec import ProcessSpec
from data_generator.generators.latent import (
    ContiguousBlockRegimeScheduler,
    OUProcessLatentGenerator,
)
from data_generator.generators.noise import AR1NoiseGenerator
from data_generator.generators.outliers import RandomSpikeOutlierInjector
from data_generator.generators.tags import LinearNonlinearTagBuilder
from data_generator.generators.targets import LaggedNonlinearTargetBuilder


class ConfigDrivenSimulator(ProcessSimulator):
    """Runs one process's full simulation from five injected collaborators."""

    def __init__(
        self,
        regime_scheduler: RegimeScheduler,
        latent_generator: LatentStateGenerator,
        tag_builder: TagBuilder,
        target_builder: TargetBuilder,
        outlier_injector: OutlierInjector,
    ) -> None:
        """Store the five collaborators this simulator composes.

        Args:
            regime_scheduler: Assigns timesteps to regimes.
            latent_generator: Simulates the shared latent trajectory.
            tag_builder: Builds clean tag values from the latent trajectory.
            target_builder: Builds target values from the clean tag signal.
            outlier_injector: Corrupts a fraction of tag readings.
        """
        self._regime_scheduler = regime_scheduler
        self._latent_generator = latent_generator
        self._tag_builder = tag_builder
        self._target_builder = target_builder
        self._outlier_injector = outlier_injector

    def simulate(self, spec: ProcessSpec) -> pd.DataFrame:
        """Run the full simulation pipeline for `spec`.

        Targets are built from the clean tag signal; outlier injection runs on that
        same clean signal separately, so a sensor fault never retroactively changes a
        target's value.

        Returns:
            DataFrame with columns ``ts``, ``regime_label``, every tag column
            (``spec.tag_names`` order), every target column (``spec.target_names`` order),
            length ``spec.n_samples``.
        """
        regime_labels = self._regime_scheduler.build_labels(spec)
        latents = self._latent_generator.generate(spec, regime_labels)
        clean_tags_df = self._tag_builder.build(spec, latents)
        targets_df = self._target_builder.build(spec, clean_tags_df)
        observed_tags_df = self._outlier_injector.inject(spec, clean_tags_df)

        ts = pd.Series(
            pd.date_range(
                start=spec.start_timestamp,
                periods=spec.n_samples,
                freq=pd.Timedelta(minutes=spec.sampling_interval_minutes),
            ),
            name="ts",
        )
        regime_label = pd.Series(regime_labels, name="regime_label")

        return pd.concat([ts, regime_label, observed_tags_df, targets_df], axis=1)


def build_default_simulator() -> ProcessSimulator:
    """Wire the concrete Phase-1 generators into one ``ConfigDrivenSimulator``.

    The only function in ``data_generator`` permitted to import concrete
    generator classes directly -- every other caller depends on
    ``ProcessSimulator`` alone, so swapping an implementation only ever
    changes this one function.

    Returns:
        A ``ProcessSimulator`` ready to ``simulate()`` any ``ProcessSpec``.
    """
    regime_scheduler = ContiguousBlockRegimeScheduler()
    latent_generator = OUProcessLatentGenerator(regime_scheduler)
    noise_generator = AR1NoiseGenerator()
    tag_builder = LinearNonlinearTagBuilder(noise_generator)
    target_builder = LaggedNonlinearTargetBuilder(noise_generator)
    outlier_injector = RandomSpikeOutlierInjector()

    return ConfigDrivenSimulator(
        regime_scheduler, latent_generator, tag_builder, target_builder, outlier_injector
    )
