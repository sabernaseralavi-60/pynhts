"""Say what the study needs; get the analysis data, the sample flow, a Table 1 and the figures.

A research project states its aim and a handful of exact assumptions: which survey wave and table, who is in the
sample (and in which order people are removed), how each variable is built, whether the statistics are weighted. This
module takes those statements as a :class:`Study`, builds the analysis frame with pynhts only, and returns a
:class:`StudyResult` that carries the frame, the **sample-flow table** (how many records each rule removed), a
**descriptive table** (mean, sd, min, max, share per variable, optionally per group with the difference), the
assumptions that were stated, a methods paragraph, and figures. Nothing is chosen silently: the skip code ``-1`` ("does
not apply") and the non-answer codes (-7, -8, -9) are different things, and every rule says which one it means.

>>> from pynhts import study as S                                           # doctest: +SKIP
>>> from pynhts.aggregate import Where                                      # doctest: +SKIP
>>> spec = S.Study(                                                         # doctest: +SKIP
...     title="Ridesharing in 35 states", aim="Who uses ridesharing?", wave=2017, unit="person",
...     steps=[S.Keep("answered the ridesharing question", Where("RIDESHARE", ">=", 0)),
...            S.Complete("complete key variables", ["R_AGE", "EDUC"])],
...     variables=[S.Var("rides", "RIDESHARE", "count", role="outcome"),
...                S.Var("female", Where("R_SEX", "==", "02"), "binary", label="Female"),
...                S.Var("age", "R_AGE", "number")],
...     weight=None)
>>> res = spec.run(data)                                                    # doctest: +SKIP
>>> res.flow, res.table(), res.report()                                     # doctest: +SKIP

The same study can be written as a dictionary or YAML file (:meth:`Study.from_dict`, :meth:`Study.from_yaml`) so that
an analyst or an agent states the assumptions as data. :func:`compare` grades a result against the numbers a paper
printed (EXACT, CLOSE, ACCEPTABLE or GAP) without tuning anything.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import numpy as np
import pandas as pd

from pynhts.aggregate import Cond, Where
from pynhts.core.validity import ANSWERED, answer_status, valid

if TYPE_CHECKING:
    from pynhts.core.data import NHTSData

Kind = Literal["number", "binary", "count", "category"]
KINDS = ("number", "binary", "count", "category")
Skip = Literal["invalid", "ok"]
Source = str | Cond | Callable[[pd.DataFrame], "pd.Series[Any]"]


# ---- steps ---------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Keep:
    """Keep the rows that satisfy ``cond`` (a population or an eligibility rule)."""

    label: str
    cond: Cond


@dataclass(frozen=True)
class Drop:
    """Remove the rows that satisfy ``cond`` (an exclusion rule)."""

    label: str
    cond: Cond


@dataclass(frozen=True)
class Complete:
    """Remove the rows with a missing value in any of ``columns``.

    A raw NHTS column is missing when it is a non-answer (-7, -8, -9) or blank; the skip code ``-1`` is missing too
    unless ``skip="ok"`` (the question did not apply, e.g. time to work of a non-worker, and that is not a gap in
    the data). A name that is a :class:`Var` of the study is missing when its value is NaN.
    """

    label: str
    columns: Sequence[str]
    skip: Skip = "invalid"


Step = Keep | Drop | Complete


# ---- variables -----------------------------------------------------------------------------------
@dataclass(frozen=True)
class Var:
    """One analysis variable.

    Args:
        name: Column name in the result frame (must not equal a raw NHTS column name).
        source: A raw column (numbers are read as numbers, codes stay codes), a :class:`pynhts.aggregate.Cond`
            (a 0/1 dummy), or a function of the raw frame that returns a Series.
        kind: ``"number"`` (mean, sd, min, max), ``"count"`` (a number that also reports the share of zeros),
            ``"binary"`` (a 0/1 value; its mean is a share) or ``"category"`` (one row per code).
        label: Text for tables and figures.
        role: ``"outcome"`` marks the variable whose distribution gets a figure; ``"group"`` is not needed here.
        needs: Raw columns a function ``source`` reads (the study loads them).
        na: For a condition source: ``"nan"`` (default) makes the dummy missing when a column the condition reads is
            a skip or non-answer; ``"false"`` evaluates the condition as it is (not satisfied = 0).
        note: A sentence for the assumption register (why the variable is built this way).
    """

    name: str
    source: Any
    kind: Kind = "number"
    label: str | None = None
    role: str | None = None
    needs: Sequence[str] = ()
    na: Literal["nan", "false"] = "nan"
    note: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}")
        if self.na not in ("nan", "false"):
            raise ValueError("na must be 'nan' or 'false'")

    def columns(self) -> tuple[str, ...]:
        """Raw columns the variable reads."""
        if isinstance(self.source, str):
            return (self.source,)
        if isinstance(self.source, Cond):
            return tuple(self.source.columns)
        return tuple(self.needs)

    def build(self, frame: pd.DataFrame) -> pd.Series:
        """The variable's values on ``frame`` (NaN where it is missing)."""
        src = self.source
        if isinstance(src, str):
            s = frame[src]
            if self.kind == "category":
                return s.astype("string").where(valid(s))
            x = pd.to_numeric(s, errors="coerce")
            return x.where(x >= 0) if self.kind != "binary" else x
        if isinstance(src, Cond):
            hit = src.mask(frame).astype(float)
            if self.na == "nan":
                ok = pd.Series(True, index=frame.index)
                for c in src.columns:
                    ok &= valid(frame[c])
                hit = hit.where(ok)
            return hit
        out = src(frame)
        return pd.Series(out, index=frame.index)


