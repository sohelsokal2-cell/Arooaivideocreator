"""
Youtube Page Manage Agent — Groq AI Brain
==========================================
YouTube Shorts-এর জন্য AI-powered content strategy:
  - Viral Title (A/B variants)
  - SEO-optimized Description
  - Tag cloud (500 chars max)
  - Chapter markers
  - Pinned comment
  - Comment reply templates
  - Thumbnail text suggestion
  - Peak posting hours (YouTube analytics-based)
  - Category & audience targeting
  - Engagement score

নোট: নিজস্ব YT_GROQ_API_KEY ব্যবহার করে।
"""

import json
import os
import re
import requests
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# ──────────────────────────────────────────────────────────────────────────────
# Env Loader
# ──────────────────────────────────────────────────────────────────────────────
def load_env():
    env_path = os.path.join(BASE_DIR, ".env")
    if not os.path.exists(env_path):
        return
    # YT-specific keys সবসময় force-load হবে (pipeline-এ অন্য agent-এর key override এড়াতে)
    YT_FORCE_KEYS = {
        "YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN",
        "YT_CHANNEL_ID", "YT_GROQ_API_KEY", "YT_GROQ_MODEL",
        "YT_PUBLISH_MODE", "YT_AUTO_ADD_SHORTS_TAG", "YT_AUTO_PIN_COMMENT",
    }
    with open(env_path, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and (k in YT_FORCE_KEYS or k not in os.environ):
                os.environ[k] = v


load_env()

API_URL = "https://api.groq.com/openai/v1/chat/completions"

# ──────────────────────────────────────────────────────────────────────────────
# Category → YouTube Tags Mapping
# ──────────────────────────────────────────────────────────────────────────────
CATEGORY_TAGS = {
    "রাজনীতি": [
        "Bangladesh Politics", "BangladeshNews", "RajnitiiBD", "BangaliiFacts",
        "BreakingNews", "Bangladesh", "Shorts", "bdnews", "PoliticsUpdate",
        "DhakaNews", "বাংলাদেশ রাজনীতি", "ব্রেকিং নিউজ",
    ],
    "অপরাধ": [
        "CrimeBD", "BreakingCrime", "BangaliiFacts", "Bangladesh", "Shorts",
        "CrimeAlert", "bdnews", "ViralNews", "বাংলাদেশ অপরাধ",
    ],
    "দুর্ঘটনা": [
        "AccidentBD", "RoadSafety", "BangaliiFacts", "Bangladesh", "Shorts",
        "BreakingNewsBD", "bdnews", "দুর্ঘটনা বাংলাদেশ",
    ],
    "আন্তর্জাতিক": [
        "WorldNews", "InternationalNews", "BangaliiFacts", "GlobalNews",
        "Bangladesh", "Shorts", "bdnews", "আন্তর্জাতিক খবর",
    ],
    "বিনোদন": [
        "EntertainmentBD", "Dhallywood", "BangaliiFacts", "BanglaEntertainment",
        "Viral", "Shorts", "bdceleb", "BanglaNews", "বিনোদন",
    ],
    "খেলাধুলা": [
        "SportsBD", "CricketBD", "BangaliiFacts", "BCB", "Football",
        "Shorts", "SportsUpdate", "bdcricket", "বাংলাদেশ ক্রিকেট",
    ],
    "default": [
        "BangaliiFacts", "Bangladesh", "BreakingNewsBD", "Shorts", "bdnews",
        "Viral", "BanglaNews", "TodayNews", "LatestNews", "বাংলা খবর",
    ],
}

# ──────────────────────────────────────────────────────────────────────────────
# Peak Hours per Category (YouTube-specific)
# ──────────────────────────────────────────────────────────────────────────────
YT_PEAK_HOURS = {
    "রাজনীতি":    "দুপুর ১২টা - ২টা  |  রাত ৯টা - ১১টা",
    "অপরাধ":      "সকাল ৮টা - ১০টা  |  বিকেল ৬টা - ৮টা",
    "দুর্ঘটনা":   "সকাল ৯টা - ১১টা  |  সন্ধ্যা ৭টা - ৯টা",
    "আন্তর্জাতিক":"দুপুর ২টা - ৪টা  |  রাত ১০টা - ১২টা",
    "বিনোদন":     "বিকেল ৪টা - ৭টা  |  রাত ৯টা - ১১টা",
    "খেলাধুলা":   "দুপুর ১২টা - ২টা  |  রাত ৮টা - ১০টা",
    "default":     "বিকেল ৫টা - সন্ধ্যা ৭টা  |  রাত ৯টা - ১১টা",
}

# ──────────────────────────────────────────────────────────────────────────────
# YouTube Category ID mapping
# ──────────────────────────────────────────────────────────────────────────────
YT_CATEGORY_IDS = {
    "রাজনীতি": 25,       # News & Politics
    "অপরাধ": 25,
    "দুর্ঘটনা": 25,
    "আন্তর্জাতিক": 25,
    "বিনোদন": 24,         # Entertainment
    "খেলাধুলা": 17,       # Sports
    "default": 25,
}

# ──────────────────────────────────────────────────────────────────────────────
# System Prompt
# ──────────────────────────────────────────────────────────────────────────────
BRAIN_SYSTEM_PROMPT = """\
You are the AI YouTube Growth Strategist for 'বাঙালি ফ্যাক্টস' (@bangaliifacts) YouTube channel.
You analyze breaking news Shorts content and devise maximum viral growth strategies for YouTube Shorts.

Return ONLY ONE valid JSON object (no markdown, no code fences):

{
  "title": "Primary viral YouTube Shorts title (max 100 chars, Bengali + English keywords, emotional hook)",
  "title_b": "A/B variant title (different angle, still catchy, max 100 chars)",
  "description": "Full SEO description (200-400 words): first 2 lines = hook+keywords, then story detail, then CTA 'সত্য খবরের জন্য চ্যানেলটি Subscribe করুন @bangaliifacts', then #Shorts and other hashtags",
  "tags": ["tag1", "tag2", ...],
  "pinned_comment": "High-engagement first comment to spark debate (Bengali, emoji, question)",
  "comment_replies": ["Reply 1", "Reply 2", "Reply 3", "Reply 4", "Reply 5"],
  "thumbnail_text": "Short punchy text for thumbnail overlay (max 6 words, Bengali)",
  "chapters": "00:00 ভূমিকা\\n00:05 মূল ঘটনা\\n00:30 বিস্তারিত\\n00:50 সমাপ্তি",
  "hook_analysis": "One sentence: why this will go viral on YouTube",
  "recommended_peak_hours": "Best upload times (Bengali)",
  "category": "One of: রাজনীতি | অপরাধ | দুর্ঘটনা | আন্তর্জাতিক | বিনোদন | খেলাধুলা | জাতীয়",
  "sensitivity_level": "Normal | Moderate | High",
  "sensitivity_note": "Moderation note or empty string",
  "estimated_reach_potential": "Low | Medium | Medium-High | High | Viral",
  "engagement_score": 85
}

Rules:
- title MUST be under 100 characters.
- tags list must have 10-15 items (mix Bengali + English).
- description must include #Shorts as a hashtag.
- If sensitivity is High, soften title/description to avoid YouTube demonetization.
- engagement_score is integer 0-100.
- Return ONLY the JSON.
"""


# ──────────────────────────────────────────────────────────────────────────────
# Helper
# ──────────────────────────────────────────────────────────────────────────────
def _extract_json(text: str) -> dict | None:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    s = text.find("{")
    e = text.rfind("}")
    if s != -1 and e != -1:
        try:
            return json.loads(text[s:e + 1])
        except json.JSONDecodeError:
            pass
    return None


def get_tags_for_category(category: str) -> list:
    for key in CATEGORY_TAGS:
        if key in category:
            return CATEGORY_TAGS[key]
    return CATEGORY_TAGS["default"]


def get_peak_hours(category: str) -> str:
    for key in YT_PEAK_HOURS:
        if key in category:
            return YT_PEAK_HOURS[key]
    return YT_PEAK_HOURS["default"]


def get_yt_category_id(category: str) -> int:
    for key in YT_CATEGORY_IDS:
        if key in category:
            return YT_CATEGORY_IDS[key]
    return YT_CATEGORY_IDS["default"]


# ──────────────────────────────────────────────────────────────────────────────
# Main Brain Function
# ──────────────────────────────────────────────────────────────────────────────
def analyze_and_optimize_video(headline: str, script_text: str = "") -> dict:
    """
    Groq AI Brain দিয়ে YouTube Shorts-এর সম্পূর্ণ কন্টেন্ট প্যাকেজ তৈরি করে।
    """
    load_env()
    key = os.environ.get("YT_GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))
    if not key:
        raise RuntimeError("YT_GROQ_API_KEY পাওয়া যায়নি। .env ফাইলে বসান।")

    model = os.environ.get("YT_GROQ_MODEL", os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b"))
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    user_prompt = f"""খবরের শিরোনাম: {headline}

রিল স্ক্রিপ্ট:
{script_text[:800] if script_text else '(স্ক্রিপ্ট পাওয়া যায়নি)'}

বাঙালি ফ্যাক্টস (@bangaliifacts) YouTube Shorts-এর জন্য সম্পূর্ণ ভাইরাল কন্টেন্ট প্যাকেজ JSON আকারে দিন।"""

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": BRAIN_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.70,
        "max_tokens": 2000,
    }

    last_error = None
    for attempt in range(1, 4):
        try:
            print(f"      🧠 Groq Brain YouTube অ্যানালাইসিস (attempt {attempt}/3)...")
            res = requests.post(API_URL, headers=headers, json=payload, timeout=35)
            if res.status_code == 200:
                content = res.json()["choices"][0]["message"]["content"]
                result = _extract_json(content)
                if result:
                    category = result.get("category", "default")
                    result.setdefault("tag_pool", get_tags_for_category(category))
                    result.setdefault("yt_category_id", get_yt_category_id(category))
                    if not result.get("recommended_peak_hours"):
                        result["recommended_peak_hours"] = get_peak_hours(category)
                    result["_model_used"] = model
                    # Ensure #Shorts in tags
                    tags = result.get("tags", [])
                    if "Shorts" not in tags and "#Shorts" not in tags:
                        tags.append("Shorts")
                    result["tags"] = tags
                    return result
                else:
                    last_error = "JSON parse ব্যর্থ"
            else:
                last_error = f"HTTP {res.status_code}: {res.text[:200]}"
        except Exception as exc:
            last_error = str(exc)
        if attempt < 3:
            time.sleep(2 * attempt)

    print(f"      ⚠️  Groq Brain সতর্কতা (3 attempt পর ফলব্যাক): {last_error}")
    return _build_fallback(headline)


# ──────────────────────────────────────────────────────────────────────────────
# Fallback
# ──────────────────────────────────────────────────────────────────────────────
def _build_fallback(headline: str) -> dict:
    short_title = headline[:97] + "..." if len(headline) > 100 else headline
    tags = CATEGORY_TAGS["default"]
    description = (
        f"{headline} | বাঙালি ফ্যাক্টস\n\n"
        "আজকের সবচেয়ে গুরুত্বপূর্ণ খবর নিয়ে আমাদের বিশেষ Shorts প্রতিবেদন। "
        "সত্য ও যাচাইকৃত তথ্যের জন্য চ্যানেলটি Subscribe করুন।\n\n"
        "✅ সত্য খবরের জন্য চ্যানেলটি Subscribe করুন @bangaliifacts\n\n"
        "#Shorts #BangaliiFacts #Bangladesh #BreakingNews #bdnews"
    )
    return {
        "title": short_title,
        "title_b": f"🚨 {short_title[:90]}",
        "description": description,
        "tags": tags,
        "pinned_comment": "এই খবর সম্পর্কে আপনার মতামত কী? কমেন্টে জানান! 👇",
        "comment_replies": [
            "ধন্যবাদ আপনার মতামতের জন্য! 🙏",
            "আরও আপডেটের জন্য চ্যানেলটি Subscribe করুন।",
            "আপনার কথা একদম সত্যি! শেয়ার করুন সবাইকে জানান।",
            "তথ্যটি গুরুত্বপূর্ণ। Subscribe করুন @bangaliifacts",
            "আপনার প্রশ্নের উত্তর শীঘ্রই আসছে! নজর রাখুন। 👀",
        ],
        "thumbnail_text": "ব্রেকিং নিউজ",
        "chapters": "00:00 ভূমিকা\n00:05 মূল ঘটনা\n00:40 বিস্তারিত\n00:55 সমাপ্তি",
        "hook_analysis": "ব্রেকিং নিউজ ফরম্যাট দ্রুত শেয়ার করতে উৎসাহিত করে।",
        "recommended_peak_hours": YT_PEAK_HOURS["default"],
        "category": "জাতীয়",
        "sensitivity_level": "Normal",
        "sensitivity_note": "",
        "estimated_reach_potential": "Medium-High",
        "engagement_score": 70,
        "tag_pool": tags,
        "yt_category_id": 25,
        "_model_used": "fallback",
    }

