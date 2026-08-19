"""Domain configuration contract for one petrochemical process.

Every generator, spec builder, and Postgres sink in ``data_generator`` is
driven by a single :class:`ProcessSpec` instance -- this module is the one
place that shape is defined. A fifth process later means a new
``ProcessSpec``, never new engine code.

Example:
    >>> from data_generator.domain.spec import (
    ...     ProcessSpec,
    ...     TagContribution,
    ...     TagSpec,
    ...     TargetSpec,
    ... )
    >>> spec = ProcessSpec(
    ...     process_name="demo",
    ...     n_latent_states=2,
    ...     sampling_interval_minutes=5.0,
    ...     n_samples=100,
    ...     tags=[TagSpec(name="temp_1"), TagSpec(name="pressure_1")],
    ...     targets=[
    ...         TargetSpec(
    ...             name="yield_a",
    ...             sources=[
    ...                 TagContribution(tag="temp_1", coef=1.2, lag_minutes=10.0)
    ...             ],
    ...         )
    ...     ],
    ... )
    >>> spec.tag_names
    ['temp_1', 'pressure_1']
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class Nonlinearity(str, Enum):  # noqa: UP042 -- CLAUDE.md §4.1 mandates (str, Enum), not StrEnum
    """The five nonlinear transforms available to tags and targets."""

    IDENTITY = "identity"
    TANH = "tanh"
    SQUARE = "square"
    LOG1P = "log1p"
    SIGMOID = "sigmoid"


class TagContribution(BaseModel):
    """One input tag's weighted, time-lagged contribution to a target."""

    tag: str
    coef: float
    lag_minutes: float = 0.0


class TagSpec(BaseModel):
    """Configuration for one simulated sensor tag."""

    name: str
    unit: str = ""
    description: str = ""
    latent_weights: dict[int, float] = Field(default_factory=dict)
    base_value: float = 0.0
    nonlinearity: Nonlinearity = Nonlinearity.IDENTITY
    nonlinear_scale: float = 1.0
    ar_coef: float = 0.3
    noise_std: float = 1.0


class TargetSpec(BaseModel):
    """Configuration for one simulated process target (yield or quality var)."""

    name: str
    unit: str = ""
    description: str = ""
    base_value: float = 0.0
    sources: list[TagContribution] = Field(default_factory=list)
    nonlinearity: Nonlinearity = Nonlinearity.IDENTITY
    nonlinear_scale: float = 1.0
    noise_std: float = 0.1
    min_value: float | None = None
    max_value: float | None = None


class RegimeSpec(BaseModel):
    """Configuration for the process's operating-regime schedule."""

    n_regimes: int = 3
    latent_mean_shift_scale: float = 1.5
    latent_var_scale_min: float = 0.7
    latent_var_scale_max: float = 1.4
    seed: int = 0


class OutlierSpec(BaseModel):
    """Configuration for injected sensor-fault outliers."""

    fraction: float = 0.01
    magnitude_std_multiplier: float = 8.0
    seed: int = 1


class ProcessSpec(BaseModel):
    """Full configuration for one simulated petrochemical process.

    This is the single source of truth the simulation engine, the
    Postgres sink, and (later) ``ml_pipeline``'s ground-truth test all
    read from.
    """

    process_name: str
    description: str = ""
    n_latent_states: int
    latent_theta: float = 0.05
    latent_sigma: float = 1.0
    sampling_interval_minutes: float
    n_samples: int
    start_timestamp: str = "2024-01-01T00:00:00"
    tags: list[TagSpec]
    targets: list[TargetSpec]
    regimes: RegimeSpec = Field(default_factory=RegimeSpec)
    outliers: OutlierSpec = Field(default_factory=OutlierSpec)
    random_seed: int = 42

    @model_validator(mode="after")
    def _check_unique_tag_names(self) -> ProcessSpec:
        names = [tag.name for tag in self.tags]
        if len(names) != len(set(names)):
            duplicates = sorted({name for name in names if names.count(name) > 1})
            raise ValueError(f"duplicate tag name(s) in ProcessSpec.tags: {duplicates}")
        return self

    @property
    def tag_names(self) -> list[str]:
        """Ordered list of every tag's name."""
        return [tag.name for tag in self.tags]

    @property
    def target_names(self) -> list[str]:
        """Ordered list of every target's name."""
        return [target.name for target in self.targets]
