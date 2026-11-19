"""Unit tests for ``data_generator.generators.simulator``."""

from __future__ import annotations

import typing

import numpy as np
import pandas as pd
import pytest

from data_generator.domain.interfaces import (
    LatentStateGenerator,
    OutlierInjector,
    ProcessSimulator,
    RegimeScheduler,
    TagBuilder,
    TargetBuilder,
)
from data_generator.domain.spec import (
    OutlierSpec,
    ProcessSpec,
    TagContribution,
    TagSpec,
    TargetSpec,
)
from data_generator.generators.simulator import ConfigDrivenSimulator, build_default_simulator

pytestmark = pytest.mark.unit


def _spec(
    n_samples: int = 5,
    sampling_interval_minutes: float = 5.0,
    start_timestamp: str = "2024-01-01T00:00:00",
    outliers: OutlierSpec | None = None,
    random_seed: int = 42,
) -> ProcessSpec:
    return ProcessSpec(
        process_name="dummy",
        n_latent_states=2,
        sampling_interval_minutes=sampling_interval_minutes,
        n_samples=n_samples,
        start_timestamp=start_timestamp,
        tags=[TagSpec(name="tag_a"), TagSpec(name="tag_b")],
        targets=[TargetSpec(name="target_a")],
        outliers=outliers if outliers is not None else OutlierSpec(),
        random_seed=random_seed,
    )


class _RecordingRegimeScheduler(RegimeScheduler):
    """Fake returning a fixed labels array, recording every call's spec."""

    def __init__(self, labels: np.ndarray, order: list[str] | None = None) -> None:
        self.labels = labels
        self._order = order
        self.calls: list[ProcessSpec] = []

    def build_labels(self, spec: ProcessSpec) -> np.ndarray:
        self.calls.append(spec)
        if self._order is not None:
            self._order.append("regime_scheduler")
        return self.labels

    def regime_latent_shift(self, spec: ProcessSpec, regime_id: int) -> np.ndarray:
        raise NotImplementedError("not exercised by ConfigDrivenSimulator")

    def regime_latent_var_scale(self, spec: ProcessSpec, regime_id: int) -> float:
        raise NotImplementedError("not exercised by ConfigDrivenSimulator")


class _RecordingLatentGenerator(LatentStateGenerator):
    """Fake returning a fixed latents array, recording every call's arguments."""

    def __init__(self, latents: np.ndarray, order: list[str] | None = None) -> None:
        self.latents = latents
        self._order = order
        self.calls: list[tuple[ProcessSpec, np.ndarray]] = []

    def generate(self, spec: ProcessSpec, regime_labels: np.ndarray) -> np.ndarray:
        self.calls.append((spec, regime_labels))
        if self._order is not None:
            self._order.append("latent_generator")
        return self.latents


class _RecordingTagBuilder(TagBuilder):
    """Fake returning a fixed tags DataFrame, recording every call's arguments."""

    def __init__(self, tags_df: pd.DataFrame, order: list[str] | None = None) -> None:
        self.tags_df = tags_df
        self._order = order
        self.calls: list[tuple[ProcessSpec, np.ndarray]] = []

    def build(self, spec: ProcessSpec, latents: np.ndarray) -> pd.DataFrame:
        self.calls.append((spec, latents))
        if self._order is not None:
            self._order.append("tag_builder")
        return self.tags_df


class _RecordingTargetBuilder(TargetBuilder):
    """Fake returning a fixed targets DataFrame, recording every call's arguments."""

    def __init__(self, targets_df: pd.DataFrame, order: list[str] | None = None) -> None:
        self.targets_df = targets_df
        self._order = order
        self.calls: list[tuple[ProcessSpec, pd.DataFrame]] = []

    def build(self, spec: ProcessSpec, tags_df: pd.DataFrame) -> pd.DataFrame:
        self.calls.append((spec, tags_df))
        if self._order is not None:
            self._order.append("target_builder")
        return self.targets_df


class _RecordingOutlierInjector(OutlierInjector):
    """Fake returning a fixed observed-tags DataFrame, recording call arguments."""

    def __init__(self, observed_tags_df: pd.DataFrame, order: list[str] | None = None) -> None:
        self.observed_tags_df = observed_tags_df
        self._order = order
        self.calls: list[tuple[ProcessSpec, pd.DataFrame]] = []

    def inject(self, spec: ProcessSpec, tags_df: pd.DataFrame) -> pd.DataFrame:
        self.calls.append((spec, tags_df))
        if self._order is not None:
            self._order.append("outlier_injector")
        return self.observed_tags_df


