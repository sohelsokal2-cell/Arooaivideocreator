import json
import os
import re
from datetime import datetime, timedelta, timezone

from docx import Document

DHAKA_TZ = timezone(timedelta(hours=6))
DATE_PAT = re.compile(r"\d{4}-\d{2}-\d{2}")
ITEM_START = re.compile(r"^(\d{1,3})\.\s+(.*)$")


def _clean(text):
    return re.sub(r"\s+", " ", (text or "")).strip()


def _date_from_name(path):
    match = DATE_PAT.search(os.path.basename(path))
    return match.group(0) if match else ""


def find_latest_input(base_dir, collector_dir=None):
    """
    সর্বশেষ story_data.json বা news_*.docx খুঁজে বের করে।
    """
    search_dirs = []
    if collector_dir and os.path.isdir(collector_dir):
        # 1. Collector-এর latest ফোল্ডার সবচেয়ে আগে অগ্রাধিকার পাবে
        latest_folder = os.path.join(collector_dir, "output", "latest")
        if os.path.isdir(latest_folder):
            json_file = os.path.join(latest_folder, "story_data.json")
            if os.path.exists(json_file):
                return json_file
        search_dirs.append(os.path.join(collector_dir, "output"))
        search_dirs.append(collector_dir)

    search_dirs.append(base_dir)

    # অন্য ফোল্ডারগুলোতে খোঁজা
    candidates = []
    for folder in search_dirs:
        if not os.path.isdir(folder):
            continue
        for root, _dirs, files in os.walk(folder):
            if "__pycache__" in root or ".system_generated" in root:
                continue
            for name in files:
                if name.startswith("~$"):
                    continue
                lower = name.lower()
                if lower == "story_data.json":
                    candidates.append((2, os.path.join(root, name)))
                elif lower.endswith(".docx") and "news_" in lower:
                    candidates.append((1, os.path.join(root, name)))

    if not candidates:
        return ""

    # অগ্রাধিকার: JSON > DOCX, এবং সাম্প্রতিক তারিখ ও মডিফিকেশন সময়
    candidates.sort(
        key=lambda item: (item[0], _date_from_name(item[1]), os.path.getmtime(item[1])),
        reverse=True,
    )
    return candidates[0][1]


def parse_news_docx(path):
    """Fallback: DOCX ডকুমেন্ট থেকে তথ্য পড়া।"""
    document = Document(path)
    lines = [_clean(p.text) for p in document.paragraphs if _clean(p.text)]
    date_label = _date_from_name(path) or datetime.now(DHAKA_TZ).strftime("%Y-%m-%d")

    headline = ""
    synthesis = ""
    sources = []
    current_source = None

    for line in lines:
        if line.startswith("মূল খবর:"):
            headline = line.replace("মূল খবর:", "").strip()
        elif line.startswith("ঘটনার সার্বিক বিবরণ:"):
            synthesis = line.replace("ঘটনার সার্বিক বিবরণ:", "").strip()
        elif re.match(r"^\d{2}\.\s+\[", line):
            if current_source:
                sources.append(current_source)
            m = re.match(r"^\d{2}\.\s+\[([^\]]+)\]\s*(.*)$", line)
            site = m.group(1) if m else "সংবাদমাধ্যম"
            title = m.group(2) if m else line
            current_source = {
                "site": site,
                "title": title,
                "body": "",
                "key_points": [],
            }
        elif current_source:
            if line.startswith("প্রতিবেদনের মূল অংশ:"):
                continue
            if line.startswith("ছবি উৎস:"):
                continue
            current_source["body"] += (" " + line)

    if current_source:
        sources.append(current_source)

    return {
        "headline": headline or (lines[0] if lines else "ব্রেকিং সংবাদ"),
        "overall_synthesis": synthesis,
        "date": date_label,
        "run_id": 1,
        "sources": sources,
    }


def load_story_input(path=None, collector_dir=None, base_dir=None):
    """
    নির্দিষ্ট পাথ বা স্বয়ংক্রিয়ভাবে সর্বশেষ ইনপুট লোড করে স্টোরি ডিকশনারি প্রদান করে।
    """
    resolved_path = path or find_latest_input(base_dir or os.getcwd(), collector_dir)
    if not resolved_path or not os.path.exists(resolved_path):
        raise FileNotFoundError("কোনো story_data.json বা news_*.docx পাওয়া যায়নি")

    if resolved_path.lower().endswith(".json"):
        with open(resolved_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return resolved_path, data

    # DOCX ফাইল হলে তার পাশে story_data.json আছে কিনা পরীক্ষা
    sibling_json = os.path.join(os.path.dirname(resolved_path), "story_data.json")
    if os.path.exists(sibling_json):
        with open(sibling_json, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return sibling_json, data

    # অন্যথায় DOCX পার্স করা
    data = parse_news_docx(resolved_path)
    return resolved_path, data
