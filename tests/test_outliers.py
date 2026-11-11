"""Unit tests for ``data_generator.generators.outliers``."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from data_generator.domain.interfaces import OutlierInjector
from data_generator.domain.spec import OutlierSpec, ProcessSpec, TagSpec
from data_generator.generators.outliers import RandomSpikeOutlierInjector

pytestmark = pytest.mark.unit


def _spec(fraction: float, magnitude_std_multiplier: float, seed: int) -> ProcessSpec:
    return ProcessSpec(
        process_name="dummy",
        n_latent_states=1,
        sampling_interval_minutes=1.0,
        n_samples=1,
        tags=[TagSpec(name="dummy")],
        targets=[],
        outliers=OutlierSpec(
            fraction=fraction,
            magnitude_std_multiplier=magnitude_std_multiplier,
            seed=seed,
        ),
    )


def _fixture() -> pd.DataFrame:
    """4 rows x 3 cols = 12 cells; a fraction of 0.25 selects exactly 3."""
    return pd.DataFrame(
        {
            "a": [1.0, 2.0, 3.0, 4.0],
            "b": [10.0, 20.0, 30.0, 40.0],
            "c": [100.0, 200.0, 300.0, 400.0],
        }
    )


def test_output_shape_matches_input() -> None:
    tags_df = _fixture()
    spec = _spec(fraction=0.25, magnitude_std_multiplier=2.0, seed=7)
    out = RandomSpikeOutlierInjector().inject(spec, tags_df)
    assert out.shape == tags_df.shape


def test_output_columns_match_input_columns_in_order() -> None:
    tags_df = _fixture()
    spec = _spec(fraction=0.25, magnitude_std_multiplier=2.0, seed=7)
    out = RandomSpikeOutlierInjector().inject(spec, tags_df)
    assert list(out.columns) == list(tags_df.columns) == ["a", "b", "c"]


def test_zero_fraction_leaves_values_unchanged() -> None:
    tags_df = _fixture()
    spec = _spec(fraction=0.0, magnitude_std_multiplier=8.0, seed=7)
    out = RandomSpikeOutlierInjector().inject(spec, tags_df)
    assert np.array_equal(out.to_numpy(), tags_df.to_numpy())


def test_input_dataframe_is_not_mutated() -> None:
    tags_df = _fixture()
    original = tags_df.copy()
    spec = _spec(fraction=0.25, magnitude_std_multiplier=2.0, seed=7)
    RandomSpikeOutlierInjector().inject(spec, tags_df)
    pd.testing.assert_frame_equal(tags_df, original)


def test_number_of_modified_cells_matches_hand_computed_formula() -> None:
    tags_df = _fixture()  # 12 cells; round(0.25 * 12) = 3
    spec = _spec(fraction=0.25, magnitude_std_multiplier=2.0, seed=7)
    out = RandomSpikeOutlierInjector().inject(spec, tags_df)
    n_modified = int((out.to_numpy() != tags_df.to_numpy()).sum())
    assert n_modified == 3


def test_injected_delta_magnitude_matches_hand_computed_value() -> None:
    # Hand-verified: seed=7 on _fixture() selects (row=3,col=0), (row=2,col=0),
    # (row=2,col=2) with signs [+1, +1, -1].
    tags_df = _fixture()
    spec = _spec(fraction=0.25, magnitude_std_multiplier=2.0, seed=7)
    out = RandomSpikeOutlierInjector().inject(spec, tags_df)
    delta = out.to_numpy() - tags_df.to_numpy()

    std_a = tags_df["a"].std(ddof=1)
    std_c = tags_df["c"].std(ddof=1)
    assert delta[3, 0] == pytest.approx(2.0 * std_a)
    assert delta[2, 0] == pytest.approx(2.0 * std_a)
    assert delta[2, 2] == pytest.approx(-2.0 * std_c)


def test_injected_sign_is_always_plus_or_minus_one_times_expected_magnitude() -> None:
    tags_df = _fixture()
    spec = _spec(fraction=0.25, magnitude_std_multiplier=2.0, seed=7)
    out = RandomSpikeOutlierInjector().inject(spec, tags_df)
    delta = out.to_numpy() - tags_df.to_numpy()
    stds = tags_df.to_numpy().std(axis=0, ddof=1)

    modified_rows, modified_cols = np.nonzero(delta)
    for row, col in zip(modified_rows, modified_cols, strict=True):
        assert abs(delta[row, col]) == pytest.approx(2.0 * stds[col])


def test_same_seed_produces_identical_output_across_two_calls() -> None:
    tags_df = _fixture()
    spec = _spec(fraction=0.25, magnitude_std_multiplier=2.0, seed=7)
    injector = RandomSpikeOutlierInjector()
    first = injector.inject(spec, tags_df)
    second = injector.inject(spec, tags_df)
    pd.testing.assert_frame_equal(first, second)


def test_different_seeds_select_different_cells() -> None:
    tags_df = _fixture()
    injector = RandomSpikeOutlierInjector()
    first = injector.inject(_spec(fraction=0.25, magnitude_std_multiplier=2.0, seed=7), tags_df)
    second = injector.inject(_spec(fraction=0.25, magnitude_std_multiplier=2.0, seed=8), tags_df)
    assert not first.equals(second)


def test_unselected_cells_retain_exact_original_values() -> None:
    tags_df = _fixture()
    spec = _spec(fraction=0.25, magnitude_std_multiplier=2.0, seed=7)
    out = RandomSpikeOutlierInjector().inject(spec, tags_df)

    selected = {(3, 0), (2, 0), (2, 2)}
    for row in range(tags_df.shape[0]):
        for col in range(tags_df.shape[1]):
            if (row, col) not in selected:
                assert out.iat[row, col] == tags_df.iat[row, col]


def test_column_std_uses_sample_ddof_not_population_ddof() -> None:
    tags_df = _fixture()
    spec = _spec(fraction=0.25, magnitude_std_multiplier=2.0, seed=7)
    out = RandomSpikeOutlierInjector().inject(spec, tags_df)
    delta_a = out.to_numpy()[3, 0] - tags_df.to_numpy()[3, 0]

    std_a_sample = tags_df["a"].std(ddof=1)
    std_a_population = tags_df["a"].std(ddof=0)
    assert std_a_sample != pytest.approx(std_a_population)
    assert delta_a == pytest.approx(2.0 * std_a_sample)
    assert delta_a != pytest.approx(2.0 * std_a_population)


def test_column_std_is_computed_before_mutation_not_recomputed_mid_injection() -> None:
    # Column "a" is hit twice (rows 2 and 3) with the same sign. A correct
    # upfront std gives both hits the identical delta; an implementation that
    # recomputed std incrementally mid-injection would not.
    tags_df = _fixture()
    spec = _spec(fraction=0.25, magnitude_std_multiplier=2.0, seed=7)
    out = RandomSpikeOutlierInjector().inject(spec, tags_df)
    delta = out.to_numpy() - tags_df.to_numpy()
    assert delta[3, 0] == pytest.approx(delta[2, 0])


def test_fraction_rounding_to_zero_outliers_leaves_output_unchanged() -> None:
    tags_df = _fixture()
    spec = _spec(fraction=0.01, magnitude_std_multiplier=2.0, seed=7)  # round(0.12) = 0
    out = RandomSpikeOutlierInjector().inject(spec, tags_df)
    assert np.array_equal(out.to_numpy(), tags_df.to_numpy())


def test_magnitude_std_multiplier_of_zero_leaves_selected_cells_unchanged() -> None:
    tags_df = _fixture()
    spec = _spec(fraction=0.25, magnitude_std_multiplier=0.0, seed=7)
    out = RandomSpikeOutlierInjector().inject(spec, tags_df)
    assert np.array_equal(out.to_numpy(), tags_df.to_numpy())


def test_single_row_dataframe_produces_nan_not_an_exception() -> None:
    # ddof=1 std is undefined for a single sample -- this is an accepted,
    # degenerate edge case (D2): no real ProcessSpec ever has n_samples=1.
    tags_df = pd.DataFrame({"a": [5.0], "b": [6.0], "c": [7.0], "d": [8.0], "e": [9.0]})
    spec = _spec(fraction=0.4, magnitude_std_multiplier=2.0, seed=3)  # round(2.0) = 2
    out = RandomSpikeOutlierInjector().inject(spec, tags_df)
    assert out.shape == tags_df.shape
    assert np.isnan(out.to_numpy()).sum() == 2


def test_single_column_dataframe_does_not_raise_and_stays_finite() -> None:
    tags_df = pd.DataFrame({"a": [5.0, 6.0, 7.0, 8.0, 9.0]})
    spec = _spec(fraction=0.4, magnitude_std_multiplier=2.0, seed=3)  # round(2.0) = 2
    out = RandomSpikeOutlierInjector().inject(spec, tags_df)
    assert out.shape == tags_df.shape
    assert np.isfinite(out.to_numpy()).all()


def test_satisfies_outlier_injector_interface() -> None:
    injector: OutlierInjector = RandomSpikeOutlierInjector()
    tags_df = _fixture()
    spec = _spec(fraction=0.1, magnitude_std_multiplier=2.0, seed=1)
    out = injector.inject(spec, tags_df)
    assert out.shape == tags_df.shape


def test_fraction_resolving_to_more_cells_than_exist_raises_value_error() -> None:
    tags_df = _fixture()
    spec = _spec(fraction=1.5, magnitude_std_multiplier=2.0, seed=7)
    with pytest.raises(ValueError):
        RandomSpikeOutlierInjector().inject(spec, tags_df)


def test_fraction_of_one_modifies_every_cell() -> None:
    tags_df = _fixture()
    spec = _spec(fraction=1.0, magnitude_std_multiplier=2.0, seed=7)
    out = RandomSpikeOutlierInjector().inject(spec, tags_df)
    assert np.all(out.to_numpy() != tags_df.to_numpy())


def test_integration_with_realistic_multi_column_fixture_is_finite() -> None:
    rng = np.random.default_rng(0)
    tags_df = pd.DataFrame(
        rng.normal(loc=50.0, scale=5.0, size=(50, 5)),
        columns=[f"tag_{i}" for i in range(5)],
    )
    spec = _spec(fraction=0.05, magnitude_std_multiplier=8.0, seed=11)
    out = RandomSpikeOutlierInjector().inject(spec, tags_df)

    expected_n_modified = round(0.05 * 50 * 5)
    n_modified = int((out.to_numpy() != tags_df.to_numpy()).sum())

    assert out.shape == tags_df.shape
    assert np.isfinite(out.to_numpy()).all()
    assert n_modified == expected_n_modified