def _build_fakes(
    n_samples: int = 5, order: list[str] | None = None
) -> tuple[
    _RecordingRegimeScheduler,
    _RecordingLatentGenerator,
    _RecordingTagBuilder,
    _RecordingTargetBuilder,
    _RecordingOutlierInjector,
    pd.DataFrame,
    pd.DataFrame,
]:
    """Build one fake per collaborator ABC, wired to known, distinguishable outputs."""
    regime_labels = np.array([0, 0, 1, 1, 1][:n_samples])
    latents = np.zeros((n_samples, 2))
    clean_tags_df = pd.DataFrame(
        {
            "tag_a": np.arange(n_samples, dtype=float),
            "tag_b": np.arange(n_samples, dtype=float) * 2.0,
        }
    )
    targets_df = pd.DataFrame({"target_a": np.arange(n_samples, dtype=float) * 10.0})
    observed_tags_df = clean_tags_df + 1000.0  # measurably different from clean_tags_df

    regime_scheduler = _RecordingRegimeScheduler(regime_labels, order)
    latent_generator = _RecordingLatentGenerator(latents, order)
    tag_builder = _RecordingTagBuilder(clean_tags_df, order)
    target_builder = _RecordingTargetBuilder(targets_df, order)
    outlier_injector = _RecordingOutlierInjector(observed_tags_df, order)

    return (
        regime_scheduler,
        latent_generator,
        tag_builder,
        target_builder,
        outlier_injector,
        clean_tags_df,
        observed_tags_df,
    )


# --- case 1 -----------------------------------------------------------------------
def test_calls_regime_scheduler_build_labels_with_spec() -> None:
    spec = _spec()
    regime_scheduler, latent_generator, tag_builder, target_builder, outlier_injector, _, _ = (
        _build_fakes()
    )
    simulator = ConfigDrivenSimulator(
        regime_scheduler, latent_generator, tag_builder, target_builder, outlier_injector
    )

    simulator.simulate(spec)

    assert regime_scheduler.calls == [spec]


# --- Case 2 --------------------------------------------------------------
def test_calls_latent_generator_generate_with_spec_and_regime_labels() -> None:
    spec = _spec()
    regime_scheduler, latent_generator, tag_builder, target_builder, outlier_injector, _, _ = (
        _build_fakes()
    )
    simulator = ConfigDrivenSimulator(
        regime_scheduler, latent_generator, tag_builder, target_builder, outlier_injector
    )

    simulator.simulate(spec)

    assert len(latent_generator.calls) == 1
    called_spec, called_regime_labels = latent_generator.calls[0]
    assert called_spec is spec
    np.testing.assert_array_equal(called_regime_labels, regime_scheduler.labels)


# --- Case 3 --------------------------------------------------------------
def test_calls_tag_builder_build_with_spec_and_latents() -> None:
    spec = _spec()
    regime_scheduler, latent_generator, tag_builder, target_builder, outlier_injector, _, _ = (
        _build_fakes()
    )
    simulator = ConfigDrivenSimulator(
        regime_scheduler, latent_generator, tag_builder, target_builder, outlier_injector
    )

    simulator.simulate(spec)

    assert len(tag_builder.calls) == 1
    called_spec, called_latents = tag_builder.calls[0]
    assert called_spec is spec
    np.testing.assert_array_equal(called_latents, latent_generator.latents)


# --- Case 4 --------------------------------------------------------------
def test_calls_target_builder_build_with_spec_and_clean_tags() -> None:
    spec = _spec()
    (
        regime_scheduler,
        latent_generator,
        tag_builder,
        target_builder,
        outlier_injector,
        clean_tags_df,
        _,
    ) = _build_fakes()
    simulator = ConfigDrivenSimulator(
        regime_scheduler, latent_generator, tag_builder, target_builder, outlier_injector
    )

    simulator.simulate(spec)

    assert len(target_builder.calls) == 1
    called_spec, called_tags_df = target_builder.calls[0]
    assert called_spec is spec
    pd.testing.assert_frame_equal(called_tags_df, clean_tags_df)


