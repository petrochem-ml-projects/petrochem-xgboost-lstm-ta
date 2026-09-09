"""Unit tests for ``data_generator.domain.interfaces``.

Each ABC has no runtime logic of its own, so these tests exercise the
two things that actually matter for a contracts-only module: that each
ABC is genuinely abstract (cannot be instantiated directly) and that its
contract is genuinely satisfiable (a minimal conforming subclass can be
instantiated and called).
"""

from __future__ import annotations

from abc import ABC

import numpy as np
import pandas as pd
import pytest

from data_generator.domain.interfaces import (
    DataSink,
    LatentStateGenerator,
    NoiseGenerator,
    OutlierInjector,
    ProcessSimulator,
    RegimeScheduler,
    TagBuilder,
    TargetBuilder,
)
from data_generator.domain.spec import ProcessSpec

ALL_ABCS = (
    LatentStateGenerator,
    RegimeScheduler,
    NoiseGenerator,
    TagBuilder,
    TargetBuilder,
    OutlierInjector,
    ProcessSimulator,
    DataSink,
)

SINGLE_METHOD_ABCS = (
    (LatentStateGenerator, "generate"),
    (NoiseGenerator, "generate"),
    (TagBuilder, "build"),
    (TargetBuilder, "build"),
    (OutlierInjector, "inject"),
    (ProcessSimulator, "simulate"),
)


def _minimal_spec() -> ProcessSpec:
    return ProcessSpec(
        process_name="dummy",
        n_latent_states=1,
        sampling_interval_minutes=1.0,
        n_samples=3,
        tags=[],
        targets=[],
    )


@pytest.mark.parametrize("abc_cls", ALL_ABCS)
def test_abcs_cannot_be_instantiated_directly(abc_cls: type[ABC]) -> None:
    with pytest.raises(TypeError):
        abc_cls()


@pytest.mark.parametrize("abc_cls,method_name", SINGLE_METHOD_ABCS)
def test_single_method_abcs_have_exactly_one_abstract_method(
    abc_cls: type[ABC], method_name: str
) -> None:
    assert set(abc_cls.__abstractmethods__) == {method_name}


def test_regime_scheduler_has_exactly_three_abstract_methods() -> None:
    assert set(RegimeScheduler.__abstractmethods__) == {
        "build_labels",
        "regime_latent_shift",
        "regime_latent_var_scale",
    }


def test_data_sink_has_exactly_two_abstract_methods() -> None:
    assert set(DataSink.__abstractmethods__) == {"prepare", "write"}


def test_minimal_conforming_latent_state_generator_is_instantiable() -> None:
    class DummyLatentStateGenerator(LatentStateGenerator):
        def generate(self, spec: ProcessSpec, _regime_labels: np.ndarray) -> np.ndarray:
            return np.zeros((spec.n_samples, spec.n_latent_states))

    spec = _minimal_spec()
    labels = np.zeros(spec.n_samples, dtype=int)
    result = DummyLatentStateGenerator().generate(spec, labels)
    assert result.shape == (spec.n_samples, spec.n_latent_states)


def test_minimal_conforming_regime_scheduler_is_instantiable() -> None:
    class DummyRegimeScheduler(RegimeScheduler):
        def build_labels(self, spec: ProcessSpec) -> np.ndarray:
            return np.zeros(spec.n_samples, dtype=int)

        def regime_latent_shift(self, spec: ProcessSpec, _regime_id: int) -> np.ndarray:
            return np.zeros(spec.n_latent_states)

        def regime_latent_var_scale(self, _spec: ProcessSpec, _regime_id: int) -> float:
            return 1.0

    spec = _minimal_spec()
    scheduler = DummyRegimeScheduler()
    assert scheduler.build_labels(spec).shape == (spec.n_samples,)
    assert scheduler.regime_latent_shift(spec, 0).shape == (spec.n_latent_states,)
    assert scheduler.regime_latent_var_scale(spec, 0) == 1.0


def test_minimal_conforming_noise_generator_is_instantiable() -> None:
    class DummyNoiseGenerator(NoiseGenerator):
        def generate(self, n_samples: int, _ar_coef: float, _std: float, _seed: int) -> np.ndarray:
            return np.zeros(n_samples)

    result = DummyNoiseGenerator().generate(5, 0.3, 1.0, 0)
    assert result.shape == (5,)


def test_minimal_conforming_tag_builder_is_instantiable() -> None:
    class DummyTagBuilder(TagBuilder):
        def build(self, spec: ProcessSpec, latents: np.ndarray) -> pd.DataFrame:
            return pd.DataFrame({name: np.zeros(latents.shape[0]) for name in spec.tag_names})

    spec = _minimal_spec()
    latents = np.zeros((spec.n_samples, spec.n_latent_states))
    result = DummyTagBuilder().build(spec, latents)
    assert list(result.columns) == spec.tag_names


def test_minimal_conforming_target_builder_is_instantiable() -> None:
    class DummyTargetBuilder(TargetBuilder):
        def build(self, spec: ProcessSpec, tags_df: pd.DataFrame) -> pd.DataFrame:
            return pd.DataFrame({name: np.zeros(len(tags_df)) for name in spec.target_names})

    spec = _minimal_spec()
    tags_df = pd.DataFrame(index=range(spec.n_samples))
    result = DummyTargetBuilder().build(spec, tags_df)
    assert list(result.columns) == spec.target_names


def test_minimal_conforming_outlier_injector_is_instantiable() -> None:
    class DummyOutlierInjector(OutlierInjector):
        def inject(self, _spec: ProcessSpec, tags_df: pd.DataFrame) -> pd.DataFrame:
            return tags_df.copy()

    spec = _minimal_spec()
    tags_df = pd.DataFrame({"a": [1.0, 2.0]})
    result = DummyOutlierInjector().inject(spec, tags_df)
    pd.testing.assert_frame_equal(result, tags_df)


def test_minimal_conforming_process_simulator_is_instantiable() -> None:
    class DummyProcessSimulator(ProcessSimulator):
        def simulate(self, _spec: ProcessSpec) -> pd.DataFrame:
            return pd.DataFrame({"ts": [], "regime_label": []})

    spec = _minimal_spec()
    result = DummyProcessSimulator().simulate(spec)
    assert "ts" in result.columns
    assert "regime_label" in result.columns


def test_minimal_conforming_data_sink_is_instantiable() -> None:
    class DummyDataSink(DataSink):
        def prepare(self, _spec: ProcessSpec) -> None:
            return None

        def write(self, _spec: ProcessSpec, df: pd.DataFrame) -> int:
            return len(df)

    spec = _minimal_spec()
    sink = DummyDataSink()
    sink.prepare(spec)
    assert sink.write(spec, pd.DataFrame({"a": [1, 2, 3]})) == 3


def test_partial_regime_scheduler_subclass_still_abstract() -> None:
    class PartialRegimeScheduler(RegimeScheduler):
        def build_labels(self, spec: ProcessSpec) -> np.ndarray:
            return np.zeros(spec.n_samples, dtype=int)

        def regime_latent_shift(self, spec: ProcessSpec, _regime_id: int) -> np.ndarray:
            return np.zeros(spec.n_latent_states)

        # regime_latent_var_scale intentionally not implemented

    with pytest.raises(TypeError):
        PartialRegimeScheduler()  # type: ignore[abstract]


def test_partial_data_sink_subclass_still_abstract() -> None:
    class PartialDataSink(DataSink):
        def prepare(self, _spec: ProcessSpec) -> None:
            return None

        # write intentionally not implemented

    with pytest.raises(TypeError):
        PartialDataSink()  # type: ignore[abstract]
