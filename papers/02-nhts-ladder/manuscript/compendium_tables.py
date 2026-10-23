"""Tables built from the NHTS Compendium corpus audit (results/tables/compendium_*.csv, made by tools/compendium/build_compendium.py)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

TAB = Path(__file__).resolve().parents[1] / "results" / "tables"

FA_DOMAIN = {
    "Bicycle and pedestrian studies": "مطالعه‌های دوچرخه و پیاده",
    "Energy consumption": "مصرف انرژی",
    "Environment": "محیط زیست",
    "Health": "سلامت",
    "Policy and mobility": "سیاست و تحرک",
    "Special population groups": "گروه‌های ویژهٔ جمعیتی",
    "Survey, data synthesis and other applications": "پیمایش، ترکیب داده و کاربردهای دیگر",
    "Traffic safety": "ایمنی ترافیک",
    "Transit planning": "برنامه‌ریزی حمل‌ونقل همگانی",
    "Travel behavior": "رفتار سفر",
    "Trend analysis and market segmentation": "تحلیل روند و بخش‌بندی بازار",
    "Emerging travel modes": "شیوه‌های نوظهور سفر",
    "Passive OD data product usage": "کاربرد فراورده‌های دادهٔ مبدأ-مقصد غیرفعال",
}


def T(lang: str, en: str, fa: str) -> str:
    """Pick the English or the Persian text."""
    return fa if lang == "fa" else en


def map_table(lang: str, md_table) -> str:
    """Case studies mapped onto the chapters of the official Compendium."""
    cs = pd.read_csv(TAB / "compendium_case_studies.csv")
    ch = pd.read_csv(TAB / "compendium_by_chapter.csv")
    rows = []
    for _, r in ch.iterrows():
        ids = cs[(cs["in_compendium"]) & (cs["domain"] == r["domain"])]["audit_id"].tolist()
        if not ids:
            continue
        name = FA_DOMAIN.get(r["domain"], r["domain"]) if lang == "fa" else r["domain"]
        rows.append([name, int(r["studies"]), ", ".join(ids), len(ids)])
    missing = cs[~cs["in_compendium"]]["audit_id"].tolist()
    rows.append([T(lang, "Not listed in the Compendium", "در گردایه فهرست نشده"), "-", ", ".join(missing), len(missing)])
    rows.append([T(lang, "All case studies", "همهٔ مطالعه‌های موردی"), int(ch["studies"].sum()), "", len(cs)])
    cols = [T(lang, "Compendium chapter", "فصل گردایه"), T(lang, "Studies in the chapter", "مطالعه‌ها در فصل"),
            T(lang, "Case studies", "مطالعه‌های موردی"), T(lang, "Number", "شمار")]
    cap = T(lang, "The case studies placed in the chapters of the official NHTS Compendium of Uses (chapter of first appearance). The second column counts all distinct studies of the Compendium in the chapter.",
            "مطالعه‌های موردی در فصل‌های گردایهٔ رسمی کاربردهای NHTS (فصل نخستین ظهور). ستون دوم همهٔ مطالعه‌های متمایز گردایه در آن فصل را می‌شمارد.")
    return md_table(pd.DataFrame(rows, columns=cols), cap, "compendium-map", lang, widths=[42, 18, 28, 12], align="lrlr")


def audit_table(lang: str, md_table) -> str:
    """Extraction audit per edition."""
    a = pd.read_csv(TAB / "compendium_extraction_audit.csv")
    rows = []
    for _, r in a.iterrows():
        anchors = "-" if pd.isna(r["abstract_anchors"]) else int(r["abstract_anchors"])
        stated = "-" if pd.isna(r["intro_stated_total"]) else int(r["intro_stated_total"])
        labels = "-" if pd.isna(r["title_labels_div2"]) else int(r["title_labels_div2"])
        rows.append([r["edition"], int(r["entries_parsed"]), anchors, labels, stated, int(r["max_abs_diff_to_independent_counts"])])
    cols = [T(lang, "Edition", "ویرایش"), T(lang, "Entries parsed", "ورودی‌های استخراج‌شده"), T(lang, "Abstract anchors", "لنگرهای چکیده"),
            T(lang, "Title labels / 2", "برچسب عنوان / ۲"), T(lang, "Total stated in the edition", "شمار اعلام‌شده در ویرایش"),
            T(lang, "Largest difference", "بیشترین اختلاف")]
    cap = T(lang, "Extraction audit of the Compendium corpus: entries parsed from each PDF edition (and rows of the 2023-2025 search export) against independent counts. A dash means that the edition has no such count.",
            "ممیزی استخراج گردایه: ورودی‌های استخراج‌شده از هر ویرایش PDF (و ردیف‌های برون‌داد جست‌وجوی ۲۰۲۳ تا ۲۰۲۵) در برابر شمارش‌های مستقل. خط تیره یعنی ویرایش چنین شمارشی ندارد.")
    return md_table(pd.DataFrame(rows, columns=cols), cap, "compendium-audit", lang, widths=[16, 16, 16, 16, 20, 16], align="lrrrrr")
