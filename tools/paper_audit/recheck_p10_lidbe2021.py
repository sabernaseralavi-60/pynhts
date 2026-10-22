"""Re-check of P10 (Lidbe et al. 2021) with the 0.8.0 medical-condition and race crosswalks.

The first audit (p10_lidbe2021.py) counted every person who did not answer "yes" to MEDCOND as "no medical
condition", including the persons the question never reached (the skip -1: ages 0-15 in 2001) and the
non-answers (-7/-8/-9). pynhts 0.8.0 maps those to missing in ``harmonize.apply_column(..., "medical_condition")``.
Here Table 3 is rebuilt with the base the summarizeNHTS tool uses (trips of persons who gave a valid answer) and
Table 4 (trip counts of the older population by trip type, medical condition and person/household characteristics,
incl. the six "what the condition does to travel" items and race) is checked cell by cell.
Nothing is tuned: each convention is stated, computed and graded; variants are reported side by side.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

import common

common.setup()
import pynhts  # noqa: E402
from pynhts import harmonize  # noqa: E402

warnings.simplefilter("ignore")
a = common.Audit("recheck_p10_lidbe2021")
waves = {2001: pynhts.load(2001), 2017: pynhts.load(2017)}
RACE = {2001: "HHR_RACE", 2017: "HH_RACE"}
HISP = {2001: "HHR_HISP", 2017: "HH_HISP"}
TIME = {2001: "TRVLCMIN", 2017: "TRVLCMIN"}  # calculated minutes (TRVL_MIN, the reported one, gives a different split)
COND_ITEMS = {"CONDNIGH": "Limit to daytime driving", "CONDRIDE": "Ask others for rides",
              "CONDPUB": "Bus or subway less frequently", "CONDRIVE": "Give up driving",
              "CONDSPEC": "Use special transportation services", "CONDTRAV": "Reduced day-to-day travel"}


def build(wave: int) -> pd.DataFrame:
    """One row per trip with the person's age, medical condition (crosswalk), condition items, race, and distance class."""
    d = waves[wave]
    per = d.persons(["R_AGE", "MEDCOND", "R_SEX", "HHVEHCNT", "DRVRCNT", RACE[wave], HISP[wave], *COND_ITEMS],
                    missing="keep", skip="keep")
    per["age"] = pd.to_numeric(per["R_AGE"]).where(lambda x: x >= 0)
    per["med"] = harmonize.apply_column(per, "MEDCOND", "medical_condition")
    for c in COND_ITEMS:
        per[c + "_x"] = harmonize.apply_column(per, c, "condition_effect")
    per["sex"] = pd.to_numeric(per["R_SEX"]).map({1: "Male", 2: "Female"})
    per["veh"] = pd.to_numeric(per["HHVEHCNT"]).where(lambda x: x >= 0).clip(upper=4)
    per["drv"] = pd.to_numeric(per["DRVRCNT"]).where(lambda x: x >= 0).clip(upper=4)
    # race, two readings of the household respondent's answer (the paper does not say which it used)
    cw = harmonize.apply_column(per, RACE[wave], "race_household")
    hisp = harmonize.apply_column(per, HISP[wave], "hispanic_household")
    re = harmonize.race_ethnicity(per)
    per["race_v2"] = re.map({"nh_white": "White", "nh_black": "African American", "nh_asian": "Asian",
                             "hispanic": "Hispanic"}).fillna("Other").mask(re.isna(), pd.NA)
    # v3: race group first; Hispanic origin = yes overrides only White, Black, Asian and unknown race (a Hispanic person
    # who gave another race stays "Other"); unknown origin keeps the race group. Recovered from the paper's 2001 and 2017 cells.
    named = cw.isin(["white", "black", "asian"]) | cw.isna()
    v3 = cw.map({"white": "White", "black": "African American", "asian": "Asian"}).fillna("Other").mask(cw.isna(), pd.NA)
    per["race_v3"] = v3.mask(hisp.eq("hispanic").fillna(False) & named, "Hispanic")
    tr = d.trips(["TRPMILES", "TDWKND", "TRAVDAY", TIME[wave]], missing="nan", skip="auto")
    keep = ["HOUSEID", "PERSONID", "age", "med", "sex", "veh", "drv", "race_v2", "race_v3", *[c + "_x" for c in COND_ITEMS]]
    m = tr.merge(per[keep], on=["HOUSEID", "PERSONID"], how="left")
    m["dist"] = pd.Series(np.where(m["TRPMILES"] >= 50, "long", "short"), index=m.index).where(m["TRPMILES"].notna())
    m["minutes"] = pd.to_numeric(m[TIME[wave]])
    m["weekend"] = m["TRAVDAY"].astype("string").str.lstrip("0").isin(["1", "7"])  # Sunday or Saturday
    m["weekend_flag"] = m["TDWKND"].astype("string").str.lstrip("0").eq("1")  # NHTS flag: also part of Friday
    return m


