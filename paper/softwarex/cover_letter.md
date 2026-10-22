Dear Editors of SoftwareX,

Please consider the enclosed Original Software Publication, "pynhts: survey-weight-aware Python access to the US National Household Travel Survey", for publication in SoftwareX.

pynhts is an open-source Python library (BSD 3-Clause, GitHub repository with README.md, LICENSE.txt and source in src/, archived on Zenodo) for the four public-use waves of the US National Household Travel Survey (2001, 2009, 2017, 2022). It downloads and verifies the official files, exposes the four tables without silent merge errors, computes estimates with the variance method of each wave (jackknife replicate weights; Taylor linearisation for 2022), maps codes between waves only where the meaning is shown to be the same, and lets an analyst state sample rules and missing-value policy as code, with a sample-flow table as output.

The software is domain-specific, but it addresses a reproducibility problem that is general for survey-based research: assumptions such as the base of a percentage, the treatment of skipped questions or the definition of a weekend are rarely stated in papers and move published values by several per cent. The paper therefore reports validation as part of the software: 142 of 175 figures printed in official reports reproduce completely, and 21 published studies that use the survey were rebuilt from the public files, with every printed number graded and no rule tuned to reach a number.

We state plainly that the package is young: it has no known external users and no publication has used it yet. The Impact section therefore rests on the validation and on the audit, which anyone can repeat with the public files.

The manuscript is not under consideration elsewhere. The generative-AI use is declared in the manuscript. [[AUTHOR-TODO: confirm there is no competing interest and give the funding statement]]

Sincerely,
Seyed Saber Naseralavi
Department of Civil Engineering, Shahid Bahonar University of Kerman, Kerman, Iran
[[AUTHOR-TODO: e-mail]]
