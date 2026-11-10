import json
import os
import re
from datetime import datetime, timedelta, timezone

from docx import Document

DATE_PAT = re.compile(r"\d{4}-\d{2}-\d{2}")
DHAKA_TZ = timezone(timedelta(hours=6))

SKIP_PREFIXES = (
    "লক্ষ্য সময়:",
    "শব্দ:",
    "উৎস:",
    "তৈরি:",
    "সংবাদ:",
    "ভয়েস-ওভার স্ক্রিপ্ট",
    "মোট শব্দ:",
)


def _clean(text):
    return re.sub(r"\s+", " ", (text or "")).strip()


def extract_date(path):
    match = DATE_PAT.search(os.path.basename(path))
    if match:
        return match.group(0)
    return datetime.now(DHAKA_TZ).strftime("%Y-%m-%d")


def find_latest_script(base_dir, writer_dir=None):
    """
    Writer Agent-এর latest ফোল্ডার বা সংশ্লিষ্ট ফোল্ডার থেকে সর্বশেষ স্ক্রিপ্ট খুঁজে বের করে।
    """
    search_dirs = []
    if writer_dir and os.path.isdir(writer_dir):
        # 1. Writer Agent-এর output/latest ফোল্ডারকে সর্বোচ্চ অগ্রাধিকার দেওয়া
        latest_folder = os.path.join(writer_dir, "output", "latest")
        if os.path.isdir(latest_folder):
            json_file = os.path.join(latest_folder, "script_data.json")
            if os.path.exists(json_file):
                return json_file
            txt_file = os.path.join(latest_folder, f"script_{datetime.now(DHAKA_TZ).strftime('%Y-%m-%d')}.txt")
            if os.path.exists(txt_file):
                return txt_file

        search_dirs.append(os.path.join(writer_dir, "output"))
        search_dirs.append(writer_dir)

    search_dirs.append(base_dir)

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
                if lower == "script_data.json":
                    candidates.append((3, os.path.join(root, name)))
                elif lower.endswith(".docx") and "script_" in lower:
                    candidates.append((2, os.path.join(root, name)))
                elif lower.endswith(".txt") and "script_" in lower:
                    candidates.append((1, os.path.join(root, name)))

    if not candidates:
        return ""

    candidates.sort(
        key=lambda item: (item[0], extract_date(item[1]), os.path.getmtime(item[1])),
        reverse=True,
    )
    return candidates[0][1]


def parse_script_json(path):
    """script_data.json থেকে রিল স্ক্রিপ্ট ও সিনভিত্তিক সেকশন পার্স করা।"""
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    date_label = data.get("date") or extract_date(path)
    headline = data.get("headline", "ব্রেকিং নিউজ")
    full_script = data.get("full_script", "")
    scenes = data.get("scenes", [])

    sections = []
    if scenes:
        for idx, sc in enumerate(scenes, start=1):
            sc_text = _clean(sc.get("text", ""))
            if not sc_text:
                continue
            img_idx = sc.get("image_index", idx)
            sections.append({
                "kind": "scene",
                "number": idx,
                "title": f"দৃশ্য {idx} (ছবি #{img_idx})",
                "filename_prefix": f"{idx:02d}_scene_{idx:02d}",
                "text": sc_text,
                "image_index": img_idx,
            })
    elif full_script:
        sections.append({
            "kind": "full",
            "number": 1,
            "title": headline,
            "filename_prefix": "01_full_reel",
            "text": full_script,
            "image_index": 1,
        })

    return date_label, sections, data


def parse_script_txt(path):
    """Fallback: .txt ফাইল থেকে পার্স করা।"""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    date_label = extract_date(path)
    lines = [_clean(line) for line in content.splitlines() if _clean(line)]
    sections = []

    # যদি SCENE BREAKDOWN থাকে
    scene_matches = re.findall(r"\[দৃশ্য\s*(\d+)\]\s*(?:\([^\)]*\))?\s*\n(.*?)(?=\n\[দৃশ্য|\Z)", content, re.S)
    if scene_matches:
        for num_str, txt in scene_matches:
            idx = int(num_str)
            clean_t = _clean(txt)
            if clean_t:
                sections.append({
                    "kind": "scene",
                    "number": idx,
                    "title": f"দৃশ্য {idx}",
                    "filename_prefix": f"{idx:02d}_scene_{idx:02d}",
                    "text": clean_t,
                    "image_index": idx,
                })
    else:
        # একটানা টেক্সট থাকলে
        reel_text = re.sub(r"^===.*?===+", "", content, flags=re.M).strip()
        sections.append({
            "kind": "full",
            "number": 1,
            "title": "রিল স্ক্রিপ্ট",
            "filename_prefix": "01_full_reel",
            "text": _clean(reel_text),
            "image_index": 1,
        })

    return date_label, sections, {"headline": "ব্রেকিং নিউজ", "date": date_label, "full_script": " ".join(s["text"] for s in sections)}


def parse_script(path):
    """
    যেকোনো ইনপুট ফরম্যাট (.json, .txt, .docx) স্বয়ংক্রিয়ভাবে পার্স করে সেকশন প্রদান করে।
    """
    if path.lower().endswith(".json"):
        return parse_script_json(path)

    # DOCX বা TXT হলে পাশে JSON আছে কিনা দেখা
    sibling_json = os.path.join(os.path.dirname(path), "script_data.json")
    if os.path.exists(sibling_json):
        return parse_script_json(sibling_json)

    if path.lower().endswith(".txt"):
        return parse_script_txt(path)

    # DOCX পার্সিং
    document = Document(path)
    paras = [_clean(p.text) for p in document.paragraphs if _clean(p.text)]
    date_label = extract_date(path)

    full_paras = []
    capture = False
    for p in paras:
        if "সম্পূর্ণ ভয়েস-ওভার স্ক্রিপ্ট" in p:
            capture = True
            continue
        if "দৃশ্যভিত্তিক স্ক্রিপ্ট" in p:
            capture = False
            continue
        if capture and not any(p.startswith(pref) for pref in SKIP_PREFIXES):
            full_paras.append(p)

    full_text = " ".join(full_paras) if full_paras else " ".join(paras[:5])
    sections = [{
        "kind": "full",
        "number": 1,
        "title": "রিল স্ক্রিপ্ট",
        "filename_prefix": "01_full_reel",
        "text": full_text,
        "image_index": 1,
    }]
    return date_label, sections, {"headline": "ব্রেকিং নিউজ", "date": date_label, "full_script": full_text}
