---
title: 'pynhts: survey-weight-aware access to US National Household Travel Survey microdata in Python'
tags:
  - Python
  - transportation
  - travel behavior
  - survey methodology
  - replicate weights
  - reproducibility
authors:
  - name: Seyed Saber Naseralavi
    orcid: 0000-0002-5392-910X
    affiliation: 1
    corresponding: true
affiliations:
  - name: Department of Civil Engineering, Shahid Bahonar University of Kerman, Kerman, Iran
    index: 1
date: 17 October 2026
bibliography: paper.bib
---

# Summary

The US National Household Travel Survey (NHTS) is the main public source of household travel
behavior in the United States. Its public-use microdata, released by the Federal Highway
Administration (FHWA), combine four linked tables (households, persons, trips and vehicles) with
sampling weights and 98 jackknife replicate weights. `pynhts` is a Python library that
downloads and verifies the 2017 NHTS files, converts them to typed Parquet, merges the tables
without silent errors, computes weighted statistics with correct replicate-weight standard
errors and margins of error, and reproduces published FHWA tables so that users can see how
closely it matches the official figures. A small bridge exports tables to NumPy arrays, PyTorch
tensors and household graphs.

# Statement of need

Using NHTS microdata correctly requires work that is repeated in every project and is easy to
get wrong. We found the following traps while building the library, and each is covered by an
automated test: the data server returns HTTP 200 with an HTML page for files that do not exist;
categorical codes are strings with leading zeros; four different non-answer codes coexist, one
of which ("appropriate skip") is not missing data; the codebook counts some codes together with
others; child tables carry 107 copies of parent columns, so naive merges duplicate columns or
pick the wrong weight; and the same column name can denote different variables in different
tables. Trip-level estimates need person-day replicate weights that are not shipped as a trip
file. Mistakes here change estimates and, more often, understate their uncertainty.

# State of the field

The R package `summarizeNHTS` [@summarizeNHTS] downloads and summarizes NHTS data in R. The R
`survey` package [@lumley2004] offers general replicate-weight analysis and can be applied
to the NHTS by users who set up the design themselves. To our knowledge, no maintained Python
package provides NHTS access, and general Python survey tooling does not know the NHTS files,
codes or weights. `pynhts` is a new package, and not an extension of an existing one, because
its value lies in the NHTS-specific schema and validation, which a general-purpose library
cannot carry, and because Python is the language of the machine-learning workflows for which
the data are increasingly used.

# Software design

`pynhts` is organized in five modules. `pynhts.io` pins SHA-256 hashes for every official
archive and member, downloads with `pooch` [@uieda2020], supports offline use and the adoption
of files the user already holds, and writes Parquet deterministically and idempotently.
`pynhts.core` derives a typed schema from the official codebook, and its loader reads columns
lazily, joins a requested column from the table that owns it with a validated many-to-one join,
and masks survey codes per column on request. `pynhts.stats` implements the stratified
jackknife used in the 2017 weighting design [@nhts2017weighting]: with 14 variance strata of
7 units the variance is $\frac{6}{7}\sum_{r=1}^{98}(\hat\theta_r-\hat\theta)^2$ [@wolter2007],
and the margin of error is $t_{0.975,98}$ times the standard error. Because all trips of a
person share one weight, trip estimates are computed on person-day units, so 923,572 trips
need only a 264,234 by 98 weight matrix. `pynhts.recipes` encodes published figures with
tolerances and expected statuses, and `pynhts.ml` converts tables to arrays [@harris2020],
tensors and graphs. The data frames are pandas [@mckinney2010].

# Research impact statement

`pynhts` has not yet been released on PyPI and has no third-party users. Its evidence of
correctness is a replication of 24 figures from Tables 1 and 3 of FHWA's *Summary of Travel
Trends: 2017 NHTS* [@mcguckin2018]. Twenty reproduce completely, including the published
margins of error; for two the estimate matches but the margin of error differs (by 6.7 % and
1.4 %); and two do not match (an unexplained gap of the printed total of persons against the
sum of the report's own age bands, and 2.706 against a printed 2.70 vehicle trips per driver).
These gaps are reported in the repository, with no rule changed to hide them. All 3,807
code frequencies of the official codebook, unweighted and weighted, are reproduced exactly.
The package has 76 unit tests that need no data, and 46 further tests that run on the real files.

# AI usage disclosure

During the development of this software and of this paper, the author used Claude (Anthropic)
as an assistant for software design, writing and running code and tests, checking the code
against the official documents and data, and drafting and editing the documentation and the
text. After using this tool, the author reviewed, verified and edited the material (code,
results, references and text) and takes full responsibility for the content. Numbers in this
paper come from the repository's validation report, and the references were checked against
Crossref.

# Acknowledgements

The NHTS is conducted by the US Department of Transportation, Federal Highway Administration,
and distributed by Oak Ridge National Laboratory.

# References