# --- Case 5 --------------------------------------------------------------
def test_calls_outlier_injector_inject_with_spec_and_clean_tags_not_targets() -> None:
    spec = _spec()
    (
        regime_scheduler,
        latent_generator,
        tag_builder,
        target_builder,
        outlier_injector,
        clean_tags_df,
        _,
    ) = _build_fakes()
    simulator = ConfigDrivenSimulator(
        regime_scheduler, latent_generator, tag_builder, target_builder, outlier_injector
    )

    simulator.simulate(spec)

    assert len(outlier_injector.calls) == 1
    called_spec, called_tags_df = outlier_injector.calls[0]
    assert called_spec is spec
    pd.testing.assert_frame_equal(called_tags_df, clean_tags_df)


# --- Case 6 --------------------------------------------------------------
def test_target_builder_and_outlier_injector_both_receive_clean_tags_regardless_of_order() -> None:
    spec = _spec()
    order: list[str] = []
    (
        regime_scheduler,
        latent_generator,
        tag_builder,
        target_builder,
        outlier_injector,
        clean_tags_df,
        _,
    ) = _build_fakes(order=order)
    simulator = ConfigDrivenSimulator(
        regime_scheduler, latent_generator, tag_builder, target_builder, outlier_injector
    )

    simulator.simulate(spec)

    assert "target_builder" in order
    assert "outlier_injector" in order
    pd.testing.assert_frame_equal(target_builder.calls[0][1], clean_tags_df)
    pd.testing.assert_frame_equal(outlier_injector.calls[0][1], clean_tags_df)


# --- Case 7 --------------------------------------------------------------
def test_output_contains_ts_regime_label_tag_and_target_columns_in_order() -> None:
    spec = _spec()
    regime_scheduler, latent_generator, tag_builder, target_builder, outlier_injector, _, _ = (
        _build_fakes()
    )
    simulator = ConfigDrivenSimulator(
        regime_scheduler, latent_generator, tag_builder, target_builder, outlier_injector
    )

    result = simulator.simulate(spec)

    assert list(result.columns) == ["ts", "regime_label", "tag_a", "tag_b", "target_a"]


# --- Case 8 --------------------------------------------------------------
def test_ts_column_is_evenly_spaced_starting_at_start_timestamp() -> None:
    spec = _spec(n_samples=5, sampling_interval_minutes=5.0, start_timestamp="2024-01-01T00:00:00")
    regime_scheduler, latent_generator, tag_builder, target_builder, outlier_injector, _, _ = (
        _build_fakes(n_samples=5)
    )
    simulator = ConfigDrivenSimulator(
        regime_scheduler, latent_generator, tag_builder, target_builder, outlier_injector
    )

    result = simulator.simulate(spec)

    assert result["ts"].dtype.kind == "M"
    assert len(result["ts"]) == 5
    assert result["ts"].iloc[0] == pd.Timestamp("2024-01-01T00:00:00")
    diffs = result["ts"].diff().dropna().unique()
    assert len(diffs) == 1
    assert diffs[0] == pd.Timedelta(minutes=5.0)


# --- Case 9 --------------------------------------------------------------
def test_regime_label_column_equals_regime_scheduler_output() -> None:
    spec = _spec()
    regime_scheduler, latent_generator, tag_builder, target_builder, outlier_injector, _, _ = (
        _build_fakes()
    )
    simulator = ConfigDrivenSimulator(
        regime_scheduler, latent_generator, tag_builder, target_builder, outlier_injector
    )

    result = simulator.simulate(spec)

    np.testing.assert_array_equal(result["regime_label"].to_numpy(), regime_scheduler.labels)


# --- Case 10 -------------------------------------------------------------
def test_tag_columns_equal_outlier_injector_output_not_clean_tags() -> None:
    spec = _spec()
    (
        regime_scheduler,
        latent_generator,
        tag_builder,
        target_builder,
        outlier_injector,
        clean_tags_df,
        observed_tags_df,
    ) = _build_fakes()
    simulator = ConfigDrivenSimulator(
        regime_scheduler, latent_generator, tag_builder, target_builder, outlier_injector
    )

    result = simulator.simulate(spec)

    pd.testing.assert_frame_equal(result[["tag_a", "tag_b"]], observed_tags_df)
    assert not result[["tag_a", "tag_b"]].equals(clean_tags_df)


