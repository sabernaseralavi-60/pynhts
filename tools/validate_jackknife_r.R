# Independent reference for pynhts' jackknife estimators (NHTS 2001 and 2009).
#
# Reads the RAW csv files (not pynhts' Parquet), builds replicate-weight designs with R's `survey`
# package and writes estimates, standard errors and degrees of freedom to a csv that
# tests/data/test_old_waves_real.py compares with pynhts. Two variance conventions per wave:
#   fhwa    the multiplier of the User's Guide / published tables (2009: 99/100, 2001: 98/99)
#   design  the textbook multiplier of the replicate method (2009 JK2: 1; 2001 JK1: 98/99)
#
# Usage:  Rscript tools/validate_jackknife_r.R <wave> <core csv folder> <replicate csv folder> <out csv>
# Needs:  R >= 4.4 and the `survey` package (tested with survey 4.4-2 on R 4.4.1).

suppressPackageStartupMessages(library(survey))
options(survey.lonely.psu = "fail")
args <- commandArgs(trailingOnly = TRUE)
wave <- as.integer(args[1]); core <- args[2]; repd <- args[3]; out <- args[4]

rd <- function(path, cols) {
  d <- read.csv(path, colClasses = "character", check.names = FALSE)
  d[cols[cols %in% names(d)]] <- lapply(d[cols[cols %in% names(d)]], as.numeric)
  d
}
rows <- list()
add <- function(estimand, convention, est, se, df) {
  rows[[length(rows) + 1]] <<- data.frame(
    wave = wave, estimand = estimand, convention = convention,
    estimate = as.numeric(est), se = as.numeric(se), df = as.numeric(df))
}
run <- function(label, data, w, repcols, r, type_fhwa, scale_fhwa, type_design, scale_design,
                total_expr, mean_var, dom_expr) {
  des <- function(type, scale) {
    if (type == "other") {
      svrepdesign(data = data, weights = as.formula(paste0("~", w)), repweights = data[, repcols],
                  type = "other", scale = scale, rscales = rep(1, r), mse = TRUE)
    } else {
      svrepdesign(data = data, weights = as.formula(paste0("~", w)), repweights = data[, repcols],
                  type = type, mse = TRUE)
    }
  }
  for (conv in c("fhwa", "design")) {
    d <- if (conv == "fhwa") des(type_fhwa, scale_fhwa) else des(type_design, scale_design)
    t1 <- svytotal(~one, d)
    add(paste0(label, "_total"), conv, coef(t1), SE(t1), degf(d))
    m <- svymean(as.formula(paste0("~", mean_var)), d, na.rm = TRUE)
    add(paste0(label, "_mean_", mean_var), conv, coef(m), SE(m), degf(d))
    sub <- subset(d, eval(parse(text = dom_expr), data) & !is.na(eval(parse(text = dom_expr), data)))
    tt <- svytotal(~one, sub)
    add(paste0(label, "_total_domain"), conv, coef(tt), SE(tt), degf(sub))
  }
}

if (wave == 2009) {
  hh <- rd(file.path(core, "HHV2PUB.CSV"), c("HHSIZE", "WTHHFIN"))
  rp <- read.csv(file.path(repd, "hh50wt.csv"), colClasses = "character", check.names = FALSE)
  repcols <- paste0("HHWGT", 1:100)
  rp[repcols] <- lapply(rp[repcols], as.numeric)
  hh <- merge(hh, rp[, c("HOUSEID", repcols)], by = "HOUSEID")
  hh$one <- 1
  stopifnot(nrow(hh) == 150147)
  run("household", hh, "WTHHFIN", repcols, 100, "other", 0.99, "JK2", NA, NULL, "HHSIZE",
      "HHSIZE >= 3")
  pe <- rd(file.path(core, "PERV2PUB.CSV"), c("R_AGE", "WTPERFIN"))
  rp <- read.csv(file.path(repd, "per50wt.csv"), colClasses = "character", check.names = FALSE)
  repcols <- paste0("WTPERFIN", 1:100)
  rp[repcols] <- lapply(rp[repcols], as.numeric)
  pe <- merge(pe, rp[, c("HOUSEID", "PERSONID", repcols)], by = c("HOUSEID", "PERSONID"))
  pe$one <- 1; pe$age <- ifelse(pe$R_AGE < 0, NA, pe$R_AGE)
  stopifnot(nrow(pe) == 308901)
  run("person", pe, "WTPERFIN", repcols, 100, "other", 0.99, "JK2", NA, NULL, "age", "R_AGE >= 65")
} else if (wave == 2001) {
  hh <- rd(file.path(core, "HHPUB.csv"), c("HHSIZE", "WTHHFIN"))
  rp <- read.csv(file.path(repd, "hh50wt.csv"), colClasses = "character", check.names = FALSE)
  repcols <- paste0("WTHFIN", 1:99)
  rp[repcols] <- lapply(rp[repcols], as.numeric)
  names(rp)[names(rp) == "ID9"] <- "HOUSEID"
  hh <- merge(hh, rp[, c("HOUSEID", repcols)], by = "HOUSEID")
  hh$one <- 1
  stopifnot(nrow(hh) == 69817)
  run("household", hh, "WTHHFIN", repcols, 99, "JK1", NULL, "JK1", NULL, NULL, "HHSIZE",
      "HHSIZE >= 3")
  pe <- rd(file.path(core, "PERPUB.csv"), c("R_AGE", "WTPERFIN"))
  rp <- read.csv(file.path(repd, "pr50wt.csv"), colClasses = "character", check.names = FALSE)
  repcols <- paste0("WTPFIN", 1:99)
  rp[repcols] <- lapply(rp[repcols], as.numeric)
  names(rp)[names(rp) == "ID9"] <- "HOUSEID"
  pe <- merge(pe, rp[, c("HOUSEID", "PERSONID", repcols)], by = c("HOUSEID", "PERSONID"))
  pe$one <- 1; pe$age <- ifelse(pe$R_AGE < 0, NA, pe$R_AGE)
  stopifnot(nrow(pe) == 160758)
  run("person", pe, "WTPERFIN", repcols, 99, "JK1", NULL, "JK1", NULL, NULL, "age", "R_AGE >= 65")
} else {
  stop("wave must be 2001 or 2009")
}
res <- do.call(rbind, rows)
write.csv(res, out, row.names = FALSE)
print(res)
