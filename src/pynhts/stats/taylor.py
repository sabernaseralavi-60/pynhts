"""Taylor-series (linearisation) variance for a stratified, one-stage cluster design.

The 2022 NextGen NHTS ships no replicate weights. Its User Guide (Appendix 1, "Sampling
Errors") says to use the Taylor series method with the analysis weight, the sampling stratum and
the primary sampling unit (HOUSEID). This is the "ultimate cluster" estimator that R's ``survey``
package and Stata's ``svy`` use for ``strata`` + ``ids`` + ``weights``: clusters are sampled with
replacement within strata, so there is no finite-population correction.

For an estimator whose linearised value of unit ``u`` is ``z_u`` (weight included), let
``Z_c`` be the sum of ``z_u`` over the units of cluster ``c`` and ``H`` the number of strata
with ``n_h`` clusters each. Then

    Var = sum_h  n_h / (n_h - 1) * sum_{c in h} (Z_c - mean_h(Z))^2 .

Clusters that hold no unit of a domain have ``Z_c = 0`` and still count in ``n_h``, which is
what makes subpopulation (domain) estimates correct. The degrees of freedom are
``n_clusters - H`` as in R's ``degf``.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def taylor_variance(z: NDArray[np.float64], stratum: NDArray[np.int64]) -> NDArray[np.float64]:
    """Variance of one or several linearised estimators.

    Args:
        z: Cluster sums of the linearised values, shape ``(n_clusters, k)``.
        stratum: Stratum index (``0..H-1``) of every cluster, shape ``(n_clusters,)``.

    Returns:
        Variance of each of the ``k`` estimators.

    Raises:
        ValueError: a stratum has a single cluster (its variance is not estimable; merge the
            stratum with a neighbour yourself rather than have the library guess).
    """
    z2 = np.asarray(z, dtype=np.float64)
    if z2.ndim == 1:
        z2 = z2[:, None]
    h = np.asarray(stratum, dtype=np.int64)
    n_h = np.bincount(h)
    if (n_h < 2).any():
        raise ValueError(f"strata with a single cluster: {np.flatnonzero(n_h < 2).tolist()}")
    scale = n_h / (n_h - 1.0)
    out = np.empty(z2.shape[1])
    for j in range(z2.shape[1]):
        mean = np.bincount(h, weights=z2[:, j]) / n_h
        dev = z2[:, j] - mean[h]
        out[j] = float(scale @ np.bincount(h, weights=dev * dev, minlength=len(n_h)))
    return out
