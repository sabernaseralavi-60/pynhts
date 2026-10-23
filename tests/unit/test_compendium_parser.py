"""The compendium parser (tools/compendium) on synthetic pages of each PDF layout; no PDF or pdftotext needed."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "compendium"))
pc = pytest.importorskip("parse_compendium")

LAYOUT_A = """Bike and Pedestrian Studies

Estimating Nonmotorized Travel Demand

Authors:
An, Meiwu; Chen, Mei
Pedestrians 2007
Transportation Research Record: Journal of the Transportation Research Board Issue: 2002
2007

Abstract:

The modeling of nonmotorized travel demand uses the National Household Travel Survey.

Subject areas and Index Terms

Economics; Pedestrians and Bicyclists

Availability: Transportation Research Board Business Office Order URL:
http://www.trb.org/news/blurb_detail.asp?id=8488
"""
LAYOUT_B = """On Accommodating Spatial Dependence in Bicycle and Pedestrian Injury Counts by
Severity Level Sriram Narayanamoorthy, Rajesh Paleti, Chandra R. Bhat

Publication Date: July 2012

Abstract: This paper proposes a new spatial multivariate count model.

Subject Areas: pedestrian and bicycle crashes; Multivariate count data

Availability: Narayanamoorthy, Sriram, Rajesh Paleti, and Chandra R. Bhat. On accommodating
spatial dependence in bicycle and pedestrian injury counts by severity level. Diss. University of Texas,
2012. https://repositories.lib.utexas.edu/handle/2152/19698
"""
LAYOUT_D = """1.2   Title: Transit Access and Egress Travel as Hidden Sources of Walking and Biking

Author(s): Kash, G. and Mokhtarian, P.

Abstract: In this paper, we use travel diary data from the 2017 National Household Travel
Survey (NHTS) Georgia subsample.

Subject Areas: Access/egress travel; Nonmotorized travel

Availability: Kash, G. and Mokhtarian, P. (2022). Transit Access. TRB 101st Annual Meeting.
https://annualmeeting.mytrb.org/OnlineProgram/Details/17346
"""
CHAPTER_GLUED = """Chapter 6. Special Population Groups
6.1. Title: Comparing Immigrant Travel

Author(s): Doe, J.

Abstract: Immigrants.

Subject Areas: Immigrants

Availability: Doe, J. (2019). Comparing Immigrant Travel. Journal.
"""


def test_layout_a_running_header_and_year():
    e = pc.parse_entry_text(LAYOUT_A, "A")
    assert e.chapter_raw == "Bike and Pedestrian Studies" and e.title == "Estimating Nonmotorized Travel Demand"
    assert e.authors.startswith("An, Meiwu; Chen, Mei") and e.pub_date_raw == "2007"
    assert e.subject_areas.startswith("Economics") and "trb.org" in e.availability


def test_layout_b_title_authors_recovered_from_availability():
    e = pc.parse_entry_text(LAYOUT_B, "B")
    assert e.title == "On Accommodating Spatial Dependence in Bicycle and Pedestrian Injury Counts by Severity Level"
    assert e.authors.startswith("Sriram Narayanamoorthy") and e.split_status == "recovered_from_availability"
    assert e.pub_date_raw == "July 2012"


def test_layout_d_numbered_title_and_labels():
    e = pc.parse_entry_text(LAYOUT_D, "D")
    assert e.entry_no == "1.2" and e.chapter_no == 1 and e.authors == "Kash, G. and Mokhtarian, P."
    assert e.title.startswith("Transit Access and Egress") and "Georgia subsample" in e.abstract


def test_chapter_heading_glued_to_first_entry():
    e = pc.parse_entry_text(CHAPTER_GLUED, "D")
    assert e.chapter_marker == "Special population groups" and e.entry_no == "6.1" and e.title == "Comparing Immigrant Travel"


def test_entry_without_abstract_label_is_flagged():
    e = pc.parse_entry_text("Some Title Smith, J.\n\nSubject Areas: x\n\nAvailability: Smith, J. Some Title. 2012.", "B")
    assert "no_abstract_label" in e.flags and e.abstract == ""


def test_clean_norm_and_domain_aliases():
    assert pc.clean("Women�s  travel") == "Women's travel"
    assert pc.norm("Hello, World-1!") == "helloworld1"
    assert pc.canon_domain("Bike and Pedestrian Studies") == "Bicycle and pedestrian studies"
    assert pc.canon_domain("Public Transportation") == "Transit planning"
    assert pc.canon_domain("Demographic Trends") == "Demographic trends (legacy)"


def test_page_footer_is_dropped():
    assert pc._drop_footer("text\n\n   12  ").endswith("text")
    assert pc._drop_footer("text\nNHTS Compendium 2013   Page 112").endswith("text")


def test_build_helpers_find_url_doi_and_year():
    bc = pytest.importorskip("build_compendium")
    assert bc.find_url("see https://example.org/a- b/c.pdf for more") == "https://example.org/a-b/c.pdf"
    assert bc.find_doi("doi:10.1016/j.tbs.2020.01.001.", "") == "10.1016/j.tbs.2020.01.001"
    assert bc.pub_year("", "Kash, G. (2022). Title. Journal.", "2022")[0] == 2022
    assert bc.pub_year("July 2012", "x", "2012")[0] == 2012
    assert bc.pub_year("", "no year here", "2019")[0] is None
