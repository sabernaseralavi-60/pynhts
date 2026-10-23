"""Tables of the manuscript, generated from results/tables (English and Persian headers)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

RES = Path(__file__).resolve().parents[1] / "results"
TAB = RES / "tables"


def T(lang, en, fa):
    return fa if lang == "fa" else en


def tables(lang, n, md_table):
    out = {}
    st = pd.read_csv(TAB / "studies.csv")
    l0 = {"SUFFICIENT": T(lang, "rebuilt", "کامل"), "PARTIAL": T(lang, "partly", "جزئی"),
          "INSUFFICIENT": T(lang, "not rebuilt", "ناکافی")}
    rows = []
    for _, r in st.iterrows():
        l2 = {"good": T(lang, "reproduced", "بازتولید شد"), "mid": T(lang, "partly", "جزئی"), "bad": T(lang, "not reproduced", "بازتولید نشد"),
              "none": T(lang, "no valid target", "بدون هدف معتبر"), "na": T(lang, "not run", "اجرا نشد")}[r["L2_grade"]]
        rows.append([r["id"], r["study"], r["wave"], r["family"], l0[r["L0_verdict"]],
                     f"{int(r['L1_graded'])} ({r['L1_share_exact_close'] * 100:.0f}%)", l2])
    cols = [T(lang, "ID", "شناسه"), T(lang, "Study", "مطالعه"), T(lang, "Wave", "موج"), T(lang, "Model", "مدل"),
            T(lang, "Sample (L0)", "نمونه (L0)"), T(lang, "Printed values matched (L1)", "عددهای چاپی منطبق (L1)"),
            T(lang, "Model (L2)", "مدل (L2)")]
    out["studies"] = md_table(pd.DataFrame(rows, columns=cols),
                              T(lang, "The 22 case studies and the rung each reached. L1 gives the number of printed descriptive values graded and, in brackets, the share graded EXACT or CLOSE.",
                                "بیست‌ودو مطالعهٔ موردی و پله‌ای که هر یک به آن رسید. L1 شمار عددهای توصیفی چاپی درجه‌بندی‌شده و در پرانتز سهم عددهای EXACT یا CLOSE را می‌دهد."),
                              "studies", lang, widths=[8, 16, 12, 19, 10, 16, 19], align="llllllr"[:7])
    by = pd.read_csv(TAB / "census_by_study.csv")
    rows = []
    for _, r in by.iterrows():
        pub = f"{int(r['naive_exact_close'])} / {int(r['weighted_exact_close'])} / {int(r['n_pub'])}" if r["n_pub"] else "-"
        lost = f"{int(r['lost_style'])} / {int(r['sig_style'])}" if r["sig_style"] else "-"
        rows.append([r["study"], int(r["n_coef"]), pub, f"{r['r_weights']:.2f}", f"{r['r_cluster']:.2f}", f"{r['r_formula']:.2f}", lost,
                     int(r["sign_flips"])])
    cols = [T(lang, "Study", "مطالعه"), T(lang, "Coefficients", "ضرایب"),
            T(lang, "Printed values reproduced: unweighted / weighted / printed", "مقدار چاپی بازتولیدشده: بدون وزن / وزنی / چاپی"),
            T(lang, "Weights", "وزن"), T(lang, "Clustering", "خوشه"), T(lang, "Replicate formula", "فرمول تکرار"),
            T(lang, "Significance lost (declared inference)", "معناداری ازدست‌رفته (استنباط اعلام‌شده)"), T(lang, "Sign flips", "تغییر علامت")]
    out["census"] = md_table(pd.DataFrame(rows, columns=cols),
                             T(lang, "Re-estimation of eight regression studies. The three ratio columns are median ratios of standard errors: weighted model-based over unweighted; weighted household-clustered over weighted model-based; replicate-weight over weighted household-clustered. Significance lost: coefficients significant under the study's declared inference that are not under the design-aware fit (the study that itself used the jackknife has none). Sign flip: unweighted and design-aware estimates differ in sign.",
                               "برآورد دوبارهٔ هشت مطالعهٔ رگرسیونی. سه ستون نسبت، میانهٔ نسبت خطاهای معیار است: وزنی مبتنی بر مدل بر بدون وزن؛ وزنی خوشه‌ای خانوار بر وزنی مبتنی بر مدل؛ وزن تکرار بر وزنی خوشه‌ای خانوار. معناداری ازدست‌رفته: ضرایب معنادار زیر استنباط اعلام‌شدهٔ مطالعه که در برازش طراحی‌آگاه نیستند (مطالعه‌ای که خود از جک‌نایف استفاده کرد موردی ندارد). تغییر علامت: علامت برآورد بدون وزن و طراحی‌آگاه فرق دارد."),
                             "census", lang, widths=[22, 9, 17, 8, 8, 9, 15, 8], align="lrrrrrrr")
    # models and hyper-parameters (glossary + search space)
    gl = [
        ("LR", T(lang, "Logistic regression: a weighted sum of the inputs turned into a probability", "رگرسیون لجستیک: جمع وزنی ورودی‌ها که به احتمال تبدیل می‌شود"),
         T(lang, "penalty strength C (0.001-100, log scale); penalty type (L1 or L2)", "قدرت جریمه C (۰٫۰۰۱ تا ۱۰۰، مقیاس لگاریتمی)؛ نوع جریمه (L1 یا L2)")),
        ("NB", T(lang, "Gaussian naive Bayes: each input is assumed bell-shaped within each class and independent of the others", "بیز ساده با توزیع گاوسی: هر ورودی در هر رده زنگوله‌ای و مستقل از دیگران فرض می‌شود"),
         T(lang, "variance floor (1e-11 to 1e-3, log scale)", "کف واریانس (۱e-۱۱ تا ۱e-۳، مقیاس لگاریتمی)")),
        ("DT", T(lang, "Decision tree: a sequence of yes/no questions on the inputs that ends in a leaf with a class", "درخت تصمیم: رشته‌ای از پرسش‌های بله/خیر دربارهٔ ورودی‌ها که به برگی با یک رده می‌رسد"),
         T(lang, "maximum depth (3, 5, 8, 12, 20); minimum leaf size (1, 5, 20, 50); split criterion (Gini or entropy)", "بیشینهٔ عمق (۳، ۵، ۸، ۱۲، ۲۰)؛ کمینهٔ اندازهٔ برگ (۱، ۵، ۲۰، ۵۰)؛ معیار شکست (جینی یا آنتروپی)")),
        ("RF", T(lang, "Random forest: many trees grown on random parts of the data whose votes are averaged", "جنگل تصادفی: درختان بسیار روی بخش‌های تصادفی داده که رأی‌شان میانگین‌گیری می‌شود"),
         T(lang, "number of trees (50, 100, 200); maximum depth (5, 10, 20, 40); minimum leaf size (1, 2, 5, 20); share of inputs tried per split (0.3, 0.5, 1)", "شمار درختان (۵۰، ۱۰۰، ۲۰۰)؛ بیشینهٔ عمق (۵، ۱۰، ۲۰، ۴۰)؛ کمینهٔ اندازهٔ برگ (۱، ۲، ۵، ۲۰)؛ سهم ورودی‌های آزموده در هر شکست (۰٫۳، ۰٫۵، ۱)")),
        ("SVM", T(lang, "Support vector machine with a radial kernel: separates the classes with a smooth boundary built from the training points nearest to it", "ماشین بردار پشتیبان با هستهٔ شعاعی: رده‌ها را با مرزی هموار که از نزدیک‌ترین نمونه‌های آموزشی ساخته می‌شود جدا می‌کند"),
         T(lang, "cost C (0.1-100, log scale); kernel width gamma (0.001-1, log scale); trained on at most 12,000 rows", "هزینهٔ C (۰٫۱ تا ۱۰۰، مقیاس لگاریتمی)؛ پهنای هسته گاما (۰٫۰۰۱ تا ۱، مقیاس لگاریتمی)؛ آموزش روی حداکثر ۱۲٬۰۰۰ ردیف")),
    ]
    cols = [T(lang, "Model", "مدل"), T(lang, "Idea in plain words", "ایده به زبان ساده"), T(lang, "Searched hyper-parameters (ten random trials each)", "ابرپارامترهای جست‌وجوشده (ده آزمایش تصادفی برای هر مدل)")]
    out["search"] = md_table(pd.DataFrame(gl, columns=cols),
                             T(lang, "The five classifiers and the search space of their settings (the same ten-trial random search for every model).",
                               "پنج طبقه‌بند و فضای جست‌وجوی تنظیمات آن‌ها (برای همهٔ مدل‌ها همان جست‌وجوی تصادفی ده‌آزمایشی)."),
                             "search", lang, widths=[8, 45, 47], align="lll")
    out["auc"] = auc_table(lang, md_table)
    out["selected"] = selected_table(lang, md_table)
    import compendium_tables as CT

    out["compendium_map"] = CT.map_table(lang, md_table)
    out["compendium_audit"] = CT.audit_table(lang, md_table)
    return out


def selected_table(lang, md_table):
    import ast

    f = TAB / "p06_p17_tuned.csv"
    if not f.exists():
        return ""
    t = pd.read_csv(f)
    t = t[(t["scheme"] == "grouped") & (t["seed"] == 0)]
    rows = []
    for lab, lname in (("AFV", T(lang, "Alternative-fuel", "سوخت جایگزین")), ("EV", T(lang, "Electric", "برقی"))):
        for m in ("LR", "NB", "DT", "RF", "SVM"):
            r = t[(t["label"] == lab) & (t["model"] == m)].iloc[0]
            h = ast.literal_eval(r["hparams"])
            txt = ", ".join(f"{k} = {v:.3g}" if isinstance(v, float) else f"{k} = {v}" for k, v in h.items())
            rows.append([lname, m, txt, f"{r['inner_auc']:.2f}"])
    cols = [T(lang, "Outcome", "پیامد"), T(lang, "Model", "مدل"), T(lang, "Selected values", "مقدارهای برگزیده"),
            T(lang, "Inner validation AUC", "AUC اعتبارسنجی درونی")]
    return md_table(pd.DataFrame(rows, columns=cols),
                    T(lang, "Selected hyper-parameters of the tuned models in the household-split pipeline (first master seed). C: cost or penalty strength; vs: variance floor; depth, leaf, crit: tree depth, minimum leaf size, split criterion; n, mf: number of trees and share of inputs per split; gamma: kernel width.",
                      "ابرپارامترهای برگزیدهٔ مدل‌های تنظیم‌شده در خط لولهٔ تقسیم خانوار (بذر اصلی نخست). C: هزینه یا قدرت جریمه؛ vs: کف واریانس؛ depth، leaf، crit: عمق درخت، کمینهٔ اندازهٔ برگ و معیار شکست؛ n، mf: شمار درختان و سهم ورودی در هر شکست؛ gamma: پهنای هسته."),
                    "selected", lang, widths=[14, 8, 62, 16], align="lllr")


def auc_table(lang, md_table):
    import json
    ml = json.loads((RES / "numbers" / "ml.json").read_text(encoding="utf-8"))
    tuned = ml.get("tuned")
    pipes = [("leaky", T(lang, "Leaky", "نشت‌دار")),
             ("rows", T(lang, "Rows", "ردیف‌ها")),
             ("grouped", T(lang, "Households", "خانوارها")),
             ("weighted", T(lang, "Weighted", "وزنی"))]
    rows = []
    for lab, lname in (("afv", T(lang, "Alternative-fuel", "سوخت جایگزین")), ("ev", T(lang, "Electric", "برقی"))):
        for m in ("lr", "nb", "dt", "rf", "svm"):
            r = [lname, m.upper()] + [f"{ml[lab][k][m]:.2f}" for k, _ in pipes]
            if tuned and lab in tuned:
                r += [f"{tuned[lab]['leaky'][m]:.2f}", f"{tuned[lab]['grouped'][m]:.2f}"]
            rows.append(r)
    cols = [T(lang, "Outcome", "پیامد"), T(lang, "Model", "مدل")] + [n for _, n in pipes]
    if tuned:
        cols += [T(lang, "Tuned, leaky", "تنظیم‌شده، نشت‌دار"),
                 T(lang, "Tuned, households", "تنظیم‌شده، خانوارها")]
    w = [14, 8] + [11] * (len(cols) - 2)
    return md_table(pd.DataFrame(rows, columns=cols),
                    T(lang, "Area under the ROC curve on held-out rows (mean of three seeds for default settings, two for tuned models). Leaky: oversample, then split rows. Rows: split rows, then oversample. Households: split households, then oversample. Weighted: split households, no oversampling, survey-weighted score.",
                      "سطح زیر منحنی ROC روی ردیف‌های کنار گذاشته‌شده (میانگین سه بذر برای تنظیمات پیش‌فرض و دو بذر برای مدل‌های تنظیم‌شده). نشت‌دار: بازنمونه‌گیری و سپس تقسیم ردیف‌ها. ردیف‌ها: تقسیم ردیف‌ها و سپس بازنمونه‌گیری. خانوارها: تقسیم خانوارها و سپس بازنمونه‌گیری. وزنی: تقسیم خانوارها بدون بازنمونه‌گیری و امتیاز وزنی."),
                    "auc", lang, widths=w, align="ll" + "r" * (len(cols) - 2))
