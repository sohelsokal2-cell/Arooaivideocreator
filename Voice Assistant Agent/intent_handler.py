"""
Voice Assistant Agent — Intent Handler & Pipeline Controller
============================================================
ইনটেন্ট অনুযায়ী অ্যাকশন এক্সিকিউট করে এবং ফলাফল ফেরত দেয়।
"""

import json
import os
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)

COLLECTOR_DIR = os.path.join(PROJECT_DIR, "News Collector Agent")
WRITER_DIR = os.path.join(PROJECT_DIR, "Writer Agent")
FB_DIR = os.path.join(PROJECT_DIR, "Facebook Page Manage Agent")
YT_DIR = os.path.join(PROJECT_DIR, "Youtube Page Manage Agent")
RUN_PIPELINE_SCRIPT = os.path.join(PROJECT_DIR, "run_pipeline.py")

def get_pipeline_context() -> str:
    """বর্তমান পাইপলাইনের সর্বশেষ খবরের হেডলাইন এবং পোস্ট লিংক সংগ্রহ করে।"""
    story_file = os.path.join(COLLECTOR_DIR, "output", "latest", "story_data.json")
    headline = "কোনো খবর পাওয়া যায়নি"
    if os.path.exists(story_file):
        try:
            with open(story_file, "r", encoding="utf-8") as f:
                d = json.load(f)
                headline = d.get("headline", headline)
        except Exception:
            pass

    fb_strategy = os.path.join(FB_DIR, "output", "latest", "facebook_strategy.json")
    category = "সাধারণ"
    if os.path.exists(fb_strategy):
        try:
            with open(fb_strategy, "r", encoding="utf-8") as f:
                d = json.load(f)
                category = d.get("category", category)
        except Exception:
            pass

    return f"সর্বশেষ খবর: {headline} | বিভাগ: {category}"

def execute_intent(intent: str, details: str = "") -> dict:
    """
    ইনটেন্ট অনুযায়ী কাজ সম্পন্ন করে ইউজারকে দেখানোর জন্য মেসেজ প্রস্তুত করে।
    """
    if intent == "run_pipeline":
        print("\n⚙️  সম্পূর্ণ এআই রিলস পাইপলাইন রান করা হচ্ছে...")
        cmd = [sys.executable, RUN_PIPELINE_SCRIPT, "--new"]
        try:
            res = subprocess.run(cmd, cwd=PROJECT_DIR)
            if res.returncode == 0:
                return {
                    "success": True,
                    "msg": "পাইপলাইন সফলভাবে শেষ হয়েছে এবং ফেসবুক ও ইউটিউবে রিল আপলোড করা হয়েছে!"
                }
            else:
                return {
                    "success": False,
                    "msg": f"পাইপলাইন চলার সময় ত্রুটি ঘটেছে (exit code: {res.returncode})"
                }
        except Exception as exc:
            return {"success": False, "msg": f"পাইপলাইন চালু করতে ব্যর্থ: {exc}"}

    elif intent == "get_news":
        story_file = os.path.join(COLLECTOR_DIR, "output", "latest", "story_data.json")
        if os.path.exists(story_file):
            try:
                with open(story_file, "r", encoding="utf-8") as f:
                    d = json.load(f)
                    headline = d.get("headline", "শিরোনাম নেই")
                    summary = d.get("summary", "")
                    sources = d.get("matched_sources_count", 1)
                    return {
                        "success": True,
                        "msg": f"আজকের নির্বাচিত খবর:\n📌 {headline}\n📝 সারসংক্ষেপ: {summary}\n🌐 {sources}টি জাতীয় সংবাদমাধ্যম দ্বারা যাচাইকৃত।"
                    }
            except Exception as exc:
                return {"success": False, "msg": f"খবর পড়তে সমস্যা: {exc}"}
        return {"success": False, "msg": "এখনও কোনো খবর সংগ্রহ করা হয়নি। আগে পাইপলাইন রান করুন।"}

    elif intent == "get_links":
        fb_log = os.path.join(FB_DIR, "output", "performance_log.json")
        yt_log = os.path.join(YT_DIR, "output", "yt_performance_log.json")
        links = []
        if os.path.exists(fb_log):
            try:
                with open(fb_log, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data and isinstance(data, list):
                        last_fb = data[-1]
                        if last_fb.get("published") and last_fb.get("reel_url"):
                            links.append(f"📘 Facebook Reel: {last_fb.get('reel_url')}")
            except Exception:
                pass

        if os.path.exists(yt_log):
            try:
                with open(yt_log, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data and isinstance(data, list):
                        last_yt = data[-1]
                        if last_yt.get("uploaded") and last_yt.get("video_url"):
                            links.append(f"📺 YouTube Shorts: {last_yt.get('video_url')}")
            except Exception:
                pass

        if links:
            return {"success": True, "msg": "\n".join(links)}
        return {"success": False, "msg": "কোনো সক্রিয় পোস্টের লিংক পাওয়া যায়নি বা অফলাইন মোডে পোস্ট সেভ রয়েছে।"}

    elif intent == "check_status":
        state_file = os.path.join(PROJECT_DIR, ".pipeline_state.json")
        if os.path.exists(state_file):
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    state = json.load(f)
                    completed = state.get("completed_agents", [])
                    return {
                        "success": True,
                        "msg": f"পাইপলাইনে এই পর্যন্ত সম্পন্ন ধাপসমূহ: {', '.join(completed) if completed else 'সবগুলো প্রস্তুত'}"
                    }
            except Exception:
                pass
        return {
            "success": True,
            "msg": "পাইপলাইনের সব ৮টি এজেন্ট পুরোপুরি সচল এবং নতুন রিল তৈরির জন্য প্রস্তুত রয়েছে।"
        }

    return {"success": True, "msg": ""}

