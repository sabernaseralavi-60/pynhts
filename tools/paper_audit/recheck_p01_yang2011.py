"""Re-check of P01 (Yang, Diez Roux, Bingham 2011) with `pynhts.study` (0.8.0 rules) and the race crosswalk.

The first audit (p01_yang2011.py) built the 130,222-person sample by hand with the single household-respondent race code
(HHR_RACE 01/02/03/06). Here the same sample is stated as a `Study` (the rules read a masked view of the file, a refused age
is no longer "under 18") and three readings of race are compared on the sample size, the Table 1 race shares and the race
odds ratios of Table 2: (a) the paper's recovered reading, (b) `harmonize.race_ethnicity()`, (c) race group first with
Hispanic origin overriding White/Black/Asian only (the rule recovered from the P10 tables). Nothing is tuned.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

import common

common.setup()
import pynhts  # noqa: E402
from pynhts import harmonize  # noqa: E402
from pynhts import study as S  # noqa: E402
from pynhts.aggregate import Where  # noqa: E402

warnings.simplefilter("ignore")
a = common.Audit("recheck_p01_yang2011")
d = pynhts.load(2001)
w = "WTPERFIN"


def race_a(v: pd.DataFrame) -> pd.Series:
    """Recovered reading: the single race code of the household respondent; 06 = Hispanic/Mexican only; others excluded."""
    return v["HHR_RACE"].map({"01": "White", "02": "Black", "03": "Asian", "06": "Hispanic"})


def race_b(v: pd.DataFrame) -> pd.Series:
    """harmonize.race_ethnicity(): non-Hispanic White/Black/Asian and Hispanic of any race; the rest (and unknown) excluded."""
    re = harmonize.race_ethnicity(v)
    return re.map({"nh_white": "White", "nh_black": "Black", "nh_asian": "Asian", "hispanic": "Hispanic"})


def race_c(v: pd.DataFrame) -> pd.Series:
    """Race group first; Hispanic origin overrides White, Black, Asian and unknown race only (other groups stay out)."""
    cw = harmonize.apply_column(v, "HHR_RACE", "race_household")
    hisp = harmonize.apply_column(v, "HHR_HISP", "hispanic_household")
    grp = cw.map({"white": "White", "black": "Black", "asian": "Asian"})
    return grp.mask(hisp.eq("hispanic").fillna(False) & (cw.isin(["white", "black", "asian"]) | cw.isna()), "Hispanic")


def spec(race_fn, name: str) -> S.Study:
    return S.Study(
        title=f"Yang 2011 sample, race reading {name}", wave=2001, unit="person", weight="auto",
        steps=[S.Keep("age 5 or older (0-4 and not-ascertained ages out)", Where("R_AGE", ">=", 5)),
               S.Complete("household income, sex and urbanization answered", ["HHFAMINC", "R_SEX", "HBHUR"]),
               S.Complete("race group of the paper (others excluded)", ["race"])],
        variables=[S.Var("age", "R_AGE", "number"), S.Var("sex", "R_SEX", "category"),
                   S.Var("income_code", "HHINCTTL", "number"), S.Var("region", "CENSUS_R", "category"),
                   S.Var("urb", "HBHUR", "category"), S.Var("tdate", "TDAYDATE", "category"),
                   S.Var("race", race_fn, "category", needs=["HHR_RACE", "HHR_HISP"])])


results = {k: spec(fn, k).run(d) for k, fn in (("a", race_a), ("b", race_b), ("c", race_c))}
for k, res in results.items():
    print(f"--- reading {k}: sample flow")
    print(res.flow.to_string(index=False))

# trip outcomes per person (as in p01): walk 26 / bicycle 25
t = d.trips(["TRPTRANS"], missing="keep", skip="keep")
t["active"] = t["TRPTRANS"].isin(["25", "26"])
per = t.groupby(["HOUSEID", "PERSONID"]).agg(ntrips=("active", "size"), nact=("active", "sum")).reset_index()

T1_RACE_ALL = {"White": 77.3, "Black": 12.9, "Asian": 2.5, "Hispanic": 7.3}
T2_OR = {"18-64": {"Black": 0.88, "Asian": 0.82, "Hispanic": 0.83}, "11-17": {"Black": 1.50}}
for k, res in results.items():
    s = res.data.copy()
    s = s[s["age"] >= 5]
    note = {"a": "recovered reading (HHR_RACE 01/02/03/06)", "b": "race_ethnicity()", "c": "race first, Hispanic overrides White/Black/Asian"}[k]
    a.check(f"[{k}] analysis sample (persons)", 130222, len(s), note + "; sample stated as a Study")
    sh = s.groupby("race")[w].sum() / s[w].sum() * 100
    for g, pub in T1_RACE_ALL.items():
        a.check(f"[{k}] T1 race={g} % (All)", pub, float(sh.get(g, np.nan)), note)
    s["grp"] = pd.cut(s["age"], bins=[5, 11, 18, 65, 200], right=False, labels=["5-10", "11-17", "18-64", "65+"])
    s = s.merge(per, on=["HOUSEID", "PERSONID"], how="left")
    s[["ntrips", "nact"]] = s[["ntrips", "nact"]].fillna(0)
    s["pat"] = (s["nact"] > 0).astype(float)
    inc = s["income_code"]
    s["income"] = np.select([inc <= 4, inc <= 8, inc <= 16], ["<20k", "20-40k", "40-80k"], default=">80k")
    s["region"] = s["region"].map({"1": "Northeast", "2": "Midwest", "3": "South", "4": "West"})
    s["urb"] = s["urb"].map({"R": "Rural", "T": "Town", "S": "Suburban", "C": "Second city", "U": "Urban"})
    s["month"] = pd.to_numeric(s["tdate"].astype(str).str[4:6])
    for g, terms in T2_OR.items():
        sub = s[s["grp"] == g]
        X = pd.DataFrame(index=sub.index)
        X["female"] = sub["sex"].ne("1").astype(float)
        for c in ("Black", "Asian", "Hispanic"):
            X["race_" + c] = (sub["race"] == c).astype(float)
        for c in ("20-40k", "40-80k", ">80k"):
            X["inc_" + c] = (sub["income"] == c).astype(float)
        for c in ("Midwest", "South", "West"):
            X["reg_" + c] = (sub["region"] == c).astype(float)
        for c in ("Town", "Suburban", "Second city", "Urban"):
            X["urb_" + c] = (sub["urb"] == c).astype(float)
        for m in range(2, 13):
            X[f"m{m}"] = (sub["month"] == m).astype(float)
        X = X.loc[:, X.std() > 0]
        b = common.wlogit(X.values, sub["pat"].values, sub[w].values)
        orr = dict(zip(X.columns, np.exp(b[1:])))
        for c, pub in terms.items():
            a.check(f"[{k}] T2 OR race_{c}, {g}", pub, float(orr.get("race_" + c, np.nan)), note)
        a.check(f"[{k}] T2 sample n, {g}", {"18-64": 84712, "11-17": 13651}[g], len(sub), note)

df = a.save()
for k in results:
    m = df["item"].str.startswith(f"[{k}]")
    print(k, df[m]["status"].value_counts().to_dict())