frames = {w: build(w) for w in waves}

# ---- Table 3: % of trips by age, medical condition and distance. With/Without columns: trips of persons with a valid MEDCOND answer
T3 = {  # (older, long, medical) -> published; medical: True / False / None (overall column)
    2001: {(False, None, True): 3.76, (False, None, False): 83.71, (False, None, None): 89.94,
           (False, False, True): 3.63, (False, False, False): 81.39, (False, False, None): 87.64,
           (False, True, True): 0.10, (False, True, False): 2.32, (False, True, None): 2.28,
           (True, None, True): 1.73, (True, None, False): 10.80, (True, None, None): 10.06,
           (True, False, True): 1.68, (True, False, False): 10.58, (True, False, None): 9.85,
           (True, True, True): 0.03, (True, True, False): 0.26, (True, True, None): 0.23},
    2017: {(False, None, True): 3.61, (False, None, False): 81.48, (False, None, None): 85.08,
           (False, False, True): 3.55, (False, False, False): 79.45, (False, False, None): 83.00,
           (False, True, True): 0.05, (False, True, False): 2.03, (False, True, None): 2.09,
           (True, None, True): 2.30, (True, None, False): 12.62, (True, None, None): 14.92,
           (True, False, True): 2.27, (True, False, False): 12.30, (True, False, None): 14.57,
           (True, True, True): 0.03, (True, True, False): 0.31, (True, True, None): 0.34},
}
TOT = {2001: (5.49, 94.51), 2017: (5.90, 94.10)}
for wave, m in frames.items():
    w = m["WTTRDFIN"]
    valid_med = m["med"].notna()
    base_valid, base_all = w[valid_med].sum(), w.sum()
    a.info(f"{wave}: share of trips by persons with a valid MEDCOND answer (%)", round(base_valid / base_all * 100, 3),
           "the rest are persons the question did not reach (skip -1: ages 0-15 in 2001) and non-answers")
    for (old, lg, med), pub in T3[wave].items():
        sel = (m["age"] >= 65).fillna(False) == old  # unknown age is "non-older": the paper's overall columns add to 100
        if lg is not None:
            sel &= m["dist"] == ("long" if lg else "short")
        if med is None:
            val = w[sel].sum() / base_all * 100
            basis = "all trips"
        else:
            sel &= m["med"].eq("yes" if med else "no")
            val = w[sel].sum() / base_valid * 100
            basis = "trips of persons with a valid answer"
        name = f"T3 {wave} {'older' if old else 'non-older'} {'all' if lg is None else ('long' if lg else 'short')} " \
               f"{'overall' if med is None else ('with' if med else 'without')} condition (%)"
        a.check(name, pub, float(val), basis)
    yes = w[m["med"].eq("yes")].sum() / base_valid * 100
    a.check(f"T3 {wave} total with medical condition (%)", TOT[wave][0], float(yes), "base: valid answers")
    a.check(f"T3 {wave} total without medical condition (%)", TOT[wave][1], float(100 - yes), "base: valid answers")
    a.info(f"T3 {wave} with medical condition, base = ALL trips (the first audit's convention)",
           round(w[m["med"].eq("yes")].sum() / base_all * 100, 3), "counts the skip as 'no': understates the share in 2001")

