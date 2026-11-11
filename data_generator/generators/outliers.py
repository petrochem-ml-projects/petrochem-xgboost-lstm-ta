"""Concrete outlier injector corrupting a seeded fraction of clean tag readings.

``RandomSpikeOutlierInjector`` is what gives Phase 2's EDA outlier analyzer
and Phase 3's ``OneClassSVMDenoiser`` something real to detect: a small,
seeded fraction of cells in an otherwise-clean tag DataFrame receive a large
additive spike, sized relative to each column's own natural variability
(CLAUDE.md Section 4.8). This models sensor faults -- a stuck transmitter, a
transient electrical glitch -- rather than the smooth, physically-motivated
variation ``latent.py``/``tags.py`` already produce.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from data_generator.domain.interfaces import OutlierInjector
from data_generator.domain.spec import ProcessSpec


class RandomSpikeOutlierInjector(OutlierInjector):
    """Injects seeded, randomly-signed spikes into a fraction of tag cells."""

    def inject(self, spec: ProcessSpec, tags_df: pd.DataFrame) -> pd.DataFrame:
        """Return a copy of ``tags_df`` with a seeded fraction of cells spiked.

        ``round(spec.outliers.fraction * n_rows * n_cols)`` distinct cells
        are selected via one seeded, without-replacement draw over the
        flattened cell index space -- guaranteeing exactly that many
        distinct cells, no collision handling needed. Each selected cell's
        value changes by ``+/- spec.outliers.magnitude_std_multiplier``
        times its column's sample standard deviation (``ddof=1``), computed
        from the clean, pre-injection values -- never recomputed
        mid-injection.

        Args:
            spec: The process specification; reads
                ``spec.outliers.fraction``,
                ``spec.outliers.magnitude_std_multiplier``, and
                ``spec.outliers.seed``.
            tags_df: Clean tag values to corrupt. Never mutated.

        Returns:
            A new DataFrame, same shape and columns as ``tags_df``.

        Raises:
            ValueError: If ``spec.outliers.fraction`` resolves to more
                cells than exist in ``tags_df`` (e.g. ``fraction > 1.0``)
                -- no defensive clamp; propagated from
                ``numpy.random.Generator.choice``.
        """
        n_rows, n_cols = tags_df.shape
        n_cells = n_rows * n_cols
        n_outliers = round(spec.outliers.fraction * n_cells)

        rng = np.random.default_rng(spec.outliers.seed)
        flat_indices = rng.choice(n_cells, size=n_outliers, replace=False)
        rows = flat_indices // n_cols
        cols = flat_indices % n_cols
        signs = rng.choice([-1.0, 1.0], size=n_outliers)

        values = tags_df.to_numpy(dtype=np.float64, copy=True)
        column_stds = values.std(axis=0, ddof=1)
        values[rows, cols] += signs * spec.outliers.magnitude_std_multiplier * column_stds[cols]

        return pd.DataFrame(values, columns=tags_df.columns, index=tags_df.index)
