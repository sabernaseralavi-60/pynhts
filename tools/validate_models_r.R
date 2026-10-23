# Independent reference for pynhts.models (NHTS 2017, person level, jackknife JKn).
#
# Reads the RAW csv files, builds the replicate-weight design with R's `survey` package
# (type = "other", scale = 6/7, rscales = 1, mse = TRUE: the JKn variance of the User's Guide) and fits three
# survey GLMs on adults; writes coefficients and standard errors to tests/golden/models_2017_r.csv.
#
# Usage:  Rscript tools/validate_models_r.R <folder with perpub.csv and perwgt.csv> <out csv>
suppressPackageStartupMessages(library(survey))
args <- commandArgs(trailingOnly = TRUE)
dir <- args[1]; out <- args[2]
per <- read.csv(file.path(dir, "perpub.csv"), colClasses = "character", check.names = FALSE)
wt <- read.csv(file.path(dir, "perwgt.csv"), colClasses = "character", check.names = FALSE)
repcols <- paste0("WTPERFIN", 1:98)
wt[c("WTPERFIN", repcols)] <- lapply(wt[c("WTPERFIN", repcols)], as.numeric)
d <- merge(per[, c("HOUSEID", "PERSONID", "R_AGE", "R_SEX", "WORKER", "DRIVER", "CNTTDTR")],
           wt[, c("HOUSEID", "PERSONID", "WTPERFIN", repcols)], by = c("HOUSEID", "PERSONID"))
d$age <- as.numeric(d$R_AGE); d$trips <- as.numeric(d$CNTTDTR)
d <- d[d$age >= 18 & d$trips >= 0 & d$R_SEX %in% c("01", "02") & d$WORKER %in% c("01", "02") & d$DRIVER %in% c("01", "02"), ]
d$female <- as.numeric(d$R_SEX == "02"); d$worker <- as.numeric(d$WORKER == "01"); d$driver <- as.numeric(d$DRIVER == "01")
d$any <- as.numeric(d$trips > 0)
des <- svrepdesign(data = d, weights = ~WTPERFIN, repweights = d[, repcols], type = "other", scale = 6/7,
                   rscales = rep(1, 98), mse = TRUE)
rows <- list()
for (spec in list(c("binomial", "any"), c("poisson", "trips"), c("gaussian", "trips"))) {
  fam <- switch(spec[1], binomial = quasibinomial(), poisson = quasipoisson(), gaussian = gaussian())
  f <- svyglm(as.formula(paste(spec[2], "~ age + female + worker + driver")), design = des, family = fam)
  s <- summary(f)$coefficients
  rows[[length(rows) + 1]] <- data.frame(family = spec[1], term = rownames(s), estimate = s[, 1], se = s[, 2], n = nrow(d))
}
res <- do.call(rbind, rows); res$term[res$term == "(Intercept)"] <- "const"
write.csv(res, out, row.names = FALSE); print(res)