# --- Case 11 -------------------------------------------------------------
def test_target_columns_equal_target_builder_output() -> None:
    spec = _spec()
    regime_scheduler, latent_generator, tag_builder, target_builder, outlier_injector, _, _ = (
        _build_fakes()
    )
    simulator = ConfigDrivenSimulator(
        regime_scheduler, latent_generator, tag_builder, target_builder, outlier_injector
    )

    result = simulator.simulate(spec)

    pd.testing.assert_frame_equal(result[["target_a"]], target_builder.targets_df)


# --- Case 12 -------------------------------------------------------------
def test_output_row_count_equals_spec_n_samples() -> None:
    spec = _spec(n_samples=5)
    regime_scheduler, latent_generator, tag_builder, target_builder, outlier_injector, _, _ = (
        _build_fakes(n_samples=5)
    )
    simulator = ConfigDrivenSimulator(
        regime_scheduler, latent_generator, tag_builder, target_builder, outlier_injector
    )

    result = simulator.simulate(spec)

    assert len(result) == 5


# --- Case 13 -------------------------------------------------------------
def test_output_has_no_extra_columns() -> None:
    spec = _spec()
    regime_scheduler, latent_generator, tag_builder, target_builder, outlier_injector, _, _ = (
        _build_fakes()
    )
    simulator = ConfigDrivenSimulator(
        regime_scheduler, latent_generator, tag_builder, target_builder, outlier_injector
    )

    result = simulator.simulate(spec)

    assert len(result.columns) == 2 + len(spec.tag_names) + len(spec.target_names)


# --- Case 14 -------------------------------------------------------------
def test_satisfies_process_simulator_interface() -> None:
    spec = _spec()
    regime_scheduler, latent_generator, tag_builder, target_builder, outlier_injector, _, _ = (
        _build_fakes()
    )
    simulator: ProcessSimulator = ConfigDrivenSimulator(
        regime_scheduler, latent_generator, tag_builder, target_builder, outlier_injector
    )

    result = simulator.simulate(spec)

    assert isinstance(result, pd.DataFrame)


# --- Case 15 -------------------------------------------------------------
def test_build_default_simulator_returns_process_simulator() -> None:
    simulator = build_default_simulator()

    assert isinstance(simulator, ProcessSimulator)


# --- Case 16 -------------------------------------------------------------
def test_build_default_simulator_does_not_leak_concrete_type_as_return_annotation() -> None:
    hints = typing.get_type_hints(build_default_simulator)

    assert hints["return"] is ProcessSimulator


def _small_real_spec(outliers: OutlierSpec) -> ProcessSpec:
    return ProcessSpec(
        process_name="e2e",
        n_latent_states=2,
        sampling_interval_minutes=5.0,
        n_samples=30,
        tags=[
            TagSpec(name="tag_a", latent_weights={0: 1.0}),
            TagSpec(name="tag_b", latent_weights={1: 1.0}),
        ],
        targets=[
            TargetSpec(
                name="target_a",
                sources=[TagContribution(tag="tag_a", coef=1.5, lag_minutes=10.0)],
            )
        ],
        outliers=outliers,
        random_seed=7,
    )


# --- Case 17 -------------------------------------------------------------
def test_build_default_simulator_end_to_end_produces_finite_reproducible_output() -> None:
    spec = _small_real_spec(OutlierSpec(fraction=0.1, magnitude_std_multiplier=5.0))

    simulator = build_default_simulator()
    first = simulator.simulate(spec)
    second = simulator.simulate(spec)

    assert np.isfinite(first[["tag_a", "tag_b", "target_a"]].to_numpy()).all()
    assert list(first.columns) == ["ts", "regime_label", "tag_a", "tag_b", "target_a"]
    assert len(first) == 30
    pd.testing.assert_frame_equal(first, second)


# --- Case 18 -------------------------------------------------------------
def test_build_default_simulator_targets_unaffected_by_outlier_injection() -> None:
    spec_clean = _small_real_spec(OutlierSpec(fraction=0.0))
    spec_corrupted = _small_real_spec(OutlierSpec(fraction=0.5, magnitude_std_multiplier=20.0))

    simulator = build_default_simulator()
    result_clean = simulator.simulate(spec_clean)
    result_corrupted = simulator.simulate(spec_corrupted)

    pd.testing.assert_frame_equal(result_clean[["target_a"]], result_corrupted[["target_a"]])
    assert not result_clean[["tag_a", "tag_b"]].equals(result_corrupted[["tag_a", "tag_b"]])
