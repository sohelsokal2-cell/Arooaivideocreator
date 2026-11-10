"""
Facebook Page Manage Agent — Groq AI Brain
===========================================
এই মডিউল Groq AI ব্যবহার করে ভাইরাল ফেসবুক রিল কন্টেন্ট স্ট্র্যাটেজি তৈরি করে।
Features:
  - ভাইরাল ক্যাপশন (Bengali + Emoji)
  - A/B Caption Variants
  - Pinned First Comment
  - Comment Reply Templates (5টি)
  - Instagram Caption Variant
  - YouTube Shorts Description
  - Dynamic Hashtag Intelligence
  - Peak Posting Hours Matrix
  - Sensitivity Auto-filter
  - Estimated Reach Potential

নোট: এই agent-এর নিজস্ব Groq API key ব্যবহার করে।
      News Collector Agent-এর key ব্যবহার হয় না।
"""

import json
import os
import re
import requests
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# ──────────────────────────────────────────────────────────────────────────────
# Environment Loader
# ──────────────────────────────────────────────────────────────────────────────
def load_env():
    env_path = os.path.join(BASE_DIR, ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v


load_env()

# ──────────────────────────────────────────────────────────────────────────────
# Groq API Config — Facebook Agent নিজস্ব key
# ──────────────────────────────────────────────────────────────────────────────
GROQ_API_KEY = os.environ.get("FB_GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))
GROQ_MODEL   = os.environ.get("FB_GROQ_MODEL", os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b"))
API_URL      = "https://api.groq.com/openai/v1/chat/completions"

# ──────────────────────────────────────────────────────────────────────────────
# Category → Hashtag Mapping (Dynamic Hashtag Intelligence)
# ──────────────────────────────────────────────────────────────────────────────
CATEGORY_HASHTAGS = {
    "রাজনীতি": [
        "#BangladeshPolitics", "#RajnitiiBD", "#BangaliiFacts",
        "#BreakingNewsBD", "#Bangladesh", "#ReelsFB", "#ViralReels",
        "#bdnews", "#PoliticsUpdate", "#DhakaNews",
    ],
    "অপরাধ": [
        "#CrimeBD", "#BreakingCrime", "#BangaliiFacts",
        "#Bangladesh", "#ReelsFB", "#CrimeAlert", "#bdnews",
        "#ViralNews", "#GunViolence", "#SafetyAlert",
    ],
    "দুর্ঘটনা": [
        "#AccidentBD", "#RoadSafety", "#BangaliiFacts",
        "#Bangladesh", "#BreakingNewsBD", "#bdnews", "#ReelsFB",
        "#ViralReels", "#AccidentAlert", "#EmergencyBD",
    ],
    "আন্তর্জাতিক": [
        "#WorldNews", "#InternationalNews", "#BangaliiFacts",
        "#GlobalNews", "#Bangladesh", "#ReelsFB", "#ViralReels",
        "#bdnews", "#InternationalPolitics", "#WorldUpdate",
    ],
    "বিনোদন": [
        "#EntertainmentBD", "#Dhallywood", "#BangaliiFacts",
        "#BanglaEntertainment", "#Viral", "#ReelsFB",
        "#ViralReels", "#bdceleb", "#BanglaNews", "#CelebBD",
    ],
    "খেলাধুলা": [
        "#SportsBD", "#CricketBD", "#BangaliiFacts",
        "#BCB", "#Football", "#ReelsFB", "#ViralReels",
        "#SportsUpdate", "#bdcricket", "#BangladeshCricket",
    ],
    "অর্থনীতি": [
        "#EconomyBD", "#BusinessBD", "#BangaliiFacts",
        "#FinanceBD", "#Bangladesh", "#ReelsFB", "#bdnews",
        "#MarketUpdate", "#EconomicNews", "#taka",
    ],
    "default": [
        "#BangaliiFacts", "#Bangladesh", "#BreakingNewsBD",
        "#ReelsFB", "#ViralReels", "#bdnews", "#Viral",
        "#BanglaNews", "#TodayNews", "#LatestNews",
    ],
}

# ──────────────────────────────────────────────────────────────────────────────
# Content Calendar — Peak Hours Per Category
# ──────────────────────────────────────────────────────────────────────────────
PEAK_HOURS_MATRIX = {
    "রাজনীতি":    "দুপুর ১২টা - ২টা  |  রাত ৮টা - ১০টা",
    "অপরাধ":      "সকাল ৮টা - ১০টা  |  বিকেল ৫টা - ৭টা",
    "দুর্ঘটনা":   "সকাল ৯টা - ১১টা  |  সন্ধ্যা ৬টা - ৮টা",
    "আন্তর্জাতিক":"দুপুর ১টা - ৩টা  |  রাত ৯টা - ১১টা",
    "বিনোদন":     "বিকেল ৪টা - ৬টা  |  রাত ৯টা - ১১টা",
    "খেলাধুলা":   "দুপুর ১২টা - ২টা  |  রাত ৮টা - ১০টা",
    "অর্থনীতি":   "সকাল ৯টা - ১১টা  |  দুপুর ১২টা - ২টা",
    "default":     "সন্ধ্যা ৭:৩০টা - রাত ৯:৩০টা",
}

# ──────────────────────────────────────────────────────────────────────────────
# System Prompt — Enhanced Brain
# ──────────────────────────────────────────────────────────────────────────────
BRAIN_SYSTEM_PROMPT = """\
You are the AI Social Media Strategist and Viral Growth Director for 'বাঙালি ফ্যাক্টস' (@bangaliifacts) Facebook page.
You analyze breaking news reel content and devise maximum viral growth strategies for Facebook Reels.

Your FULL output must be ONE valid JSON object (no markdown, no code fences) with these exact keys:

{
  "caption": "Primary viral Facebook Reel caption with emoji hooks, 2-3 bullet highlights, curiosity question, CTA: 'সত্য ও ব্রেকিং খবরের জন্য পেজটি ফলো করুন @bangaliifacts', and 10-15 hashtags",
  "caption_b": "Alternative A/B test caption (different opening hook and tone, still viral and Bengali)",
  "first_comment": "High-engagement pinned comment that sparks debate and replies (Bengali, emojis, question-based)",
  "comment_replies": ["Reply 1 to drop on engaging comments", "Reply 2", "Reply 3", "Reply 4", "Reply 5"],
  "instagram_caption": "Shorter caption optimized for Instagram Reels (max 2200 chars, same news, slightly different CTA)",
  "youtube_description": "YouTube Shorts description (120-200 words, SEO keywords in first line, Bengali+English mix)",
  "hook_analysis": "One sentence explaining WHY this content will go viral (what emotional trigger)",
  "recommended_peak_hours": "Best times to post (Bengali)",
  "category": "One of: রাজনীতি | অপরাধ | দুর্ঘটনা | আন্তর্জাতিক | বিনোদন | খেলাধুলা | অর্থনীতি | জাতীয়",
  "sensitivity_level": "Normal | Moderate | High",
  "sensitivity_note": "Brief note if content needs moderation (empty string if Normal)",
  "estimated_reach_potential": "Low | Medium | Medium-High | High | Viral",
  "engagement_score": 85
}

Rules:
- engagement_score is 0-100 integer estimating viral potential.
- If sensitivity_level is High, auto-soften the caption to avoid community guideline violations.
- caption MUST end with the hashtags on new lines.
- All Bengali text must use proper Unicode.
- Return ONLY the JSON object. No extra text.
"""


# ──────────────────────────────────────────────────────────────────────────────
# Helper: Extract JSON from Response
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


# ──────────────────────────────────────────────────────────────────────────────
# Helper: Get Dynamic Hashtags
# ──────────────────────────────────────────────────────────────────────────────
def get_hashtags_for_category(category: str) -> str:
    for key in CATEGORY_HASHTAGS:
        if key in category:
            return "\n".join(CATEGORY_HASHTAGS[key])
    return "\n".join(CATEGORY_HASHTAGS["default"])


# ──────────────────────────────────────────────────────────────────────────────
# Helper: Get Peak Hours
# ──────────────────────────────────────────────────────────────────────────────
def get_peak_hours(category: str) -> str:
    for key in PEAK_HOURS_MATRIX:
        if key in category:
            return PEAK_HOURS_MATRIX[key]
    return PEAK_HOURS_MATRIX["default"]


# ──────────────────────────────────────────────────────────────────────────────
# Main Brain Function
# ──────────────────────────────────────────────────────────────────────────────
def analyze_and_optimize_post(headline: str, script_text: str = "") -> dict:
    """
    Groq AI Brain দিয়ে সম্পূর্ণ সোশ্যাল মিডিয়া স্ট্র্যাটেজি তৈরি করে।
    Returns enriched strategy dict with all platform captions, hashtags, reply templates, etc.
    """
    load_env()
    key = os.environ.get("FB_GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))
    if not key:
        raise RuntimeError("FB_GROQ_API_KEY (বা GROQ_API_KEY) পাওয়া যায়নি। .env ফাইলে বসান।")

    model = os.environ.get("FB_GROQ_MODEL", os.environ.get("GROQ_MODEL", GROQ_MODEL))

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    user_prompt = f"""খবরের শিরোনাম: {headline}

রিল স্ক্রিপ্ট (সারসংক্ষেপ):
{script_text[:800] if script_text else '(স্ক্রিপ্ট পাওয়া যায়নি)'}

বাঙালি ফ্যাক্টস (@bangaliifacts) ফেসবুক পেজের রিল পাবলিশিংয়ের জন্য সম্পূর্ণ ভাইরাল কন্টেন্ট প্যাকেজ JSON আকারে দিন।"""

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
    for attempt in range(1, 4):  # 3 retries
        try:
            print(f"      🧠 Groq Brain অ্যানালাইসিস (attempt {attempt}/3)...")
            res = requests.post(API_URL, headers=headers, json=payload, timeout=35)
            if res.status_code == 200:
                content = res.json()["choices"][0]["message"]["content"]
                result = _extract_json(content)
                if result:
                    # Enrich with deterministic data
                    category = result.get("category", "default")
                    result.setdefault("hashtag_pool", get_hashtags_for_category(category))
                    if not result.get("recommended_peak_hours"):
                        result["recommended_peak_hours"] = get_peak_hours(category)
                    result["_model_used"] = model
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
# Fallback Strategy
# ──────────────────────────────────────────────────────────────────────────────
def _build_fallback(headline: str) -> dict:
    hashtags = "\n".join(CATEGORY_HASHTAGS["default"])
    caption = (
        f"🚨 {headline}\n\n"
        "▶️ ঘটনার সত্যতা ও বিস্তারিত নিয়ে আজকের বিশেষ রিল প্রতিবেদন।\n"
        "সম্পূর্ণ ভিডিওটি দেখুন এবং আপনার মতামত জানান।\n\n"
        "👉 সত্য ও ব্রেকিং খবরের জন্য পেজটি ফলো করুন @bangaliifacts\n\n"
        f"{hashtags}"
    )
    return {
        "caption": caption,
        "caption_b": f"⚡ এইমাত্র জানা গেল: {headline}\n\n"
                     "বিস্তারিত দেখুন। ভিডিওটি শেয়ার করুন সত্য ছড়িয়ে দিন!\n\n"
                     "🔔 ফলো করুন @bangaliifacts\n\n" + hashtags,
        "first_comment": "এই বিষয়ে আপনার কী অভিমত? সঠিক তথ্য প্রচারে ভিডিওটি শেয়ার করুন!",
        "comment_replies": [
            "ধন্যবাদ আপনার মতামতের জন্য! 🙏",
            "ঠিকই বলেছেন। আরও আপডেটের জন্য পেজটি ফলো করুন।",
            "আপনার কথা একদম সত্যি! শেয়ার করুন সবাইকে জানান।",
            "তথ্যটি গুরুত্বপূর্ণ। ফলো করুন @bangaliifacts",
            "আপনার প্রশ্নের উত্তর শীঘ্রই আসছে! নজর রাখুন। 👀",
        ],
        "instagram_caption": f"🚨 {headline}\n\nবিস্তারিত ভিডিওতে। ফলো করুন @bangaliifacts\n\n"
                              "#BangaliiFacts #Bangladesh #BreakingNews",
        "youtube_description": (
            f"{headline} | বাঙালি ফ্যাক্টস\n\n"
            "আজকের সবচেয়ে গুরুত্বপূর্ণ খবর নিয়ে আমাদের বিশেষ ভিডিও প্রতিবেদন। "
            "সত্য ও যাচাইকৃত তথ্যের জন্য চ্যানেলটি সাবস্ক্রাইব করুন।\n\n"
            "#BangaliiFacts #Bangladesh #BreakingNews #bdnews"
        ),
        "hook_analysis": "ব্রেকিং নিউজ ফরম্যাটে জরুরি তথ্য মানুষকে দ্রুত শেয়ার করতে উৎসাহিত করে।",
        "recommended_peak_hours": PEAK_HOURS_MATRIX["default"],
        "category": "জাতীয়",
        "sensitivity_level": "Normal",
        "sensitivity_note": "",
        "estimated_reach_potential": "Medium-High",
        "engagement_score": 70,
        "hashtag_pool": hashtags,
        "_model_used": "fallback",
    }
