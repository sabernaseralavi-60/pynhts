"""Transparent, regex-based methodological tags for a study's title, abstract and subject areas.

The tags describe what an *abstract says*, not what the analysis did: an abstract that does not name the survey weights
may still have used them (this is why the rebuild of studies in the pynhts ladder is needed). Every pattern is listed
here so that a reader can audit it; `docs/compendium.md` gives the precision spot-check of the shipped corpus.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

SURVEY_TOKEN = re.compile(
    r"\b(?:NHTS|NPTS|National\s+Household\s+Travel\s+Survey|Nationwide\s+Personal\s+Transportation\s+Survey|"
    r"National\s+Personal\s+Transportation\s+Survey|Nationwide\s+Household\s+Travel\s+Survey|"
    r"National\s+Household\s+Transportation\s+Survey)\b",
    re.I,
)
WAVE_YEARS = ("1969", "1977", "1983", "1990", "1995", "2001", "2009", "2017", "2022")
_WAVE_NUM = re.compile(r"(?<![\d.])(1969|1977|1983|1990|1995|2001|2009|2017|2022)(?![\d])")
_WAVE_ALT = re.compile(r"(?<![\d.])(?:2016\s*[-/–]\s*(?:20)?17|2008\s*[-/–]\s*(?:20)?09)(?![\d])")
NEXTGEN_OD = re.compile(r"\bnext\s*gen(?:eration)?\s*(?:passenger\s+|truck\s+)?(?:OD|origin[\s-]*destination)", re.I)

MODEL_FAMILIES: dict[str, re.Pattern[str]] = {
    "Logit/Choice": re.compile(
        r"\b(?:logit|logistic|probit|discrete[\s-]choice|multinomial|mnl|nested\s+logit|mixed\s+logit|ordered\s+(?:logit|probit|response)|"
        r"mdcev|choice\s+model|latent\s+class\s+choice|binary\s+choice|mode[\s-]choice\s+model)\b", re.I),
    "Count (Poisson/NB/ZINB)": re.compile(
        r"\b(?:poisson|negative[\s-]binomial|zinb|zero[\s-]inflated|count\s+(?:data\s+)?model|hurdle\s+model|zero[\s-]truncated)\b", re.I),
    "OLS/Linear": re.compile(
        r"\b(?:ols|ordinary\s+least\s+squares|linear\s+regression|multiple\s+regression|least[\s-]squares\s+regression|"
        r"linear\s+(?:probability|mixed)\s+model|log[\s-]linear|regression\s+analysis|regression\s+model)", re.I),
    "SEM/Path": re.compile(r"\b(?:structural\s+equation|sem\b|path\s+analysis|latent\s+variable\s+model|simultaneous\s+equation)", re.I),
    "PSM/Causal": re.compile(
        r"\b(?:propensity\s+score|difference[\s-]in[\s-]differences?|instrumental\s+variable|regression\s+discontinuity|"
        r"causal\s+(?:inference|effect|forest)|quasi[\s-]experiment)", re.I),
    "Hazard/Duration": re.compile(r"\b(?:hazard[\s-]based|hazard\s+model|duration\s+model|survival\s+analysis|time[\s-]to[\s-]event)", re.I),
    "Multilevel/Mixed": re.compile(r"\b(?:multi[\s-]?level|hierarchical\s+(?:linear\s+)?model|mixed[\s-]effects?|random[\s-]effects?|random\s+parameter)", re.I),
    "Spatial": re.compile(r"\b(?:spatial\s+(?:regression|econometric|lag|error|autocorrelation)|geographically\s+weighted|gwr|moran)", re.I),
    "Machine learning": re.compile(
        r"\b(?:machine[\s-]learning|deep[\s-]learning|neural\s+network|random\s+forests?|gradient[\s-]boost|xgboost|lightgbm|catboost|"
        r"adaboost|support\s+vector|svm|decision\s+tree|k[\s-]nearest|knn|naive\s+bayes|lstm|convolutional|transformer\s+model|"
        r"reinforcement\s+learning|graph\s+neural|supervised\s+learning|classifier|bagging|ensemble\s+(?:learning|method))", re.I),
    "Clustering/Segmentation": re.compile(r"\b(?:k[\s-]means|cluster\s+analysis|clustering|latent\s+class\s+analysis|market\s+segmentation|typolog)", re.I),
    "Simulation/Optimisation": re.compile(
        r"\b(?:simulat|agent[\s-]based|microsimulation|monte\s+carlo|optimi[sz]ation|linear\s+programming|mixed[\s-]integer|"
        r"scenario\s+analysis|system\s+dynamics|stochastic\s+model)", re.I),
}
_REGRESSION_ANY = re.compile(r"\bregress", re.I)
_REGRESSION_INFERENCE = (
    "Logit/Choice", "Count (Poisson/NB/ZINB)", "OLS/Linear", "SEM/Path", "PSM/Causal", "Hazard/Duration", "Multilevel/Mixed", "Spatial",
)

_SURVEY_WEIGHT = re.compile(
    r"\b(?:(?:sampling|survey|population|person|household|trip|expansion|final|statistical|replicate|analysis|design|nhts|sample)[\s-]+weights?\b|"
    r"(?:sample|survey|sampling)\s+weighting|weights?\s+(?:should\s+be\s+|were\s+|was\s+|are\s+|is\s+|being\s+)?(?:applied|used|provided|supplied|included|introduced)|"
    r"expansion\s+factors?|post[\s-]?stratif|raking|wtperfin|wthhfin|wttrdfin|hhwgt|wtfin|"
    r"weighted\s+(?:(?:multivariate|multivariable|multiple|multilevel|mixed|ordinal|ordered|binary|multinomial|generalized|negative|binomial|linear|log|adjusted|nested|descriptive|simple|and|the|survey|national|nationally)\s+){0,3}(?:regression|logistic|logit|probit|poisson|descriptive|statistics|estimat\w*|sample|analys\w*|percent\w*|proportion\w*|"
    r"prevalence|means?|survey|odds|model\w*|rates?|trips?|results?|population|national\w*|counts?|totals?|frequenc\w*|data|least|"
    r"by\s+(?:the\s+)?(?:survey|sampling|person|household|trip|nhts)|to\s+(?:reflect|represent|match|account|adequately|be\s+representative|the\s+(?:national|us|u\.s\.)))|"
    r"(?:survey|sample|population|person|household|trip)[\s-]weighted|with\s+and\s+without\s+weights?|"
    r"weighting\s+(?:scheme|factor|procedure|method\b|adjust\w*|by)|"
    r"(?:using|apply(?:ing)?|applied|incorporat(?:e|ing))\s+(?:the\s+)?(?:survey\s+|sampling\s+|provided\s+)?weights?\b)", re.I)
# uses of "weight" that are not survey weights (spatial weighting, propensity or class weights, vehicle weight, weighted graphs ...)
_WEIGHT_NOISE = re.compile(
    r"\b(?:vehicle|gross|curb|body|birth|axle|load|passenger)\s+weight|weight\s+(?:loss|gain|status|matri|initiali)|lightweight|light[\s-]weight|"
    r"(?:geographically|spatially|spatial|temporally|locally)[\s-]+weighted(?:\s+\w+){0,2}\s+(?:regression|model)|\bgwr\b|"
    r"(?:propensity[\s-]score|inverse[\s-]probability|inverse[\s-]distance|entropy|kernel|class)[\s-]+weight\w*|"
    r"(?:demand|density|income|time|distance|self|cost|utility|gravity)[\s-]+weighted|"
    r"weighted\s+(?:f[\s-]?score|f1|directed|graph|network|duration|average|sum|mean\s+of|loss|kappa|rf|voting|centroid)|"
    r"population[\s-]weighted\s+(?:density|average|mean|centroid)|\bpwd\b", re.I)

VARIANCE_STRICT: dict[str, re.Pattern[str]] = {
    "replicate weights": re.compile(r"\breplicate[\s-]+weights?\b|\breplicate\s+(?:variance|estimat)", re.I),
    "jackknife": re.compile(r"\bjack[\s-]?knife\b", re.I),
    "BRR": re.compile(r"\bbalanced\s+repeated\s+replication\b|\bBRR\b"),
    "Taylor linearisation": re.compile(r"\btaylor[\s-]+(?:series|linear)|\blineari[sz]ation\b", re.I),
    "svy/survey package": re.compile(r"\bsvy\b|\bsurvey\s+package\b|\bsurveyglm\b|\bproc\s+surveyreg\b|\bsurveylogistic\b", re.I),
    "complex survey design": re.compile(
        r"\bcomplex\s+(?:survey|sampl)|\bdesign[\s-]effects?\b|\bdeff\b|\bdesign[\s-]based\s+(?:variance|inference|estimat|standard)|"
        r"\bsurvey[\s-]design\s+(?:weights|adjust|variance|aware|effects|based)|\bfollowing\s+the\s+(?:nhts\s+)?survey\s+design\b|"
        r"\baccount(?:s|ed|ing)?\s+for\s+(?:the\s+)?(?:complex\s+)?survey\s+design|\bvariance\s+estimation\b|\bsurvey[\s-]weighted\s+(?:standard|variance)", re.I),
    "clustered standard errors": re.compile(r"\bcluster(?:ed)?[\s-]+(?:robust\s+)?(?:standard\s+errors?|se)\b|\bcluster[\s-]robust\b", re.I),
}
VARIANCE_WEAK: dict[str, re.Pattern[str]] = {
    "bootstrap": re.compile(r"\bbootstrap", re.I),
    "robust standard errors": re.compile(r"\brobust\s+standard\s+errors?\b|\bsandwich\b|\bhuber[\s-]white\b", re.I),
}

_RESAMPLING = re.compile(
    r"\b(?:smote|adasyn|over[\s-]?sampl|under[\s-]?sampl|class[\s-]+imbalance|imbalanced?\s+(?:data|class|dataset|sample)|resampl|rebalanc)", re.I)
_VALIDATION = re.compile(
    r"\b(?:cross[\s-]?validat|k[\s-]fold|hold[\s-]?out|train(?:ing)?[\s/-]+(?:and\s+)?test|test(?:ing)?\s+(?:set|data|sample)|"
    r"training\s+(?:set|data|sample)|validation\s+(?:set|data|sample)|\broc\b|\bauc\b|area\s+under|f1[\s-]score|confusion\s+matrix|"
    r"out[\s-]of[\s-]sample)", re.I)
_ACCURACY = re.compile(
    r"(?:accuracy|accurate(?:ly)?|auc|f1[\s-]score|f-measure)[^.;]{0,70}?(\d{2}(?:\.\d+)?)\s*(?:%|percent)|"
    r"(\d{2}(?:\.\d+)?)\s*(?:%|percent)\s+(?:\w+\s+){0,3}(?:accuracy|accurate)", re.I)
_ACCURACY_FRACTION = re.compile(r"(?:accuracy|auc|f1[\s-]score)(?:\s+(?:of|was|is|=|reached|achieved|at))*\s*[:=]?\s*(0\.\d{2,4}|1\.0+)(?!\d)", re.I)

TOPICS: dict[str, re.Pattern[str]] = {
    "bikeshare / micromobility": re.compile(r"bike[\s-]?shar|bicycle[\s-]shar|e[\s-]?scooter|scooter|micromobil|shared\s+(?:bike|micro)", re.I),
    "cycling / walking / active travel": re.compile(r"\bbicycl|\bcycling|\bbik(?:e|ing)\b|\bwalking|\bpedestrian|active\s+(?:travel|transport)", re.I),
    "older adults": re.compile(r"older\s+(?:adult|driver|people|american)|elderly|\bseniors?\b|\baging\b|\bageing\b|aged\s+65", re.I),
    "children / school travel": re.compile(r"\bschool|\bchildren|\bchild\b|\byouth|adolescen|\bteen|student", re.I),
    "EV / alternative fuel adoption": re.compile(
        r"electric\s+vehicle|plug[\s-]in|\bphevs?\b|\bbevs?\b|\bevs\b|\bev\b|alternative[\s-]fuel|\bafvs?\b|hybrid\s+vehicle|charging|battery[\s-]electric", re.I),
    "ride-hailing / shared mobility": re.compile(r"ride[\s-]?hail|ride[\s-]?sourc|ride[\s-]?shar|transportation\s+network\s+compan|\btncs?\b|\buber\b|\blyft\b|shared\s+mobility|carshar|car[\s-]shar", re.I),
    "online shopping / e-commerce": re.compile(r"online\s+shopping|e[\s-]?shopping|e[\s-]?commerce|home\s+delivery|online\s+purchas|package\s+delivery|delivery\s+demand", re.I),
    "telework / telecommuting": re.compile(r"telework|telecommut|work(?:ing)?\s+(?:from|at)\s+home|remote\s+work|home[\s-]based\s+work", re.I),
    "automated vehicles": re.compile(r"autonomous|automated\s+vehicle|self[\s-]driving|connected\s+and\s+automated|\bavs?\b|driverless", re.I),
    "transit": re.compile(r"\btransit\b|\bbus(?:es)?\b|\brail\b|public\s+transport", re.I),
    "health / physical activity": re.compile(r"physical\s+activity|obesity|\bhealth|\bbmi\b|chronic|exercise", re.I),
    "traffic safety": re.compile(r"\bcrash|\bfatal|\bsafety|\binjur|collision", re.I),
    "energy / fuel": re.compile(r"\bfuel|\benergy|gasoline|\bmpg\b|fuel\s+economy|petroleum|vehicle\s+efficiency", re.I),
    "emissions / climate": re.compile(r"emission|greenhouse|\bghg\b|air\s+quality|carbon|climate", re.I),
    "equity / low income": re.compile(r"\bequit|low[\s-]income|disparit|poverty|environmental\s+justice|disadvantage|affordab", re.I),
    "COVID-19": re.compile(r"covid|pandemic|coronavirus", re.I),
    "VMT / vehicle use": re.compile(r"\bvmt\b|vehicle[\s-]miles?|miles\s+(?:of\s+travel|driven)|annual\s+mileage", re.I),
    "freight / trucks": re.compile(r"freight|\btruck|goods\s+movement|commercial\s+vehicle", re.I),
    "rural": re.compile(r"\brural", re.I),
    "race / ethnicity / immigrants": re.compile(r"immigrant|\brace\b|racial|ethnic|minorit|hispanic|latino|african[\s-]american|\bblack\b", re.I),
    "disability": re.compile(r"disabilit|mobility[\s-](?:limit|impair)|impairment", re.I),
    "vehicle ownership": re.compile(r"vehicle\s+ownership|car\s+ownership|auto(?:mobile)?\s+ownership|\bcarless|zero[\s-]vehicle|motori[sz]ation", re.I),
    "commuting": re.compile(r"\bcommut|journey[\s-]to[\s-]work|work\s+trip|home[\s-]to[\s-]work", re.I),
    "built environment / land use": re.compile(r"built\s+environment|land[\s-]use|\bdensity|sprawl|walkab|neighbou?rhood|urban\s+form|smart\s+growth", re.I),
    "gender": re.compile(r"\bgender|\bwomen|\bwoman|\bfemale", re.I),
    "travel-survey methods / data synthesis": re.compile(
        r"survey\s+method|data\s+collection|synthetic|synthesis|imputation|non[\s-]?response|response\s+rate|transferab|data\s+fusion|sampling", re.I),
    "passive OD / big data": re.compile(r"origin[\s-]destination|location[\s-]based|mobile\s+(?:device|phone)|cell\s*phone|\bgps\b|big\s+data|passive\s+data", re.I),
    "trip chaining / activity patterns": re.compile(r"trip[\s-]chain|tour\b|activity[\s-](?:pattern|based|travel)|time\s+use", re.I),
}


@dataclass
class Tags:
    """Methodological tags of one study (what the text says, not what the analysis did)."""

    mentions_nhts: bool = False
    nhts_waves_mentioned: list[str] = field(default_factory=list)
    model_families: list[str] = field(default_factory=list)
    study_type: str = "descriptive_or_other"
    is_ml: bool = False
    mentions_weights: bool = False
    weight_terms: list[str] = field(default_factory=list)
    mentions_variance_design: bool = False
    variance_terms: list[str] = field(default_factory=list)
    mentions_bootstrap_or_robust_se: bool = False
    mentions_resampling: bool = False
    mentions_validation: bool = False
    mentions_imbalance_or_leakage_risk: bool = False
    accuracy_claim_pct: float | None = None
    topics: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        """Return the tags as a plain dictionary."""
        return asdict(self)


def detect_waves(text: str) -> list[str]:
    """NHTS/NPTS waves named near a survey token ("2017 NHTS", "NHTS data from 2001 and 2009", "2016-17")."""
    found: set[str] = set()
    for m in SURVEY_TOKEN.finditer(text):
        window = text[max(0, m.start() - 45): m.end() + 60]
        found.update(_WAVE_NUM.findall(window))
        if _WAVE_ALT.search(window):
            found.add("2017" if "17" in _WAVE_ALT.search(window).group(0)[-2:] else "2009")  # type: ignore[union-attr]
    for m in re.finditer(r"\b(?:NPTS|Nationwide\s+Personal\s+Transportation\s+Survey)\b", text, re.I):
        if not found.intersection(("1969", "1977", "1983", "1990", "1995")) and m:
            found.add("NPTS (year unstated)")
            break
    if NEXTGEN_OD.search(text):
        found.add("NextGen OD")
    order = list(WAVE_YEARS) + ["NPTS (year unstated)", "NextGen OD"]
    return [w for w in order if w in found]


def tag(title: str = "", abstract: str = "", subject_areas: str = "") -> Tags:
    """Tag one study from its title, abstract and subject areas."""
    text = " ".join(x for x in (title, abstract, subject_areas) if x)
    t = Tags()
    t.mentions_nhts = bool(SURVEY_TOKEN.search(text))
    t.nhts_waves_mentioned = detect_waves(text)
    fams = [name for name, rx in MODEL_FAMILIES.items() if rx.search(text)]
    if not any(f in fams for f in _REGRESSION_INFERENCE) and _REGRESSION_ANY.search(text):
        fams.append("Regression (unspecified)")
    t.model_families = fams
    t.is_ml = "Machine learning" in fams
    cleaned = _WEIGHT_NOISE.sub(" ", text)
    wt = [m.group(0).lower() for m in _SURVEY_WEIGHT.finditer(cleaned)]
    t.weight_terms = sorted(set(wt))
    t.mentions_weights = bool(wt)
    vt = [name for name, rx in VARIANCE_STRICT.items() if rx.search(text)]
    t.variance_terms = vt
    t.mentions_variance_design = bool(vt)
    t.mentions_bootstrap_or_robust_se = any(rx.search(text) for rx in VARIANCE_WEAK.values())
    t.mentions_resampling = bool(_RESAMPLING.search(text))
    t.mentions_validation = bool(_VALIDATION.search(text))
    t.mentions_imbalance_or_leakage_risk = t.mentions_resampling or (t.is_ml and t.mentions_validation)
    nums = [float(a or b) for a, b in _ACCURACY.findall(text)]
    nums += [float(x) * 100 for x in _ACCURACY_FRACTION.findall(text)]
    nums = [x for x in nums if 50.0 <= x <= 100.0]
    t.accuracy_claim_pct = max(nums) if nums else None
    t.topics = [name for name, rx in TOPICS.items() if rx.search(text)]
    if t.is_ml:
        t.study_type = "machine_learning"
    elif any(f in fams for f in _REGRESSION_INFERENCE) or "Regression (unspecified)" in fams:
        t.study_type = "regression_inference"
    elif "Simulation/Optimisation" in fams:
        t.study_type = "simulation_or_optimisation"
    else:
        t.study_type = "descriptive_or_other"
    return t