@dataclass
class StudyResult:
    """What :meth:`Study.run` returns."""

    study: Study
    data: pd.DataFrame
    flow: pd.DataFrame
    weight: str | None
    meta: dict[str, Any]
    assumptions: list[str]
    labels: dict[str, dict[str, str]] = field(default_factory=dict)

    # ---- descriptive table --------------------------------------------------------------------
    def table(self, by: str | None = None) -> pd.DataFrame:
        """Descriptive statistics, one row per variable (per level for a category), per group when ``by`` is set.

        Columns: ``variable``, ``label``, ``level``, ``n`` (non-missing records), ``mean``, ``sd``, ``min``, ``max``,
        ``share_pct`` (binary and category) and ``zero_pct`` (count). Weighted when the study has a weight; the
        unweighted ``sd`` is the sample standard deviation (n - 1), the weighted one is the frequency-weight-free
        weighted standard deviation of :func:`pynhts.eda.weighted_mean_sd`.
        """
        if by is None:
            return self._stats(self.data, None)
        if by not in self.data.columns:
            raise KeyError(f"{by!r} is not a variable of the study")
        parts = []
        for g, sub in self.data.groupby(by, observed=True, dropna=True):
            parts.append(self._stats(sub, _group_name(by, g)))
        out = pd.concat(parts, ignore_index=True)
        return out

    def _stats(self, frame: pd.DataFrame, group: str | None) -> pd.DataFrame:
        from pynhts.eda import weighted_mean_sd

        w = frame[self.weight] if self.weight else None
        rows: list[dict[str, Any]] = []
        for v in self.study.variables:
            x = frame[v.name]
            label = v.label or v.name
            if v.kind == "category":
                known = x.notna()
                ww = w[known] if w is not None else pd.Series(1.0, index=x[known].index)
                tot = float(ww.sum())
                for lev in sorted(x[known].unique()):
                    hit = float(ww[x[known] == lev].sum())
                    rows.append({"variable": v.name, "label": label, "level": self._level(v, lev),
                                 "n": int((x == lev).sum()), "share_pct": hit / tot * 100 if tot else np.nan})
                continue
            xv = pd.to_numeric(x, errors="coerce")
            known = xv.notna()
            xk = xv[known]
            if w is None:
                m = float(xk.mean()) if len(xk) else np.nan
                sd = float(xk.std(ddof=1)) if len(xk) > 1 else np.nan
            else:
                m, sd = weighted_mean_sd(xk, w[known])
            row = {"variable": v.name, "label": label, "level": "", "n": int(known.sum()), "mean": m, "sd": sd,
                   "min": float(xk.min()) if len(xk) else np.nan, "max": float(xk.max()) if len(xk) else np.nan}
            if v.kind == "binary":
                row["share_pct"] = m * 100
            if v.kind == "count":
                ww = w[known] if w is not None else pd.Series(1.0, index=xk.index)
                row["zero_pct"] = float(ww[xk == 0].sum() / ww.sum() * 100) if len(xk) else np.nan
            rows.append(row)
        t = pd.DataFrame(rows)
        if group is not None:
            t.insert(0, "group", group)
        return t

    def _level(self, v: Var, code: str) -> str:
        lab = self.labels.get(v.name, {}).get(code)
        return f"{code} {lab}" if lab else str(code)

    def count_distribution(
        self, name: str, bands: Sequence[tuple[int, int | None]] = ((1, 1), (2, 2), (3, 5), (6, 10), (11, 20), (21, None))
    ) -> pd.DataFrame:
        """Zeros against users, and how the users (value above zero) spread over bands of the count.

        Zero-inflated count outcomes (uses in the last 30 days) are reported this way in the literature: the share of
        zeros, then the share of users with 1, 2, 3-5, ... uses. ``bands`` are inclusive ``(low, high)`` pairs;
        ``high=None`` is open-ended. Weighted when the study is. Columns: ``band``, ``n``, ``share_of_users_pct`` and,
        on the first two rows, ``share_of_all_pct``.
        """
        x = pd.to_numeric(self.data[name], errors="coerce")
        ok = x.notna()
        w = self.data[self.weight][ok] if self.weight else pd.Series(1.0, index=x[ok].index)
        xv = x[ok]
        tot = float(w.sum())
        users = xv > 0
        utot = float(w[users].sum())
        rows = [{"band": "0 (non-users)", "n": int((xv == 0).sum()), "share_of_all_pct": float(w[xv == 0].sum()) / tot * 100},
                {"band": ">= 1 (users)", "n": int(users.sum()), "share_of_all_pct": utot / tot * 100}]
        for lo, hi in bands:
            m = users & (xv >= lo) & (xv <= hi if hi is not None else True)
            lab = f"{lo}" if hi == lo else f"{lo}+" if hi is None else f"{lo}-{hi}"
            rows.append({"band": lab, "n": int(m.sum()), "share_of_users_pct": float(w[m].sum()) / utot * 100 if utot else np.nan})
        return pd.DataFrame(rows)

    def difference(self, by: str, a: str, b: str) -> pd.DataFrame:
        """Mean (or share) of group ``a`` minus group ``b`` for every number, count and binary variable."""
        t = self.table(by=by)
        t = t[t["level"] == ""]
        ta = t[t["group"] == a].set_index("variable")
        tb = t[t["group"] == b].set_index("variable")
        out = pd.DataFrame({"mean_a": ta["mean"], "mean_b": tb["mean"]})
        out["difference"] = out["mean_a"] - out["mean_b"]
        out.index.name = "variable"
        return out.reset_index()

    # ---- text ---------------------------------------------------------------------------------
    def methods(self) -> str:
        """A methods paragraph stating data, sample rules and weighting."""
        m = self.meta
        wtxt = (f"estimates are weighted with {self.weight}" if self.weight
                else "statistics are unweighted (no survey weight was applied; they describe the sample, not the population)")
        first, last = int(self.flow["n_after"].iloc[0]), int(self.flow["n_after"].iloc[-1])
        steps = self.flow.iloc[1:].to_dict("records")
        rules = "; ".join(f"{r['rule']} ({int(r['n_removed']):,} removed)" for r in steps
                          if r["n_removed"]) or "no records were removed"
        return (f"We used the {m['wave']} National Household Travel Survey {m['table']} file ({first:,} records). "
                f"Sample: {rules}, leaving {last:,} records. {wtxt[0].upper() + wtxt[1:]}. "
                f"Analysis variables were built with pynhts {m['version']}.")

    def report(self, by: str | None = None) -> str:
        """The study as a Markdown report: aim, data, sample flow, descriptive table, assumptions."""
        s = self.study
        out = [f"# {s.title}", ""]
        if s.aim:
            out += ["## Aim", s.aim, ""]
        out += ["## Data and sample", self.methods(), "", "### Sample flow", _md(self.flow), ""]
        t = self.table(by=by)
        out += ["### Descriptive statistics" + (f" by {by}" if by else ""), _md(_round(t)), ""]
        if by is not None:
            groups = list(t["group"].unique())
            if len(groups) == 2:
                out += [f"### Difference ({groups[0]} minus {groups[1]})", _md(_round(self.difference(by, *groups))), ""]
        out += ["## Assumptions", *(f"- {x}" for x in self.assumptions), ""]
        return "\n".join(out)

    # ---- figures ------------------------------------------------------------------------------
    def figures(self, by: str | None = None) -> dict[str, Any]:
        """Figures (needs the optional ``matplotlib``): ``flow``, one ``dist_<name>`` per outcome, ``groups`` with ``by``."""
        from pynhts.viz import plots

        figs: dict[str, Any] = {}
        plt = plots._plt()
        fig, ax = plt.subplots(figsize=(6.5, 0.45 * len(self.flow) + 1.2))
        ax.barh(self.flow["rule"][::-1], self.flow["n_after"][::-1], color="#0072B2")
        for i, v in enumerate(self.flow["n_after"][::-1]):
            ax.text(v, i, f" {int(v):,}", va="center", fontsize=8)
        ax.set_xlabel("records remaining")
        ax.set_title("Sample flow")
        fig.tight_layout()
        figs["flow"] = fig
        w = self.data[self.weight] if self.weight else None
        for v in self.study.variables:
            if v.role == "outcome" and v.kind in ("number", "count"):
                x = pd.to_numeric(self.data[v.name], errors="coerce")
                ok = x.notna()
                ax2 = plots.histogram(x[ok], weight=None if w is None else w[ok], xlabel=v.label or v.name,
                                      title=f"Distribution of {v.label or v.name}")
                if v.kind == "count":
                    zero = float(((x[ok] == 0) * (w[ok] if w is not None else 1.0)).sum() / (w[ok].sum() if w is not None else ok.sum()))
                    ax2.text(0.97, 0.93, f"zero: {zero * 100:.1f} %", transform=ax2.transAxes, ha="right", va="top", fontsize=9)
                figs[f"dist_{v.name}"] = ax2.figure
        if by is not None:
            t = self.table(by=by)
            t = t[t["share_pct"].notna() & (t["variable"] != by)]
            if len(t):
                piv = t.assign(item=t["label"] + t["level"].map(lambda x: f": {x}" if x else "")).pivot_table(
                    index="item", columns="group", values="share_pct", sort=False)
                fig3, ax3 = plt.subplots(figsize=(6.5, 0.3 * len(piv) + 1.4))
                piv.plot.barh(ax=ax3)
                ax3.invert_yaxis()
                ax3.set_xlabel("share, %")
                ax3.set_title(f"Shares by {by}")
                fig3.tight_layout()
                figs["groups"] = fig3
        return figs

    def save(self, directory: str | Path, by: str | None = None, figures: bool = True) -> list[Path]:
        """Write ``report.md``, ``table1.csv``, ``flow.csv`` and (with matplotlib) the figures; returns the paths."""
        d = Path(directory)
        d.mkdir(parents=True, exist_ok=True)
        written = []
        (d / "report.md").write_text(self.report(by=by), encoding="utf-8")
        written.append(d / "report.md")
        self.table(by=by).to_csv(d / "table1.csv", index=False)
        written.append(d / "table1.csv")
        self.flow.to_csv(d / "flow.csv", index=False)
        written.append(d / "flow.csv")
        if figures:
            try:
                figs = self.figures(by=by)
            except ImportError:
                figs = {}
            for name, fig in figs.items():
                p = d / f"{name}.png"
                fig.savefig(p, dpi=150, bbox_inches="tight")
                written.append(p)
        return written


