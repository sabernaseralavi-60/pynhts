"""Figures for the pilot: |z| per target and model, and the travel-share-by-time curves."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / "paper" / "pilot"
res = pd.read_csv(out / "pilot_results.csv")
order = ["reference_train", "resample_fine", "resample_coarse", "resample_none", "markov_dur", "markov1"]
label = {"reference_train": "split-half reference (noise floor)", "resample_fine": "weighted resample (fine cells)",
         "resample_coarse": "weighted resample (coarse cells)", "resample_none": "weighted resample (no covariates)",
         "markov_dur": "Markov + duration (semi-Markov)", "markov1": "first-order Markov"}
color = {"reference_train": "#888888", "resample_fine": "#1b7837", "resample_coarse": "#5aae61",
         "resample_none": "#a6dba0", "markov_dur": "#d6604d", "markov1": "#b2182b"}

# Fig 1: median |z| across splits, per target
med = res.assign(az=res.z.abs()).groupby(["target", "model"]).az.median().unstack()[order]
med = med.sort_values("markov1")
fig, ax = plt.subplots(figsize=(8, 7))
y = np.arange(len(med))
for m in order:
    ax.scatter(med[m], y, s=28, color=color[m], label=label[m], zorder=3)
ax.axvline(1.96, color="k", ls="--", lw=0.8)
ax.text(2.0, len(med) - 0.6, "|z| = 1.96", fontsize=8)
ax.set_yticks(y, med.index, fontsize=8)
ax.set_xscale("symlog", linthresh=2)
ax.set_xlabel("median |z| over 5 random household splits (error in sampling-error units)")
ax.grid(axis="x", alpha=0.3)
ax.legend(fontsize=7, loc="lower right")
fig.tight_layout()
fig.savefig(out / "fig_abs_z_by_target.png", dpi=200)

# Fig 2: share travelling through the day
prof = pd.read_csv(out / "travel_profile_split0.csv")
hours = 4 + prof.slot * 5 / 60
fig, ax = plt.subplots(figsize=(8, 4))
ax.plot(hours, prof.test, color="k", lw=2, label="held-out survey (weighted)")
for m in ["resample_fine", "markov_dur", "markov1"]:
    ax.plot(hours, prof[m], color=color[m], lw=1.2, label=label[m])
ax.set_xlabel("hour of day (travel day starts 04:00)")
ax.set_ylabel("share of persons travelling")
ax.legend(fontsize=8)
fig.tight_layout()
fig.savefig(out / "fig_travel_profile.png", dpi=200)
print("figures written to", out)
