import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import gemini_api

POST_SYSTEM_PROMPT = """You are a viral social media strategist and content creator for 'বাঙালি ফ্যাক্টস' (@bangaliifacts) Facebook and YouTube Shorts / Reels.
Your task is to take the news story and reel script, and generate engaging, viral, high-CTR metadata in Bengali.

STRICT RULES:
1. Do NOT mention any newspaper or source names (e.g., Prothom Alo, Daily Star).
2. All titles and descriptions must be in natural, engaging Bengali.
3. Include high-converting click-worthy hooks that encourage curiosity, comments, and shares.
4. Output MUST be valid JSON adhering strictly to the schema provided.

Output Schema:
{
  "titles": [
    "কৌতূহলোদ্দীপক ভাইরাল টাইটেল ১ (ইমোজি সহ)",
    "ব্রেকিং নিউজ স্টাইল টাইটেল ২",
    "প্রশ্নবোধক বা এনগেজিং টাইটেল ৩"
  ],
  "description": "ভিডিওটির মূল তথ্যের আকর্ষণীয় সংক্ষিপ্ত বিবরণী (৫০-৮০ শব্দ)। সাথে ফলো বা সাবস্ক্রাইব করার মৃদু কল-টু-অ্যাকশন।",
  "call_to_action": "আপনার কী মতামত? কমেন্টে জানান! নিয়মিত ব্রেকিং নিউজ ও অজানা তথ্য পেতে ফলো করুন @bangaliifacts",
  "hashtags": [
    "#BangaliiFacts",
    "#BreakingNews",
    "#Bangladesh",
    "#BangladeshNews",
    "#ViralReels",
    "#FacebookReels",
    "#Shorts",
    "#TrendingNews"
  ]
}
"""


def generate_post_metadata(headline, script_text, date_label=""):
    """
    Gemini AI দিয়ে সোশ্যাল মিডিয়ার ভাইরাল টাইটেল, ডেসক্রিপশন এবং হ্যাশট্যাগ তৈরি করে।
    """
    user_prompt = f"""খবরের বিষয়: {headline}
তারিখ: {date_label}

সম্পূর্ণ স্ক্রিপ্ট:
{script_text}

দয়া করে ফেসবুক রিল ও ইউটিউব শর্টসের জন্য ৩টি ক্যাচি টাইটেল, ৫০-৮০ শব্দের বিবরণী (description), কল-টু-অ্যাকশন এবং ১৫-২০টি ট্রেন্ডিং হ্যাশট্যাগ তৈরি করে JSON আকারে দিন।"""

    try:
        data = gemini_api.ask_gemini(
            user_content=user_prompt,
            system_prompt=POST_SYSTEM_PROMPT,
            temperature=0.7,
            max_output_tokens=700
        )
        return data
    except Exception as exc:
        print(f"      ⚠️  সোশ্যাল মিডিয়া পোস্ট জেনারেশন ত্রুটি: {exc} — ডিফল্ট মেটাডাটা তৈরি করা হচ্ছে")
        clean_headline = headline.replace('"', '').replace("'", "")
        return {
            "titles": [
                f"🚨 {clean_headline} | বাঙালি ফ্যাক্টস",
                f"কী ঘটতে যাচ্ছে? {clean_headline}",
                f"ব্রেকিং নিউজ: {clean_headline}!"
            ],
            "description": f"{clean_headline}। দেশের সর্বশেষ ব্রেকিং খবর এবং সত্য ঘটনা জানতে চোখ রাখুন বাঙালি ফ্যাক্টস-এ। লাইক ও ফলো দিয়ে সাথেই থাকুন!",
            "call_to_action": "আপনার মতামত কমেন্টে জানান! আরও জানতে ফলো করুন @bangaliifacts",
            "hashtags": [
                "#BangaliiFacts",
                "#BanglaNews",
                "#Bangladesh",
                "#BreakingNews",
                "#ViralNews",
                "#Shorts",
                "#Reels"
            ]
        }


def format_post_text(post_data, headline=""):
    """
    সোশ্যাল মিডিয়ায় সরাসরি কপি-পেস্ট উপযোগী ফরম্যাট তৈরি করে।
    """
    lines = []
    lines.append("═══════════════════════════════════════════════════════════")
    lines.append("  বাঙালি ফ্যাক্টস (@bangaliifacts) — সোশ্যাল মিডিয়া পোস্ট মেটাডাটা")
    lines.append("═══════════════════════════════════════════════════════════\n")

    lines.append("📌 প্রস্তাবিত টাইটেল (Title Options):")
    for idx, t in enumerate(post_data.get("titles", []), 1):
        lines.append(f"  {idx}. {t}")

    lines.append("\n📝 ডেসক্রিপশন (Description):")
    lines.append(post_data.get("description", ""))

    lines.append("\n📢 কল-টু-অ্যাকশন (Call to Action):")
    lines.append(post_data.get("call_to_action", "ফলো করুন @bangaliifacts"))

    lines.append("\n🏷️ হ্যাশট্যাগ (Hashtags):")
    tags = post_data.get("hashtags", [])
    lines.append(" ".join(tags))
    lines.append("\n═══════════════════════════════════════════════════════════")

    return "\n".join(lines)