# ---- Table 4: trips (millions, annual) of persons aged 65+, by distance (short, long) and medical condition (with, without)
# cell order: 2001 short-with, short-without, long-with, long-without, then the same for 2017
T4 = {
    ("day", "Weekday"): [4083.9, 24847.2, 74.3, 534.2, 5969.7, 33590.5, 62.7, 777.0],
    ("day", "Weekend"): [1305.2, 9055.3, 31.0, 284.8, 2429.5, 12045.3, 50.2, 387.9],
    ("dur", "< 60 min"): [5243.3, 33021.4, 4.5, 58.5, 7995.2, 43844.0, 9.6, 84.2],
    ("dur", ">= 60 min"): [145.9, 881.0, 100.8, 760.6, 404.1, 1791.8, 103.3, 1080.7],
    ("sex", "Male"): [2126.1, 16619.7, 52.7, 430.6, 3422.2, 21890.1, 59.3, 629.5],
    ("sex", "Female"): [3263.0, 17282.8, 52.6, 388.5, 4977.1, 23712.4, 53.6, 535.3],
    ("race", "White"): [4468.9, 29117.0, 83.0, 744.6, 5397.6, 35111.7, 89.5, 939.7],
    ("race", "African American"): [451.8, 2139.8, 11.3, 29.5, 1233.1, 4198.8, 9.2, 90.6],
    ("race", "Asian"): [24.8, 254.5, 0.0, 5.8, 239.9, 1078.8, 0.9, 15.4],
    ("race", "Hispanic"): [151.6, 867.5, 2.5, 17.7, 855.4, 3277.9, 3.3, 68.9],
    ("race", "Other"): [260.1, 1187.8, 6.2, 16.0, 636.4, 1848.7, 9.8, 48.1],
    ("veh", 0): [561.7, 1146.5, 9.2, 18.9, 1244.7, 2062.9, 1.9, 26.7],
    ("veh", 1): [2552.7, 12573.3, 39.3, 238.8, 3674.9, 16001.9, 44.6, 296.4],
    ("veh", 2): [1643.8, 14533.7, 33.8, 340.4, 2137.1, 17024.1, 31.8, 446.7],
    ("veh", 3): [414.4, 4018.0, 17.2, 183.8, 812.7, 6978.2, 19.1, 283.4],
    ("veh", 4): [216.5, 1631.0, 5.8, 37.1, 529.9, 3568.5, 15.6, 111.7],
    ("drv", 0): [447.3, 852.1, 8.0, 19.9, 918.9, 1557.0, 1.9, 25.2],
    ("drv", 1): [2282.4, 10492.0, 37.9, 217.1, 3663.0, 14704.2, 48.4, 287.6],
    ("drv", 2): [2331.7, 20125.4, 49.3, 537.3, 3135.7, 25143.5, 48.1, 729.2],
    ("drv", 3): [290.4, 2054.2, 9.5, 37.7, 471.0, 3427.2, 10.5, 107.8],
    ("drv", 4): [37.3, 378.8, 0.6, 7.0, 210.6, 803.8, 4.0, 15.1],
}
NA = np.nan  # the printed table has a dash: 2001 asks the condition items only of persons with a condition
T4_COND = {  # item -> {yes/no: 2001 short-with, short-without, long-with, long-without, 2017 same}
    "CONDNIGH": {"yes": [2526.1, NA, 38.9, NA, 2576.8, 1890.9, 41.5, 18.3], "no": [2529.6, NA, 64.5, NA, 5822.5, 4095.9, 71.4, 98.2]},
    "CONDRIDE": {"yes": [2483.2, NA, 48.4, NA, 3199.8, 978.1, 39.5, 12.7], "no": [2905.7, NA, 57.0, NA, 5199.5, 5008.7, 73.4, 103.8]},
    "CONDPUB": {"yes": [713.5, NA, 23.4, NA, 752.3, 220.9, 3.5, 1.5], "no": [4487.1, NA, 78.7, NA, 7647.0, 5765.9, 109.4, 115.1]},
    "CONDRIVE": {"yes": [1040.4, NA, 27.0, NA, 1725.0, 404.1, 16.2, 0.6], "no": [4004.6, NA, 70.1, NA, 6674.3, 5582.7, 96.7, 116.0]},
    "CONDSPEC": {"yes": [437.1, NA, 9.4, NA, 877.4, 132.3, 3.0, 0.3], "no": [4749.9, NA, 91.1, NA, 7521.8, 5854.5, 109.9, 116.3]},
    "CONDTRAV": {"yes": [4138.8, NA, 81.3, NA, 5631.2, 1663.0, 78.2, 22.2], "no": [1244.0, NA, 24.0, NA, 2768.1, 4323.8, 34.7, 94.4]},
}
CELLS = [(2001, "short", "with"), (2001, "short", "without"), (2001, "long", "with"), (2001, "long", "without"),
         (2017, "short", "with"), (2017, "short", "without"), (2017, "long", "with"), (2017, "long", "without")]


