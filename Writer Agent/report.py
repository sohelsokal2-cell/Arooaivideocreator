import json
import os
import re

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


def _set_bangla_font(document):
    style = document.styles["Normal"]
    style.font.name = "Nirmala UI"
    style.font.size = Pt(12)
    rpr = style.element.get_or_add_rPr()
    rpr.rFonts.set(qn("w:eastAsia"), "Nirmala UI")


def write_txt_script(script_data, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    full_script = script_data.get("full_script", "")
    scenes = script_data.get("scenes", [])
    headline = script_data.get("headline", "")

    lines = [
        f"=== REEL SCRIPT: {headline} ===",
        full_script,
        "",
        "=== SCENE BREAKDOWN ===",
    ]
    for sc in scenes:
        lines.append(f"[দৃশ্য {sc.get('scene_num', 1)}] (ছবি #{sc.get('image_index', 1)})")
        lines.append(sc.get("text", ""))
        lines.append("")

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines).strip() + "\n")
    return path


def write_docx_script(script_data, path, date_label):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    document = Document()
    _set_bangla_font(document)

    headline = script_data.get("headline", "ব্রেকিং রিল স্ক্রিপ্ট")
    full_script = script_data.get("full_script", "")
    word_count = script_data.get("word_count", len(full_script.split()))
    scenes = script_data.get("scenes", [])

    # ১. শিরোনাম
    heading = document.add_heading(f"রিল স্ক্রিপ্ট — {date_label}", level=0)
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER

    sub_title = document.add_paragraph()
    sub_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    s_run = sub_title.add_run(headline)
    s_run.bold = True
    s_run.font.size = Pt(14)
    s_run.font.color.rgb = RGBColor(180, 20, 20)

    # ২. মেটা
    meta = document.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    m_run = meta.add_run(
        f"মোট শব্দ: {word_count} | আনুমানিক সময়: ৪৫-৬০ সেকেন্ড | "
        f"ধরন: পেশাদার তথ্যবহুল রিল ভয়েস-ওভার"
    )
    m_run.italic = True
    m_run.font.size = Pt(10)
    m_run.font.color.rgb = RGBColor(90, 90, 90)

    # ৩. সম্পূর্ণ ভয়েস-ওভার টেক্সট
    document.add_heading("সম্পূর্ণ ভয়েস-ওভার স্ক্রিপ্ট (একটানা পড়ার জন্য):", level=1)
    full_p = document.add_paragraph()
    f_run = full_p.add_run(full_script)
    f_run.font.size = Pt(12.5)

    # ৪. দৃশ্যভিত্তিক বিভাজন (Video Creator Agent-এর জন্য)
    document.add_heading("দৃশ্যভিত্তিক স্ক্রিপ্ট ও ইমেজ ম্যাপিং:", level=1)
    for sc in scenes:
        p = document.add_paragraph()
        run_label = p.add_run(f"দৃশ্য {sc.get('scene_num', 1)} [ছবি #{sc.get('image_index', 1)}]: ")
        run_label.bold = True
        run_label.font.size = Pt(11)
        run_label.font.color.rgb = RGBColor(0, 102, 204)
        run_txt = p.add_run(sc.get("text", ""))
        run_txt.font.size = Pt(11)

    document.save(path)
    return path


def write_json_script(script_data, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(script_data, fh, ensure_ascii=False, indent=2)
    return path
