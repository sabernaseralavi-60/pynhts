"""Re-check of P02 (Zhou & Wang 2014) with `pynhts.study` (0.8.0 rules).

P02 uses no race variable (Table 2 has income, education, work status, internet use, urban), so the race crosswalk does not
apply; what 0.8.0 changes is how the sample is stated and how a skip or refusal is read. The first audit could not recover
the "invalid records" rule (106,211 persons vs 85,663). The paper's own Table 2 gives the clue: the minimum of `cnttdtr`
(trips on the travel day) is 2, i.e. the final file holds persons with at least two trips. The sample is rebuilt as a
Study whose flow table shows every rule, with that rule added and graded; no other rule is tuned.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

import common

common.setup()
import pynhts  # noqa: E402
from pynhts import study as S  # noqa: E402
from pynhts.aggregate import Where  # noqa: E402

warnings.simplefilter("ignore")
a = common.Audit("recheck_p02_zhou_wang2014")
d = pynhts.load(2009)


def make(min_trips: int) -> S.Study:
    return S.Study(
        title=f"Zhou & Wang 2014 sample, at least {min_trips} trip(s)", wave=2009, unit="person", weight=None,
        steps=[S.Keep("aged 18 or older", Where("R_AGE", ">=", 18)),
               S.Keep(f"at least {min_trips} trip(s) on the travel day", Where("CNTTDTR", ">=", min_trips)),
               S.Complete("work status, internet purchases, internet use, education, income, urban answered",
                          ["WKFTPT", "PURCHASE", "WEBUSE", "EDUC", "HHFAMINC", "HBHUR", "URBAN"])],
        variables=[S.Var("age", "R_AGE", "number"), S.Var("purchase", "PURCHASE", "count"),
                   S.Var("trips", "CNTTDTR", "count"), S.Var("hhsize", "HHSIZE", "number"),
                   S.Var("vehicles", "HHVEHCNT", "number"), S.Var("renters", "HBHTNRNT", "number"),
                   S.Var("webuse1", Where("WEBUSE", "==", "01"), "binary"), S.Var("webuse2", Where("WEBUSE", "==", "02"), "binary"),
                   S.Var("income_lt50", Where("HHFAMINC", "in", [f"{i:02d}" for i in range(1, 11)]), "binary"),
                   S.Var("educ_hs", Where("EDUC", "in", ["01", "02"]), "binary"),
                   S.Var("educ_bachelor", Where("EDUC", "==", "04"), "binary"),
                   S.Var("educ_college", Where("EDUC", "in", ["03", "04"]), "binary",
                         note="some college or associate's degree (03) plus bachelor's degree (04); the paper calls its educ2 'bachelor's degree'"),
                   S.Var("fulltime", Where("WKFTPT", "==", "01"), "binary"),
                   S.Var("urban", Where("URBAN", "==", "01"), "binary"),
                   S.Var("female", Where("R_SEX", "==", "02"), "binary")])


one, two = make(1).run(d), make(2).run(d)
print("--- at least 1 trip (the first audit's reading)")
print(one.flow.to_string(index=False))
print("--- at least 2 trips (Table 2: min cnttdtr = 2)")
print(two.flow.to_string(index=False))
a.check("final sample, at least 1 trip (first audit's rule)", 85663, len(one.data), "Study; replaces the hand-written rule, same sample as p02")
a.check("final sample, at least 2 trips (Table 2 min of cnttdtr = 2)", 85663, len(two.data),
        "rule read from the paper's Table 2, not tuned to the count")

T2 = {  # column of the Study result: published mean (Table 2)
    "age": 47.85, "purchase": 2.277, "trips": 4.844, "hhsize": 2.909, "vehicles": 2.593, "renters": 22.44,
    "webuse1": 0.815, "webuse2": 0.117, "income_lt50": 0.224, "educ_hs": 0.202, "educ_bachelor": 0.576, "educ_college": 0.576,
    "fulltime": 0.807, "urban": 0.629, "female": 0.468,
}
for label, res in (("1+ trips", one), ("2+ trips", two)):
    for v, pub in T2.items():
        a.check(f"T2 mean {v} [{label}]", pub, float(res.data[v].mean()))
# Table 3: the final dataset against the original person file (percentages)
for label, res in (("1+ trips", one), ("2+ trips", two)):
    for v, pub in (("female", 46.8), ("income_lt50", 22.4), ("webuse1", 81.5), ("educ_bachelor", 57.6), ("educ_college", 57.6)):
        a.check(f"T3 final dataset % {v} [{label}]", pub, float(res.data[v].mean() * 100))

# ---- hypotheses for the 20,548 persons that remain unexplained: invalid TRIPS (a missing value in a trip variable of Table 2)
trips = d.trips(["DWELTIME", "TRVL_MIN", "STRTTIME", "TRPTRANS", "WHYTRP1S", "TRPMILES"], missing="keep", skip="keep")
keys = ["HOUSEID", "PERSONID"]
for col in ("TRVL_MIN", "STRTTIME", "TRPTRANS", "WHYTRP1S", "TRPMILES"):
    bad = trips.loc[pd.to_numeric(trips[col], errors="coerce") < 0, keys].drop_duplicates()
    left = one.data.merge(bad, on=keys, how="left", indicator=True)
    a.info(f"persons left if no trip has a missing/skip {col}", int((left["_merge"] == "left_only").sum()),
           "hypothesis only; the published count is 85,663")
a.info("DWELTIME is -9 for the last trip of every person's day, so 'no missing dwell time' leaves", 0,
       "dwell time can only be a sum over the trips that have one; the rule cannot be 'every trip valid'")
edu = one.data.merge(d.persons(["EDUC"], missing="keep", skip="keep")[[*keys, "EDUC"]], on=keys)["EDUC"].value_counts(normalize=True).round(3)
a.info("education shares in the rebuilt sample (01 < high school, 02 high school, 03 some college, 04 bachelor, 05 graduate)",
       str(edu.to_dict()), "the paper prints 57.6 % 'bachelor's degree' (educ2): codes 03 + 04 together give 57.3 %, code 04 alone 27.4 %, so the paper's label is wider than the codebook's")

# ---- "travel day is weekend" (Table 2 tdwknd = 0.298): the NHTS flag TDWKND also covers part of Friday; Saturday + Sunday is TRAVDAY 7 or 1
days = d.trips(["TDWKND", "TRAVDAY"], missing="keep", skip="keep")
per_day = days.groupby(keys).agg(flag=("TDWKND", lambda x: x.astype("string").str.lstrip("0").eq("1").any()),
                                 satsun=("TRAVDAY", lambda x: x.astype("string").str.lstrip("0").isin(["1", "7"]).any())).reset_index()
for label, res in (("1+ trips", one),):
    z = res.data.merge(per_day, on=keys, how="left")
    a.check(f"T2 mean tdwknd, TDWKND flag [{label}]", 0.298, float(z["flag"].mean()), "the NHTS weekend flag (Friday evening is weekend)")
    a.check(f"T2 mean tdwknd, Saturday + Sunday by TRAVDAY [{label}]", 0.298, float(z["satsun"].mean()), "reading that reproduces Lidbe's Table 4 weekend cells (P10)")

df = a.save()
for label in ("1+ trips", "2+ trips"):
    print(label, df[df["item"].str.contains(label, regex=False)]["status"].value_counts().to_dict())
