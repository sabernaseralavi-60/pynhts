# pynhts

Typed, survey-weight-aware Python access to US National Household Travel Survey (NHTS)
microdata. Four waves are supported: **2001**, **2009**, **2017** and **2022** (NextGen).

## Install

```
pip install pynhts
```

## Five-minute tour

```python
import pynhts

data = pynhts.load(2017)           # downloads, verifies (SHA-256) and converts on first use

# 1. Lazy, validated tables; columns are joined from the table that owns them
trips = data.trips(["TRPMILES", "TRPTRANS", "HHFAMINC", "R_AGE"])

# 2. Correct weighted statistics with margins of error (jackknife, 98 replicate weights)
s = data.survey("person", ["R_AGE_IMP", "DRIVER"])
s.total(domain=s.rows["DRIVER"] == "01")        # 223,277 thousand drivers, MOE 827 thousand

t = data.survey("trip", ["TRPMILES"])
t.mean("TRPMILES")                              # 10.70 miles, MOE 0.40

# 3. Replicate published tables and see every gap
from pynhts import recipes
print(recipes.to_markdown(recipes.run("stt2017", data)))

# 4. Hand data to machine-learning code
from pynhts import ml
arr = ml.to_arrays(trips, ["TRPMILES", "R_AGE"], target="TRPTRANS", weight="WTTRDFIN")
```

```python
# 2022 has no replicate weights: Taylor-series errors (strata + households), same interface
d22 = pynhts.load(2022)
d22.survey("household", ["HHSIZE"]).mean("HHSIZE")          # 2.44 persons, SE 0.022, df 7873

# the two waves use different codes: compare and harmonize them explicitly
from pynhts import harmonize
harmonize.compare_waves()                                    # 253 names in one wave only, 47 with changed codes
trips = d22.trips(["TRPTRANS"], missing="keep")
trips["mode"] = harmonize.apply(trips["TRPTRANS"], "mode", wave=2022)

pynhts.dictionary(2022)                                      # every variable, owner table, type, codes
```

Command line: `pynhts fetch [--wave 2022] [--replicates]`, `pynhts docs --wave 2022`,
`pynhts register <folder-with-your-CSVs>`, `pynhts info`, `pynhts validate [stt2017|ug2022|...]`.

## Where the data live

Raw CSV and Parquet files go to `$PYNHTS_CACHE_DIR` or the user cache directory. They are
never part of the package or of the git repository. Files you already have can be adopted
with `pynhts register`, after their hashes are checked. After conversion the raw CSVs can be
deleted: the Parquet files are enough.

## Pages

* [Validation against published tables](validation.md): what reproduces and what does not.
* [Comparing waves](waves.md): the four waves, code crosswalks, what cannot be compared.
* [Methods](methods.md): weights, jackknife and Taylor-series variance, margins of error.
* [Data notes](data_notes.md): the NHTS 2017, 2022, 2009 and 2001 pitfalls found while building the library.
* [Roadmap](roadmap.md)