def cell(m: pd.DataFrame, group: pd.Series, cat, dist: str, med: str) -> float:
    sel = (m["age"] >= 65) & group.eq(cat).fillna(False) & (m["dist"] == dist) & m["med"].eq("yes" if med == "with" else "no")
    return float(m.loc[sel, "WTTRDFIN"].sum() / 1e6)


def group_of(m: pd.DataFrame, key: str, variant: str) -> pd.Series:
    if key == "day":
        return m["weekend_flag" if variant == "flag" else "weekend"].map({True: "Weekend", False: "Weekday"}).astype("object")
    if key == "dur":  # "60 minutes or more", everything else (an unknown duration included) is "< 60 min"
        return pd.Series(np.where(m["minutes"] >= 60, ">= 60 min", "< 60 min"), index=m.index)
    if key == "sex":
        return m["sex"].astype("object")
    if key == "race":
        return m[f"race_{variant}"].astype("object")
    return m[key]


for (key, cat), pubs in T4.items():
    variants = ("v2", "v3") if key == "race" else (None, "flag") if key == "day" else (None,)
    for variant in variants:
        for pub, (wave, dist, med) in zip(pubs, CELLS, strict=True):
            m = frames[wave]
            val = cell(m, group_of(m, key, variant), cat, dist, med)
            tag = (f" [race reading {variant}]" if key == "race" else " [TDWKND flag]" if variant else "")
            a.check(f"T4 {wave} {key}={cat} {dist}-distance {med} condition (million trips){tag}", pub, val,
                    "trips of persons 65+, annual weight WTTRDFIN / 1e6" + ("; v2 = harmonize.race_ethnicity(), v3 = race group first, Hispanic origin overrides White/Black/Asian/unknown only" if variant else ""))

for item, rows in T4_COND.items():
    for ans, pubs in rows.items():
        for pub, (wave, dist, med) in zip(pubs, CELLS, strict=True):
            if pub != pub:
                continue
            m = frames[wave]
            val = cell(m, m[item + "_x"].astype("object"), ans, dist, med)
            a.check(f"T4 {wave} {item}={ans} {dist}-distance {med} condition (million trips)", pub, val,
                    "condition_effect crosswalk; the item is asked only of persons with a condition (2017 also of everybody 80+)")

df = a.save()
for part, mask in (("T3", df["item"].str.startswith("T3")), ("T4 (all)", df["item"].str.startswith("T4")),
                   ("T4 weekday/weekend by TDWKND", df["item"].str.contains("TDWKND flag")), ("T4 race v3", df["item"].str.contains("race reading v3")), ("T4 race v2", df["item"].str.contains("race reading v2")),
                   ("T4 condition items", df["item"].str.contains("COND"))):
    print(part, df[mask]["status"].value_counts().to_dict())
