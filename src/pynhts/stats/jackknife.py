"""Stratified jackknife (JKn) variance for the NHTS 2017 replicate weights.

The 2017 NHTS weighting report (Westat/ORNL) forms ``G = 98`` replicates by deleting one of
7 variance units at a time inside each of 14 variance strata. With ``n_h = 7`` units in every
stratum the JKn variance of an estimate ``theta`` is

    Var(theta) = sum_h (n_h - 1)/n_h * sum_{r in h} (theta_r - theta)^2
               = (6/7) * sum_{r=1}^{98} (theta_r - theta)^2 .

The 95 % margin of error that FHWA prints is ``t(0.975, df) * SE`` with ``df = 98``; this was
checked against the published Table 1 margins of error (ratio MOE/SE = 1.984 = t(0.975, 98)).
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray

N_REPLICATES = 98
N_STRATA = 14
UNITS_PER_STRATUM = 7
JKN_FACTOR = (UNITS_PER_STRATUM - 1) / UNITS_PER_STRATUM  # 6/7
DEFAULT_DF = N_REPLICATES


def jackknife_variance(
    full: ArrayLike, replicates: ArrayLike, factor: float = JKN_FACTOR,
    n_replicates: int = N_REPLICATES,
) -> NDArray[np.float64]:
    """JKn variance of one or several estimates.

    Args:
        full: Full-sample estimate(s), shape ``(k,)`` or scalar.
        replicates: Replicate estimates, shape ``(G, k)`` or ``(G,)`` for a scalar estimate.
        factor: ``(n_h - 1) / n_h``; 6/7 for 2017, 99/100 for 2009, 98/99 for 2001.
        n_replicates: Expected number of replicates (98 in 2017, 100 in 2009, 99 in 2001).

    Returns:
        Variance with shape ``(k,)`` (0-d array for a scalar estimate).
    """
    theta = np.asarray(full, dtype=np.float64)
    reps = np.asarray(replicates, dtype=np.float64)
    if reps.shape[0] != n_replicates:
        raise ValueError(f"expected {n_replicates} replicates, got {reps.shape[0]}")
    return np.asarray(factor * np.sum((reps - theta) ** 2, axis=0))
