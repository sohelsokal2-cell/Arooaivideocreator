import json
import os
import re
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(BASE_DIR, "history.json")

STOPWORDS = set("""এবং ও বা কিন্তু তবে থেকে জন্য দিয়ে নিয়ে না হয় হয়ে হবে করে করা করেন এর
এই সেই তার তাদের তিনি তিনির আর আমি আমাদের আপনি মধ্যে পর পর্যন্ত কী যে কোন কোনো একটি
একটা একটির সঙ্গে সাথে পরে আগে মতো হিসেবে দেওয়া দেয়া নিজে বলে বলেন বলা the a an of to in on for and or""".split())


def _tokens(text):
    words = re.findall(r"[\w\u0980-\u09FF]+", (text or "").lower())
    return {w for w in words if len(w) > 1 and w not in STOPWORDS}


def _similarity(a, b):
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))


def load_history():
    if not os.path.exists(HISTORY_FILE):
        return {}
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:
        print(f"[history] সতর্কবার্তা: history.json পড়া যায়নি ({exc}), নতুন করে শুরু হচ্ছে")
        return {}


def save_history(history):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as fh:
            json.dump(history, fh, ensure_ascii=False, indent=2)
    except Exception as exc:
        print(f"[history] ত্রুটি: history.json সেভ করা যায়নি ({exc})")


def is_already_covered_today(title, summary, today_str, threshold=0.55):
    history = load_history()
    today_records = history.get(today_str, [])
    if not today_records:
        return False

    for rec in today_records:
        rec_headline = rec.get("headline", "")
        rec_topic = rec.get("topic", "")
        rec_text = rec_headline + " " + rec_topic

        # Token similarity check
        if _similarity(title, rec_headline) >= threshold:
            return True
        if _similarity(title, rec_topic) >= threshold:
            return True
        if summary and _similarity(summary, rec_text) >= threshold:
            return True

        # Check keywords overlap if present
        rec_keywords = set(rec.get("keywords", []))
        if rec_keywords:
            cand_tokens = _tokens(title + " " + (summary or ""))
            if len(rec_keywords & cand_tokens) >= max(2, int(len(rec_keywords) * 0.6)):
                return True

    return False


def get_today_run_count(today_str):
    history = load_history()
    return len(history.get(today_str, []))


def record_story(today_str, run_info):
    history = load_history()
    if today_str not in history:
        history[today_str] = []
    history[today_str].append(run_info)
    save_history(history)

