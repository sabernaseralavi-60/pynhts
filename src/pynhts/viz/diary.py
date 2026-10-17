"""The 24-hour activity diary: share of the population in each activity state, minute by minute.

The diary day runs from 04:00 to 03:59 (the NHTS travel day), 1,440 minutes. For every person-day
the minutes are split into **in transit** (from a trip's start to its end time) and the activity
that precedes or follows: before the first trip the origin purpose of that trip, after each trip
its destination purpose. Each person-day carries its full-sample person weight (``WTPERFIN``), so
the curves estimate the share of the *population* (not of the trips) in each state.

Assumptions, all explicit:

* Persons of ``persons`` without any trip stay in ``no_trip_state`` ("Home") all day; pass
  ``None`` to leave them out instead.
* A person-day with an unreadable start or end time is left out of numerator *and* denominator
  (count in ``profile.attrs["n_dropped"]``).
* If trip times overlap or run backwards, boundaries are made non-decreasing (a cumulative
  maximum), so every person always accounts for exactly 1,440 minutes.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from pynhts.tours import TourResult

if TYPE_CHECKING:
    from matplotlib.figure import Figure

PK = ["HOUSEID", "PERSONID"]
DAY_MINUTES = 1440
TRANSIT = "In transit"
OTHER = "Other"

# Stack order, bottom to top. "Other" also receives every unlisted or invalid purpose code.
DEFAULT_GROUPS: dict[str, tuple[str, ...]] = {
    "Home": ("01", "02"),
    "Work": ("03", "04"),
    "School": ("08", "09"),
    "Shopping and services": ("11", "12", "13", "14"),
    "Social and recreation": ("15", "16", "17", "19"),
    OTHER: ("05", "06", "10", "18", "97"),
    TRANSIT: ("07",),  # "change type of transportation" is travel, not an activity
}
# Okabe-Ito based (colour-blind safe); Home is a recessive neutral, transit the strongest hue.
COLORS = {
    "Home": "#D9D9D9", "Work": "#0072B2", "School": "#56B4E9",
    "Shopping and services": "#E69F00", "Social and recreation": "#009E73",
    OTHER: "#CC79A7", TRANSIT: "#D55E00",
}


def _state_order(groups: Mapping[str, Sequence[str]]) -> list[str]:
    order = [s for s in groups if s not in (OTHER, TRANSIT)]
    return [*order, OTHER, TRANSIT]


def _code_to_state(groups: Mapping[str, Sequence[str]]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for state, codes in groups.items():
        for code in codes:
            if code in mapping:
                raise ValueError(f"purpose code {code!r} is listed in two groups")
            mapping[code] = TRANSIT if state == TRANSIT else state
    return mapping


def _clock_minutes(series: pd.Series) -> pd.Series:
    """HHMM text or number to minutes after midnight; NaN where unreadable."""
    v = pd.to_numeric(series, errors="coerce").astype("Float64").astype("float64")
    ok = (v >= 0) & (v <= 2359) & ((v % 100) < 60)
    out: pd.Series = pd.Series(
        np.where(ok, (v // 100) * 60 + (v % 100), np.nan), index=series.index)
    return out


def activity_profile(
    trips: pd.DataFrame | TourResult,
    persons: pd.DataFrame,
    by: str | None = None,
    *,
    weight: str = "WTPERFIN",
    groups: Mapping[str, Sequence[str]] | None = None,
    no_trip_state: str | None = "Home",
    day_start: int = 4,
) -> pd.DataFrame:
    """Weighted share of persons in each activity state at every minute of the diary day.

    Args:
        trips: Trips with ``HOUSEID``, ``PERSONID``, ``TDTRPNUM``, ``WHYFROM``, ``WHYTO``,
            ``STRTTIME`` and ``ENDTIME`` (or a :class:`~pynhts.tours.TourResult`; its trips are
            used). Load the purposes with ``missing="keep"``.
        persons: The population of the diary: ``HOUSEID``, ``PERSONID``, the ``weight`` column
            and, if given, ``by``. Persons not listed here are ignored, so a filtered ``persons``
            table selects the group (e.g. transit users).
        by: Optional person column; one profile per value.
        weight: Person-day weight column in ``persons``.
        groups: ``state -> purpose codes`` in stack order (default :data:`DEFAULT_GROUPS`).
        no_trip_state: State of persons without trips (``None`` leaves them out).
        day_start: Hour at which the diary day begins (NHTS: 4).

    Returns:
        A tidy frame with ``[by,] minute`` (0 = ``day_start``:00) and one column per state; each
        row sums to 1. ``attrs`` holds ``population`` (weighted persons per group, a Series) and
        ``n_dropped`` (persons left out for unreadable times).
    """
    df = trips.trips if isinstance(trips, TourResult) else trips
    need = [*PK, "TDTRPNUM", "WHYFROM", "WHYTO", "STRTTIME", "ENDTIME"]
    absent = [c for c in need if c not in df.columns]
    if absent:
        raise ValueError(f"trips lack required columns: {absent}")
    pcols = [*PK, weight, *([by] if by else [])]
    absent = [c for c in pcols if c not in persons.columns]
    if absent:
        raise ValueError(f"persons lack required columns: {absent}")
    if persons.duplicated(PK).any():
        raise ValueError("persons must have one row per HOUSEID/PERSONID")

    grp = dict(DEFAULT_GROUPS if groups is None else groups)
    states = _state_order(grp)
    state_ix = {s: i for i, s in enumerate(states)}
    if no_trip_state is not None and no_trip_state not in state_ix:
        raise ValueError(f"no_trip_state {no_trip_state!r} is not one of {states}")
    to_state = _code_to_state(grp)

    pop = persons[pcols].dropna(subset=[weight, *([by] if by else [])]).copy()
    pop["_g"], labels = pd.factorize(pop[by], sort=True) if by else (0, pd.Index([None]))
    n_groups = len(labels)

    t = df[need].merge(pop[[*PK, "_g"]], on=PK, how="inner")
    t["_seq"] = pd.to_numeric(t["TDTRPNUM"], errors="coerce")
    t = t.sort_values([*PK, "_seq"], kind="stable").reset_index(drop=True)
    s_raw, e_raw = _clock_minutes(t["STRTTIME"]), _clock_minutes(t["ENDTIME"])
    bad = (s_raw.isna() | e_raw.isna() | t["_seq"].isna()).groupby([t["HOUSEID"], t["PERSONID"]])
    bad_person = bad.transform("any")
    dropped = t.loc[bad_person, PK].drop_duplicates()
    t = t[~bad_person].reset_index(drop=True)
    s_raw, e_raw = s_raw[~bad_person].reset_index(drop=True), e_raw[~bad_person].reset_index(
        drop=True)

    pid = t.groupby(PK, sort=False).ngroup().to_numpy()
    first = np.r_[True, pid[1:] != pid[:-1]] if len(t) else np.array([], dtype=bool)
    last = np.r_[pid[1:] != pid[:-1], True] if len(t) else np.array([], dtype=bool)
    def day(x: pd.Series) -> NDArray[np.float64]:
        return np.asarray((x - day_start * 60) % DAY_MINUTES, dtype=np.float64)

    flat = np.column_stack([day(s_raw), day(e_raw)]).reshape(-1)
    bounds = np.asarray(
        pd.Series(flat).groupby(np.repeat(pid, 2)).cummax(), dtype=np.float64).reshape(-1, 2)
    start, end = bounds[:, 0], bounds[:, 1]
    prev_end = np.r_[0.0, end[:-1]]
    prev_end[first] = 0.0

    def state_of(col: str) -> NDArray[np.int64]:
        s = t[col].astype("string").map(to_state).fillna(OTHER)
        return np.asarray(s.map(state_ix).to_numpy(), dtype=np.int64)

    from_s, to_s = state_of("WHYFROM"), state_of("WHYTO")
    prev_to = np.r_[0, to_s[:-1]]
    pre_state = np.where(first, from_s, prev_to)
    group = t["_g"].to_numpy(dtype=np.int64)
    wmap = pop.set_index(PK)[weight]
    w = wmap.reindex(pd.MultiIndex.from_frame(t[PK])).to_numpy(dtype=np.float64)

    seg_start = np.concatenate([prev_end, start, end[last]])
    seg_end = np.concatenate([start, end, np.full(int(last.sum()), float(DAY_MINUTES))])
    seg_state = np.concatenate(
        [pre_state, np.full(len(t), state_ix[TRANSIT]), to_s[last]])
    seg_group = np.concatenate([group, group, group[last]])
    seg_w = np.concatenate([w, w, w[last]])

    n_s, width = len(states), DAY_MINUTES + 1
    size = n_groups * n_s * width

    def acc(pos: NDArray[np.float64], weights: NDArray[np.float64]) -> NDArray[np.float64]:
        flat = (seg_group * n_s + seg_state) * width + pos.astype(np.int64)
        return np.asarray(np.bincount(flat, weights=weights, minlength=size), dtype=np.float64)

    diff = acc(seg_start, seg_w) - acc(seg_end, seg_w)
    occ = np.cumsum(diff.reshape(n_groups, n_s, width), axis=2)[:, :, :DAY_MINUTES]

    # persons without any trip
    traveller = t[PK].drop_duplicates()
    no_trip = pop.merge(traveller.assign(_t=1), on=PK, how="left")
    no_trip = no_trip[no_trip["_t"].isna()]
    if len(dropped):
        no_trip = no_trip.merge(dropped.assign(_d=1), on=PK, how="left")
        no_trip = no_trip[no_trip["_d"].isna()]
    pop_w = np.zeros(n_groups)
    in_scope = pop.merge(dropped.assign(_d=1), on=PK, how="left")
    in_scope = in_scope[in_scope["_d"].isna()]
    if no_trip_state is None:
        in_scope = in_scope.merge(traveller.assign(_t=1), on=PK, how="inner")
    else:
        extra = no_trip.groupby("_g")[weight].sum()
        for g, val in zip(extra.index.to_numpy(), extra.to_numpy(), strict=True):
            occ[int(g), state_ix[no_trip_state], :] += float(val)
    totals = in_scope.groupby("_g")[weight].sum()
    for g, val in zip(totals.index.to_numpy(), totals.to_numpy(), strict=True):
        pop_w[int(g)] = float(val)

    with np.errstate(divide="ignore", invalid="ignore"):
        share = occ / pop_w[:, None, None]
    frames = []
    for g in range(n_groups):
        f = pd.DataFrame(share[g].T, columns=states)
        f.insert(0, "minute", np.arange(DAY_MINUTES))
        if by:
            f.insert(0, by, labels[g])
        frames.append(f)
    out: pd.DataFrame = pd.concat(frames, ignore_index=True)
    out.attrs["population"] = pd.Series(pop_w, index=labels, name="weighted persons")
    out.attrs["n_dropped"] = len(dropped)
    out.attrs["day_start"] = day_start
    out.attrs["by"] = by
    return out


def _clock_label(minute: float, day_start: int) -> str:
    return f"{int((minute + day_start * 60) // 60) % 24:02d}:00"


def plot_profile(
    profile: pd.DataFrame,
    *,
    title: str | None = None,
    ncols: int = 2,
    colors: Mapping[str, str] | None = None,
    figsize: tuple[float, float] | None = None,
    savepath: str | Path | Sequence[str | Path] | None = None,
    dpi: int = 300,
) -> Figure:
    """Stacked-area chart of an :func:`activity_profile` (one panel per ``by`` value).

    Args:
        profile: Output of :func:`activity_profile`.
        title: Figure title.
        ncols: Panels per row when ``by`` was used.
        colors: ``state -> colour`` overrides of :data:`COLORS`.
        figsize: Figure size in inches (default: 7.2 wide, as a two-column journal figure).
        savepath: File(s) to save (e.g. ``["fig1.png", "fig1.pdf"]``) at ``dpi``.
        dpi: Resolution of raster output.

    Returns:
        The matplotlib figure.
    """
    import matplotlib.pyplot as plt

    by: str | None = profile.attrs.get("by")
    day_start = int(profile.attrs.get("day_start", 4))
    states = [c for c in profile.columns if c not in ("minute", by)]
    palette = {**COLORS, **(colors or {})}
    parts: list[tuple[Any, pd.DataFrame]] = (
        list(profile.groupby(by, sort=False)) if by else [(None, profile)]
    )
    ncols = min(ncols, len(parts)) if by else 1
    nrows = -(-len(parts) // ncols)
    fig, axes = plt.subplots(
        nrows, ncols, sharex=True, sharey=True, squeeze=False,
        figsize=figsize or (7.2, (3.2 if not by else 2.6) * nrows + 0.9),
    )
    pops = profile.attrs.get("population")
    x = np.arange(DAY_MINUTES) / 60.0 + day_start
    for ax, (name, part) in zip(axes.ravel(), parts, strict=False):
        ys = [100.0 * part[s].to_numpy() for s in states]
        ax.stackplot(x, ys, labels=states, colors=[palette.get(s, "#888888") for s in states],
                     edgecolor="white", linewidth=0.3)
        ax.set_xlim(day_start, day_start + 24)
        ax.set_ylim(0, 100)
        ticks = np.arange(day_start, day_start + 25, 4)
        ax.set_xticks(ticks, [_clock_label(float((t - day_start) * 60), day_start) for t in ticks])
        ax.tick_params(labelsize=8)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        if by:
            n = f" (weighted persons: {pops[name]:,.0f})" if pops is not None else ""
            ax.set_title(f"{name}{n}", fontsize=9, loc="left")
    for ax in axes.ravel()[len(parts):]:
        ax.set_visible(False)
    for ax in axes[:, 0]:
        ax.set_ylabel("Persons in state (%)", fontsize=9)
    for ax in axes[-1]:
        ax.set_xlabel("Time of day", fontsize=9)
    handles, labels = axes.ravel()[0].get_legend_handles_labels()
    fig.legend(handles[::-1], labels[::-1], loc="center left", bbox_to_anchor=(0.995, 0.5),
               fontsize=8, frameon=False, title="Activity", title_fontsize=9)
    if title:
        fig.suptitle(title, fontsize=10, x=0.01, ha="left")
    fig.tight_layout()
    if savepath is not None:
        paths = [savepath] if isinstance(savepath, (str, Path)) else list(savepath)
        for p in paths:
            fig.savefig(p, dpi=dpi, bbox_inches="tight")
    return fig


def plot_activity_diary(
    trips: pd.DataFrame | TourResult,
    persons: pd.DataFrame,
    by: str | None = None,
    *,
    weight: str = "WTPERFIN",
    groups: Mapping[str, Sequence[str]] | None = None,
    no_trip_state: str | None = "Home",
    **plot_options: Any,
) -> Figure:
    """Compute :func:`activity_profile` and draw it with :func:`plot_profile`.

    ``plot_options`` are the keyword arguments of :func:`plot_profile` (``title``, ``savepath``...).
    """
    profile = activity_profile(
        trips, persons, by, weight=weight, groups=groups, no_trip_state=no_trip_state)
    return plot_profile(profile, **plot_options)
