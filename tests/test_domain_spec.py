"""Unit tests for the ProcessSpec domain configuration contract."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from data_generator.domain.spec import (
    Nonlinearity,
    OutlierSpec,
    ProcessSpec,
    RegimeSpec,
    TagContribution,
    TagSpec,
    TargetSpec,
)


def _minimal_process_spec(**overrides: object) -> ProcessSpec:
    defaults: dict[str, object] = {
        "process_name": "demo",
        "n_latent_states": 2,
        "sampling_interval_minutes": 5.0,
        "n_samples": 100,
        "tags": [TagSpec(name="tag_a"), TagSpec(name="tag_b")],
        "targets": [
            TargetSpec(
                name="target_a",
                sources=[TagContribution(tag="tag_a", coef=1.0, lag_minutes=10.0)],
            )
        ],
    }
    defaults.update(overrides)
    return ProcessSpec(**defaults)  # type: ignore[arg-type]


def test_nonlinearity_has_five_members() -> None:
    assert {member.value for member in Nonlinearity} == {
        "identity",
        "tanh",
        "square",
        "log1p",
        "sigmoid",
    }
    assert isinstance(Nonlinearity.TANH, str)


def test_tag_spec_defaults() -> None:
    tag = TagSpec(name="t1")
    assert tag.unit == ""
    assert tag.description == ""
    assert tag.latent_weights == {}
    assert tag.base_value == 0.0
    assert tag.nonlinearity == Nonlinearity.IDENTITY
    assert tag.nonlinear_scale == 1.0
    assert tag.ar_coef == 0.3
    assert tag.noise_std == 1.0


def test_tag_contribution_defaults() -> None:
    contribution = TagContribution(tag="t1", coef=1.0)
    assert contribution.lag_minutes == 0.0


def test_target_spec_defaults() -> None:
    target = TargetSpec(name="y1")
    assert target.sources == []
    assert target.min_value is None
    assert target.max_value is None
    assert target.base_value == 0.0
    assert target.nonlinearity == Nonlinearity.IDENTITY
    assert target.nonlinear_scale == 1.0
    assert target.noise_std == 0.1


def test_regime_spec_defaults() -> None:
    regime = RegimeSpec()
    assert regime.n_regimes == 3
    assert regime.latent_mean_shift_scale == 1.5
    assert regime.latent_var_scale_min == 0.7
    assert regime.latent_var_scale_max == 1.4
    assert regime.seed == 0


def test_outlier_spec_defaults() -> None:
    outliers = OutlierSpec()
    assert outliers.fraction == 0.01
    assert outliers.magnitude_std_multiplier == 8.0
    assert outliers.seed == 1


def test_process_spec_minimal_construction() -> None:
    spec = _minimal_process_spec()
    assert spec.tag_names == ["tag_a", "tag_b"]
    assert spec.target_names == ["target_a"]
    assert isinstance(spec.regimes, RegimeSpec)
    assert isinstance(spec.outliers, OutlierSpec)


def test_process_spec_rejects_duplicate_tag_names() -> None:
    with pytest.raises(ValidationError):
        _minimal_process_spec(tags=[TagSpec(name="dup"), TagSpec(name="dup")])


def test_tag_names_and_target_names_properties() -> None:
    spec = _minimal_process_spec()
    assert spec.tag_names == [tag.name for tag in spec.tags]
    assert spec.target_names == [target.name for target in spec.targets]


def test_mutable_defaults_are_independent_across_instances() -> None:
    tag_one = TagSpec(name="one")
    tag_two = TagSpec(name="two")
    tag_one.latent_weights[0] = 1.0
    assert tag_two.latent_weights == {}

    spec_one = _minimal_process_spec()
    spec_two = _minimal_process_spec()
    spec_one.regimes.seed = 99
    assert spec_two.regimes.seed == 0


@pytest.mark.parametrize(
    "missing_field",
    [
        "process_name",
        "n_latent_states",
        "sampling_interval_minutes",
        "n_samples",
        "tags",
        "targets",
    ],
)
def test_process_spec_requires_core_fields_explicitly(missing_field: str) -> None:
    kwargs: dict[str, object] = {
        "process_name": "demo",
        "n_latent_states": 2,
        "sampling_interval_minutes": 5.0,
        "n_samples": 100,
        "tags": [TagSpec(name="tag_a")],
        "targets": [],
    }
    del kwargs[missing_field]
    with pytest.raises(ValidationError):
        ProcessSpec(**kwargs)  # type: ignore[arg-type]
