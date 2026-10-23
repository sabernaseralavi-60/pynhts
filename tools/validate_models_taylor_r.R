# Independent reference for pynhts.models on NHTS 2022 (Taylor-series design: strata STRATUMID, clusters HOUSEID).
# Usage: Rscript tools/validate_models_taylor_r.R <folder with perv2pub.csv and hhv2pub.csv> <out csv>
suppressPackageStartupMessages(library(survey))
options(survey.lonely.psu = "fail")
args <- commandArgs(trailingOnly = TRUE)
dir <- args[1]; out <- args[2]
per <- read.csv(file.path(dir, "perv2pub.csv"), colClasses = "character", check.names = FALSE)
hh <- read.csv(file.path(dir, "hhv2pub.csv"), colClasses = "character", check.names = FALSE)
d <- merge(per[, c("HOUSEID", "PERSONID", "WTPERFIN", "R_AGE", "R_SEX", "WORKER", "DRIVER", "PTUSED")],
           hh[, c("HOUSEID", "STRATUMID")], by = "HOUSEID")
d$w <- as.numeric(d$WTPERFIN); d$age <- as.numeric(d$R_AGE); d$pt <- as.numeric(d$PTUSED)
d <- d[d$age >= 18 & d$R_SEX %in% c("01", "02") & d$WORKER %in% c("01", "02") & d$DRIVER %in% c("01", "02") & d$pt >= 0, ]
d$female <- as.numeric(d$R_SEX == "02"); d$worker <- as.numeric(d$WORKER == "01"); d$driver <- as.numeric(d$DRIVER == "01")
des <- svydesign(ids = ~HOUSEID, strata = ~STRATUMID, weights = ~w, data = d, nest = TRUE)
rows <- list()
for (spec in list(c("binomial", "driver", "age + female + worker"), c("poisson", "pt", "age + female + worker + driver"))) {
  fam <- switch(spec[1], binomial = quasibinomial(), poisson = quasipoisson())
  f <- svyglm(as.formula(paste(spec[2], "~", spec[3])), design = des, family = fam)
  s <- summary(f)$coefficients
  rows[[length(rows) + 1]] <- data.frame(family = spec[1], term = rownames(s), estimate = s[, 1], se = s[, 2], n = nrow(d))
}
res <- do.call(rbind, rows); res$term[res$term == "(Intercept)"] <- "const"
write.csv(res, out, row.names = FALSE); print(res)