@dataclass
class Study:
    """The research question and its exact assumptions.

    Args:
        title: Name of the study.
        aim: The research purpose in words (printed in the report).
        wave: Survey year (2001, 2009, 2017 or 2022).
        unit: Table whose rows are the units of analysis: ``"person"``, ``"household"``, ``"trip"`` or ``"vehicle"``.
        steps: Sample rules applied in this order (:class:`Keep`, :class:`Drop`, :class:`Complete`).
        variables: Analysis variables (:class:`Var`).
        weight: ``"auto"`` uses the table's survey weight, ``None`` is explicitly unweighted (what many papers did),
            or a weight column name.
        assumptions: Free-text decisions that are not visible in the rules (for the register).
    """

    title: str
    wave: int
    unit: str
    variables: Sequence[Var]
    steps: Sequence[Step] = ()
    aim: str = ""
    weight: str | None = "auto"
    assumptions: Sequence[str] = ()

    # ---- running ------------------------------------------------------------------------------
    def required_columns(self) -> list[str]:
        """Raw columns the study reads."""
        names = {v.name for v in self.variables}
        cols: list[str] = []
        for st in self.steps:
            if isinstance(st, Complete):
                cols += [c for c in st.columns if c not in names]
            else:
                cols += list(st.cond.columns)
        for v in self.variables:
            cols += list(v.columns())
        return list(dict.fromkeys(cols))

    def run(self, data: NHTSData) -> StudyResult:
        """Build the analysis frame and the result."""
        import pynhts

        if int(data.wave) != int(self.wave):
            raise ValueError(f"the study is for NHTS {self.wave} but the data are NHTS {data.wave}")
        taken = {v.name for v in self.variables}
        if len(taken) != len(self.variables):
            raise ValueError("variable names must be unique")
        raw = data.table(self.unit, self.required_columns(), missing="keep", skip="keep", keys=True)
        clash = taken & set(raw.columns)
        if clash:
            raise ValueError(f"variable names {sorted(clash)} equal raw NHTS columns; rename them")
        wcol = raw.attrs.get("pynhts", {}).get("weight")
        if self.weight == "auto":
            weight = wcol
        else:
            weight = self.weight
            if weight is not None and weight not in raw.columns:
                raw = data.table(self.unit, [*self.required_columns(), weight], missing="keep", skip="keep", keys=True)
        work = raw.copy()
        for v in self.variables:
            work[v.name] = v.build(raw)
        flow = [{"rule": f"{self.unit} records in the {self.wave} file", "n_before": len(work), "n_removed": 0,
                 "n_after": len(work)}]
        for st in self.steps:
            before = len(work)
            work = work[_step_mask(st, work, taken)]
            flow.append({"rule": st.label, "n_before": before, "n_removed": before - len(work), "n_after": len(work)})
        keep = [c for c in ("HOUSEID", "PERSONID", "VEHID", "TDTRPNUM") if c in work.columns]
        cols = [*keep, *[v.name for v in self.variables]] + ([weight] if weight and weight in work.columns else [])
        out = work[cols].reset_index(drop=True)
        out.attrs["pynhts"] = {"wave": self.wave, "table": self.unit, "weight": weight}
        labels = _labels(data, self.unit, self.variables)
        notes = list(self.assumptions) + [f"{v.name}: {v.note}" for v in self.variables if v.note]
        notes.append("weighted with " + weight if weight else "statistics are unweighted (weight=None)")
        notes.append("skip code -1 and non-answer codes -7/-8/-9 are never read as quantities; "
                     "a step or variable says where a skip counts as an answer")
        meta = {"wave": self.wave, "table": self.unit, "version": pynhts.__version__}
        return StudyResult(self, out, pd.DataFrame(flow), weight, meta, notes, labels)

    # ---- declarative form ---------------------------------------------------------------------
    @classmethod
    def from_dict(cls, spec: Mapping[str, Any]) -> Study:
        """Build a study from plain data (what a YAML file holds).

        Conditions are ``{"column": "HHSTATE", "op": "in", "value": ["CA", "TX"]}`` (the operators of
        :class:`pynhts.aggregate.Where`), or ``{"all": [cond, ...]}`` / ``{"any": [cond, ...]}``. Variables are
        ``{"name": "age", "source": "R_AGE", "kind": "number"}``, ``{"name": "female", "where": cond, "kind": "binary"}``
        or ``{"name": "lndens", "source": "HBPPOPDN", "transform": "log"}``.
        """
        steps: list[Step] = []
        for s in spec.get("steps", []):
            if "complete" in s:
                steps.append(Complete(s["label"], list(s["complete"]), s.get("skip", "invalid")))
            elif "keep" in s:
                steps.append(Keep(s["label"], _cond(s["keep"])))
            elif "drop" in s:
                steps.append(Drop(s["label"], _cond(s["drop"])))
            else:
                raise ValueError(f"a step needs one of keep, drop, complete: {s}")
        vs = []
        for v in spec.get("variables", []):
            src: Any
            if "where" in v:
                src = _cond(v["where"])
            elif v.get("transform") == "log":
                col = v["source"]
                src = _log_of(col)
            elif v.get("transform") in (None, "none"):
                src = v["source"]
            else:
                raise ValueError(f"unknown transform {v.get('transform')!r}")
            needs = (v["source"],) if v.get("transform") == "log" else ()
            vs.append(Var(v["name"], src, v.get("kind", "number"), v.get("label"), v.get("role"), needs,
                          v.get("na", "nan"), v.get("note")))
        return cls(title=spec.get("title", "Study"), wave=int(spec["wave"]), unit=spec["unit"], variables=vs,
                   steps=steps, aim=spec.get("aim", ""), weight=spec.get("weight", "auto"),
                   assumptions=list(spec.get("assumptions", [])))

    @classmethod
    def from_yaml(cls, path: str | Path) -> Study:
        """Read a study from a YAML file (see :meth:`from_dict`)."""
        import yaml

        return cls.from_dict(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


# ---- helpers -------------------------------------------------------------------------------------
def _group_name(by: str, g: Any) -> str:
    """``user=1`` for a 0/1 variable, the value itself otherwise."""
    if isinstance(g, float) and float(g).is_integer():
        return f"{by}={int(g)}"
    return str(g)


def _log_of(col: str) -> Callable[[pd.DataFrame], pd.Series]:
    def f(frame: pd.DataFrame) -> pd.Series:
        x = pd.to_numeric(frame[col], errors="coerce").astype("float64")
        return pd.Series(np.log(x.where(x > 0)), index=frame.index)

    return f


def _cond(d: Mapping[str, Any]) -> Cond:
    if "all" in d or "any" in d:
        key = "all" if "all" in d else "any"
        parts = [_cond(x) for x in d[key]]
        out = parts[0]
        for p in parts[1:]:
            out = (out & p) if key == "all" else (out | p)
        return out
    return Where(d["column"], d["op"], d.get("value"))


def _step_mask(step: Step, work: pd.DataFrame, names: set[str]) -> pd.Series:
    if isinstance(step, Keep):
        return step.cond.mask(work).fillna(False).astype(bool)
    if isinstance(step, Drop):
        return ~step.cond.mask(work).fillna(False).astype(bool)
    ok = pd.Series(True, index=work.index)
    for c in step.columns:
        if c in names:
            ok &= work[c].notna()
        elif step.skip == "ok":
            ok &= answer_status(work[c]).isin([ANSWERED, "skip"])
        else:
            ok &= valid(work[c])
    return ok


def _labels(data: NHTSData, table: str, variables: Sequence[Var]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    try:
        cols = data.schema(table).columns
    except Exception:  # noqa: BLE001 - labels are a courtesy; the study must not fail without them
        return out
    for v in variables:
        if v.kind == "category" and isinstance(v.source, str) and v.source in cols:
            out[v.name] = {c.code: c.label for c in cols[v.source].codes}
    return out


def _round(t: pd.DataFrame) -> pd.DataFrame:
    return t.round(3)


def _md(t: pd.DataFrame) -> str:
    cols = [str(c) for c in t.columns]
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join("---" for _ in cols) + " |"]
    for row in t.itertuples(index=False):
        cells = ["" if (isinstance(x, float) and np.isnan(x)) else f"{x:,}" if isinstance(x, int) else str(x) for x in row]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


# ---- comparison with published numbers ---------------------------------------------------------------
def grade(published: float, ours: float) -> str:
    """``EXACT`` when ours prints the same at the printed precision, ``CLOSE`` within 2 %, ``ACCEPTABLE`` within 5 %, else ``GAP``.

    The precision is that of the printed number (``5.0`` is one decimal, ``5`` none); rounding is half-up, like a
    printed table, not the banker's rounding of Python's ``round``.
    """
    if published is None or ours is None or ours != ours or published != published:
        return "NOT_COMPUTED"
    dec = max(0, -Decimal(str(published)).as_tuple().exponent)  # type: ignore[operator]
    shown = Decimal(str(float(ours))).quantize(Decimal(1).scaleb(-dec), rounding=ROUND_HALF_UP)
    if shown == Decimal(str(published)):
        return "EXACT"
    if published == 0:
        return "GAP"
    rel = abs(ours - published) / abs(published)
    return "CLOSE" if rel <= 0.02 else "ACCEPTABLE" if rel <= 0.05 else "GAP"


def compare(result: StudyResult, published: pd.DataFrame | Sequence[Mapping[str, Any]], by: str | None = None) -> pd.DataFrame:
    """Grade what a paper printed against the study's own numbers; nothing is adjusted to match.

    ``published`` has the columns ``variable``, ``stat`` (``mean``, ``sd``, ``min``, ``max``, ``n``, ``share_pct`` or
    ``zero_pct``), ``value`` and optionally ``level`` and ``group`` (when ``by`` is given). The rows ``n_records`` with
    the stat ``n`` and the variable ``"sample"`` compare the final sample size.
    """
    pub = pd.DataFrame(published)
    t = result.table(by=by)
    rows = []
    for d in pub.to_dict("records"):
        if d["variable"] == "sample":
            ours = float(len(result.data))
        else:
            sel = t[t["variable"] == d["variable"]]
            if d.get("level") not in (None, "") and not (isinstance(d.get("level"), float) and np.isnan(d["level"])):
                sel = sel[sel["level"].astype(str).str.startswith(str(d["level"]))]
            if by is not None and d.get("group") is not None:
                sel = sel[sel["group"] == str(d["group"])]
            ours = float(sel.iloc[0][d["stat"]]) if len(sel) and d["stat"] in sel.columns else float("nan")
        row: dict[str, Any] = {"variable": d["variable"], "stat": d["stat"]}
        for key in ("level", "group"):
            if key in d:
                row[key] = d[key]
        row.update({"published": d["value"], "pynhts": ours, "status": grade(d["value"], ours)})
        rows.append(row)
    return pd.DataFrame(rows)


__all__ = ["Complete", "Drop", "Keep", "Study", "StudyResult", "Var", "compare", "grade"]
