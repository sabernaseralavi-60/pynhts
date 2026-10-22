"""P19 - Sadeghvaziri & Tawfik (2020), ASCE ICTD: elderly travel patterns, NHTS 2017 and 2009.

The paper prints bar charts only (no numbers): weekly walk, bike and transit counts of persons 65+ by race and income, for
households of one against two or more persons. So this audit can test the DIRECTION of the printed statements, not
magnitudes: "if the elderly person lives alone he/she has more walk trips; this holds among all races in 2017, and in 2009
for all races except Whites and Asians". Weighted means, person weight, persons 65+, race of the household respondent
mapped with harmonize.apply_column (the 2009 file has no person-level race).
"""

from __future__ import annotations

import pandas as pd

import common

common.setup()
import pynhts  # noqa: E402
from pynhts import harmonize  # noqa: E402

a = common.Audit("p19_sadeghvaziri2020")
RACES = ["white", "black", "asian", "aian", "nhpi", "multiple", "other"]
out = {}
for wave in (2009, 2017):
    d = pynhts.load(wave)
    p = d.persons(["R_AGE", "HHSIZE", "HH_RACE", "NWALKTRP", "NBIKETRP"], missing="nan", skip="auto")
    p["race"] = harmonize.apply_column(p, "HH_RACE", "race_household")
    age = pd.to_numeric(p["R_AGE"])
    s = p[(age >= 65) & pd.to_numeric(p["NWALKTRP"]).ge(0)].copy()
    s["alone"] = pd.to_numeric(s["HHSIZE"]) == 1
    s["walk"] = pd.to_numeric(s["NWALKTRP"])
    a.info(f"{wave}: persons 65+ with a walk count", len(s), f"alone: {int(s['alone'].sum())}")

    def wmean(g: pd.DataFrame) -> float:
        return float((g["walk"] * g["WTPERFIN"]).sum() / g["WTPERFIN"].sum())

    for race in RACES:
        g = s[s["race"] == race]
        if g["alone"].nunique() < 2:
            continue
        alone, others = wmean(g[g["alone"]]), wmean(g[~g["alone"]])
        out[(wave, race)] = (alone, others, len(g))
        a.info(f"{wave} {race}: weekly walk trips, alone / with others", f"{alone:.2f} / {others:.2f}  (n = {len(g)})", "")

# the printed statements, as 1 = lives-alone mean is higher
for race in RACES:
    if (2017, race) in out:
        al, ot, n = out[(2017, race)]
        a.check(f"2017 {race}: alone > with others (1 = yes)", 1, float(al > ot), "paper: 'among all races'")
for race in ("black", "other"):
    if (2009, race) in out:
        al, ot, n = out[(2009, race)]
        a.check(f"2009 {race}: alone > with others (1 = yes)", 1, float(al > ot), "paper: all races except Whites and Asians")
for race in ("white", "asian"):
    if (2009, race) in out:
        al, ot, n = out[(2009, race)]
        a.check(f"2009 {race}: alone > with others (0 = no)", 0, float(al > ot), "paper: the exception in 2009")
a.rows.append({"item": "magnitudes of Figures 2-6", "published": None, "pynhts": None, "status": "NOT_COMPUTABLE",
               "note": "bar charts without printed values; the walk question is 'past week' in both waves (NWALKTRP)"})
a.save()
