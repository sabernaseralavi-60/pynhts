# pynhts

Typed, survey-weight-aware Python access to US National Household Travel Survey (NHTS)
microdata. Phase 1 covers the **2017** wave.

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

Command line: `pynhts fetch --replicates`, `pynhts register <folder-with-your-CSVs>`,
`pynhts info`, `pynhts validate`.

## Where the data live

Raw CSV and Parquet files go to `$PYNHTS_CACHE_DIR` or the user cache directory. They are
never part of the package or of the git repository. Files you already have can be adopted
with `pynhts register`, after their hashes are checked. After conversion the raw CSVs can be
deleted: the Parquet files are enough.

## Pages

* [Validation against published tables](validation.md): what reproduces and what does not.
* [Methods](methods.md): weights, jackknife variance, margins of error.
* [Data notes](data_notes.md): the NHTS 2017 pitfalls found while building the library.
* [Roadmap](roadmap.md)
