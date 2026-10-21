# Independent reference for pynhts' Taylor-series estimator (NHTS 2022).
#
# Builds the design the 2022 User Guide prescribes (ids = HOUSEID, strata = STRATUMID, analysis
# weight) with R's `survey` package and writes estimates, standard errors and design degrees of
# freedom to tests/golden/taylor_2022_r.csv. tests/data/test_wave2022.py compares pynhts with it.
#
# Usage:  Rscript tools/validate_taylor_r.R <folder with the 2022 CSVs> <output csv>
# Needs:  R >= 4.4 and the `survey` package (tested with survey 4.4-2 on R 4.5.2).

suppressPackageStartupMessages(library(survey))
options(survey.lonely.psu = "fail")

args <- commandArgs(trailingOnly = TRUE)
src <- args[1]
out <- args[2]

rd <- function(f) read.csv(file.path(src, f), colClasses = "character", check.names = FALSE)
num <- function(d, cols) { for (c in cols) d[[c]] <- as.numeric(d[[c]]); d }

hh <- num(rd("hhv2pub.csv"), c("WTHHFIN", "WTHHFIN5D", "WTHHFIN2D", "HHSIZE", "HHVEHCNT"))
pe <- num(rd("perv2pub.csv"), c("WTPERFIN", "R_AGE"))
tr <- num(rd("tripv2pub.csv"), c("WTTRDFIN", "TRPMILES"))
ve <- num(rd("vehv2pub.csv"), c("WTHHFIN"))

# child files carry a copy of STRATUMID; prove it equals the household file's before using it
strata <- hh[, c("HOUSEID", "STRATUMID")]
for (nm in c("pe", "tr", "ve")) {
  d <- get(nm)
  stopifnot("STRATUMID" %in% names(d))
  chk <- merge(d[, c("HOUSEID", "STRATUMID")], strata, by = "HOUSEID", suffixes = c("", ".hh"))
  stopifnot(nrow(chk) == nrow(d), all(chk$STRATUMID == chk$STRATUMID.hh))
}
hh$one <- 1; pe$one <- 1; tr$one <- 1; ve$one <- 1

des <- function(d, w) svydesign(ids = ~HOUSEID, strata = ~STRATUMID, weights = as.formula(paste0("~", w)),
                                data = d, nest = TRUE)
# Design-correct analysis keeps every sampled household as a cluster, also those with no trip or
# no vehicle row. R drops them when the child file alone is the data, so add one zero-weight
# placeholder row per missing household (it contributes nothing to any estimate). The "observed"
# designs below are what R/SAS give on the child file alone.
full <- function(d, w) {
  miss <- hh[!(hh$HOUSEID %in% d$HOUSEID), c("HOUSEID", "STRATUMID")]
  if (nrow(miss) == 0) return(d)
  ph <- d[rep(1, nrow(miss)), ]
  ph$HOUSEID <- miss$HOUSEID; ph$STRATUMID <- miss$STRATUMID; ph[[w]] <- 0
  rbind(d, ph)
}
dhh <- des(hh, "WTHHFIN"); dhh5 <- des(hh, "WTHHFIN5D")
dpe <- des(pe, "WTPERFIN")

rows <- list()
add <- function(id, est, se, d) {
  rows[[length(rows) + 1]] <<- data.frame(
    id = id, estimate = format(unname(est), digits = 17), se = format(unname(se), digits = 17),
    df = if (is.numeric(d)) d else degf(d), stringsAsFactors = FALSE)
}
one <- function(id, r, d) add(id, coef(r)[1], SE(r)[1], d)

one("hh_total", svytotal(~one, dhh), dhh)
one("hh_mean_size", svymean(~HHSIZE, dhh), dhh)
hh$noveh <- as.numeric(hh$HHVEHCNT == 0); dhh <- des(hh, "WTHHFIN")
one("hh_share_no_vehicle", svymean(~noveh, dhh), dhh)
one("hh_total_weekday_weights", svytotal(~one, dhh5), dhh5)
b <- svyby(~HHSIZE, ~CENSUS_R, dhh, svymean)
# degrees of freedom of a domain estimate: degf of the subpopulation design, as pynhts does
for (i in seq_len(nrow(b))) add(paste0("hh_mean_size_region_", b$CENSUS_R[i]), b$HHSIZE[i], b$se[i],
                                degf(subset(dhh, CENSUS_R == b$CENSUS_R[i])))

pe$worker <- as.numeric(pe$WORKER == "01"); dpe <- des(pe, "WTPERFIN")
one("per_total", svytotal(~one, dpe), dpe)
wk <- subset(dpe, worker == 1)
one("per_workers_total", svytotal(~one, wk), wk)
one("per_share_workers", svymean(~worker, dpe), dpe)
agek <- subset(dpe, R_AGE >= 0)
one("per_mean_age", svymean(~R_AGE, agek), agek)
# sex codes -7/-8/-9 are missing values; pynhts masks them, so the groups are 01 and 02 only
agesex <- subset(dpe, R_AGE >= 0 & R_SEX %in% c("01", "02"))
b <- svyby(~R_AGE, ~R_SEX, agesex, svymean)
for (i in seq_len(nrow(b))) add(paste0("per_mean_age_sex_", b$R_SEX[i]), b$R_AGE[i], b$se[i],
                                degf(subset(agesex, R_SEX == b$R_SEX[i])))

tr$pmt <- ifelse(tr$TRPMILES >= 0, tr$TRPMILES, 0)
tr$walk <- as.numeric(tr$TRPTRANS == "20")
dtr_obs <- des(tr, "WTTRDFIN")
one("trip_total_observed", svytotal(~one, dtr_obs), dtr_obs)
one("trip_share_walk_observed", svymean(~walk, dtr_obs), dtr_obs)
dtr <- des(full(tr, "WTTRDFIN"), "WTTRDFIN")
one("trip_total", svytotal(~one, dtr), dtr)
okm <- subset(dtr, TRPMILES >= 0)   # rows with a valid distance; the 14 trips coded -9 are missing
one("trip_pmt_total", svytotal(~TRPMILES, okm), okm)
one("trip_mean_miles", svymean(~TRPMILES, okm), okm)
one("trip_share_walk", svymean(~walk, dtr), dtr)
wlk <- subset(dtr, walk == 1)
one("trip_total_domain_walk", svytotal(~one, wlk), wlk)

dve_obs <- des(ve, "WTHHFIN")
one("veh_total_observed", svytotal(~one, dve_obs), dve_obs)
dve <- des(full(ve, "WTHHFIN"), "WTHHFIN")
one("veh_total", svytotal(~one, dve), dve)

# Cross-survey ratio (trips per household): stack both tables under one design with PSU = household
st <- rbind(
  data.frame(HOUSEID = tr$HOUSEID, STRATUMID = tr$STRATUMID, w = tr$WTTRDFIN, x = 1, y = 0),
  data.frame(HOUSEID = hh$HOUSEID, STRATUMID = hh$STRATUMID, w = hh$WTHHFIN, x = 0, y = 1))
dst <- svydesign(ids = ~HOUSEID, strata = ~STRATUMID, weights = ~w, data = st, nest = TRUE)
r <- svyratio(~x, ~y, dst)
add("trips_per_household", coef(r)[1], SE(r)[1], dst)

res <- do.call(rbind, rows)
dir.create(dirname(out), showWarnings = FALSE, recursive = TRUE)
write.csv(res, out, row.names = FALSE, quote = FALSE)
cat("survey", as.character(packageVersion("survey")), "R", R.version.string, "\n")
cat("wrote", nrow(res), "rows to", out, "\n")
