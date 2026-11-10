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
    style.font.size = Pt(11)
    rPr = style.element.get_or_add_rPr()
    rPr.rFonts.set(qn("w:cs"), "Nirmala UI")
    rPr.rFonts.set(qn("w:ascii"), "Nirmala UI")
    rPr.rFonts.set(qn("w:hAnsi"), "Nirmala UI")
    rPr.rFonts.set(qn("w:eastAsia"), "Nirmala UI")


def _add_hyperlink(paragraph, url, text):
    part = paragraph.part
    relationship_id = part.relate_to(
        url,
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
        is_external=True,
    )
    hyperlink = paragraph._element.makeelement(qn("w:hyperlink"), {})
    run = paragraph._element.makeelement(qn("w:r"), {})
    properties = paragraph._element.makeelement(qn("w:rPr"), {})
    color = paragraph._element.makeelement(qn("w:color"), {qn("w:val"): "1155CC"})
    underline = paragraph._element.makeelement(qn("w:u"), {qn("w:val"): "single"})
    properties.append(color)
    properties.append(underline)
    run.append(properties)
    text_node = paragraph._element.makeelement(qn("w:t"), {})
    text_node.text = text
    run.append(text_node)
    hyperlink.append(run)
    hyperlink.set(qn("r:id"), relationship_id)
    paragraph._element.append(hyperlink)
    return hyperlink


def _short_date(value):
    if not value:
        return ""
    return str(value).strip()[:40]


def write_consolidated_report(story_data, docx_path, json_path=None):
    """
    একক ব্রেকিং নিউজের উপর মাল্টি-সোর্স রিপোর্ট (.docx এবং .json) তৈরি করে।
    """
    # 1. JSON ফাইল সেভ করা (মেশিন রিডেবল ফরমেট)
    if json_path:
        os.makedirs(os.path.dirname(json_path), exist_ok=True)
        try:
            with open(json_path, "w", encoding="utf-8") as fh:
                json.dump(story_data, fh, ensure_ascii=False, indent=2)
        except Exception as exc:
            print(f"[report] JSON সেভ করতে সমস্যা: {exc}")

    # 2. DOCX ফাইল তৈরি করা
    os.makedirs(os.path.dirname(docx_path), exist_ok=True)
    document = Document()
    _set_bangla_font(document)

    headline = story_data.get("headline", "ব্রেকিং সংবাদ")
    date_label = story_data.get("date", "")
    run_id = story_data.get("run_id", 1)
    synthesis = story_data.get("overall_synthesis", "")
    sources = story_data.get("sources", [])

    # হেডিং
    heading = document.add_heading(f"সংবাদ বিশ্লেষণ — {date_label} (রান #{run_id:02d})", level=0)
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER

    main_title_p = document.add_paragraph()
    main_title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    main_run = main_title_p.add_run(f"মূল খবর: {headline}")
    main_run.bold = True
    main_run.font.size = Pt(14)
    main_run.font.color.rgb = RGBColor(160, 20, 20)

    # সার্বিক সমন্বিত সারসংক্ষেপ
    if synthesis:
        syn_p = document.add_paragraph()
        syn_run = syn_p.add_run(f"ঘটনার সার্বিক বিবরণ: {synthesis}")
        syn_run.italic = True
        syn_run.font.size = Pt(11.5)
        syn_run.font.color.rgb = RGBColor(40, 40, 40)

    intro = document.add_paragraph()
    intro.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = intro.add_run(
        f"মোট কভার করা সংবাদমাধ্যম: {len(sources)}টি | "
        f"লক্ষ্য: Writer Agent-এর জন্য বহু-উৎস দৃষ্টিকোণ ও সঠিক তথ্য"
    )
    run.font.size = Pt(9.5)
    run.font.color.rgb = RGBColor(90, 90, 90)

    document.add_heading("বিভিন্ন সংবাদমাধ্যমের প্রতিবেদন ও দৃষ্টিকোণ:", level=1)

    for idx, src in enumerate(sources, start=1):
        site_name = src.get("site", "সংবাদমাধ্যম")
        title = src.get("title") or headline

        # ১. সোর্স হেডিং
        title_para = document.add_paragraph()
        t_run = title_para.add_run(f"{idx:02d}. [{site_name}] {title}")
        t_run.bold = True
        t_run.font.size = Pt(12)

        # ২. মেটাডাটা
        meta = document.add_paragraph()
        m_run1 = meta.add_run(f"সংবাদপত্র: {site_name}")
        m_run1.font.size = Pt(9.5)
        m_run1.font.color.rgb = RGBColor(80, 80, 80)
        pub = _short_date(src.get("published"))
        if pub:
            m_run2 = meta.add_run(f"  |  প্রকাশ: {pub}")
            m_run2.font.size = Pt(9.5)
            m_run2.font.color.rgb = RGBColor(80, 80, 80)

        # ৩. লিংক
        if src.get("url"):
            link_para = document.add_paragraph()
            _add_hyperlink(link_para, src["url"], src["url"])

        # ৪. অ্যাঙ্গেল বা বিশেষ পয়েন্ট
        angle = src.get("angle")
        if angle:
            angle_p = document.add_paragraph()
            a_lbl = angle_p.add_run("দৃষ্টিকোণ / বিশেষ দিক: ")
            a_lbl.bold = True
            a_lbl.font.size = Pt(10.5)
            angle_p.add_run(angle).font.size = Pt(10.5)

        key_pts = src.get("key_points", [])
        if key_pts:
            for pt in key_pts:
                p_bullet = document.add_paragraph(style="List Bullet")
                p_bullet.add_run(pt).font.size = Pt(10.5)

        # ৫. বিস্তারিত মূল বিবরণ (Body)
        body = src.get("body")
        if body:
            body_p = document.add_paragraph()
            body_lbl = body_p.add_run("প্রতিবেদনের মূল অংশ:\n")
            body_lbl.bold = True
            body_lbl.font.size = Pt(10)
            body_p.add_run(body[:600] + ("..." if len(body) > 600 else "")).font.size = Pt(10)

        # ৬. ছবি
        img_path = src.get("image_path")
        if img_path and os.path.exists(img_path):
            try:
                document.add_picture(img_path, width=Inches(3.8))
                document.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.LEFT
                caption = document.add_paragraph()
                cap_run = caption.add_run(f"ছবি উৎস: {site_name} ({os.path.basename(img_path)})")
                cap_run.italic = True
                cap_run.font.size = Pt(8.5)
                cap_run.font.color.rgb = RGBColor(110, 110, 110)
            except Exception as exc:
                print(f"[report] ছবি সংযুক্ত করতে সমস্যা: {exc}")

        document.add_paragraph("").paragraph_format.space_after = Pt(6)

    document.add_page_break()
    foot = document.add_paragraph()
    foot_run = foot.add_run(
        f"তৈরি: {date_label} | Groq AI দিয়ে বিশ্লেষণ ও সমন্বিত | ছবি: images/ ফোল্ডারে সংরক্ষিত"
    )
    foot_run.italic = True
    foot_run.font.size = Pt(9)
    foot_run.font.color.rgb = RGBColor(120, 120, 120)

    document.save(docx_path)
    return docx_path
