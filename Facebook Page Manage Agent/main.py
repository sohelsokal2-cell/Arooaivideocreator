"""
Facebook Page Manage Agent — Main Orchestrator
===============================================
AI Reels Creator পাইপলাইনের ৭ নম্বর এজেন্ট।
Groq AI Brain + Meta Graph API দিয়ে ফেসবুক রিল অটোমেশন।

Features:
  - Groq AI enhanced brain (নিজস্ব FB_GROQ_API_KEY)
  - A/B Caption variants
  - Multi-platform output (FB + Instagram + YouTube)
  - Comment reply templates
  - Analytics tracking (performance_log.json)
  - Content calendar + peak hours
  - Sensitivity auto-filter
  - Hashtag intelligence per category
  - Offline / Direct / Schedule / Draft mode
  - Resumable checkpoint
"""

import argparse
import json
import os
import shutil
import sys
import time
from datetime import datetime, timedelta, timezone

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR          = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR       = os.path.dirname(BASE_DIR)
VIDEO_AGENT_DIR   = os.path.join(PROJECT_DIR, "Video Creator Agent")
THUMB_AGENT_DIR   = os.path.join(PROJECT_DIR, "Thumbnail creator Agent")
WRITER_AGENT_DIR  = os.path.join(PROJECT_DIR, "Writer Agent")
COLLECTOR_DIR     = os.path.join(PROJECT_DIR, "News Collector Agent")
DHAKA_TZ          = timezone(timedelta(hours=6))

sys.path.insert(0, BASE_DIR)
import groq_brain
import meta_publisher


# ──────────────────────────────────────────────────────────────────────────────
# Env Loader
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


# ──────────────────────────────────────────────────────────────────────────────
# Context Loader
# ──────────────────────────────────────────────────────────────────────────────
def load_story_context():
    story_json  = os.path.join(COLLECTOR_DIR,    "output", "latest", "story_data.json")
    script_json = os.path.join(WRITER_AGENT_DIR, "output", "latest", "script_data.json")

    headline   = "ব্রেকিং নিউজ"
    date_label = datetime.now(DHAKA_TZ).strftime("%Y-%m-%d")
    run_id     = 1
    script_txt = ""

    if os.path.exists(story_json):
        try:
            with open(story_json, "r", encoding="utf-8") as f:
                d = json.load(f)
                headline   = d.get("headline", headline)
                date_label = d.get("date", date_label)
                run_id     = d.get("run_id", run_id)
        except Exception:
            pass

    if os.path.exists(script_json):
        try:
            with open(script_json, "r", encoding="utf-8") as f:
                s = json.load(f)
                script_txt = s.get("full_script", "")
        except Exception:
            pass

    video_path = os.path.join(VIDEO_AGENT_DIR, "output", "latest", "reel_latest.mp4")
    thumb_path = os.path.join(THUMB_AGENT_DIR, "output", "latest", "thumbnail_reels_9x16.jpg")

    return headline, date_label, run_id, script_txt, video_path, thumb_path


# ──────────────────────────────────────────────────────────────────────────────
# Analytics Logger
# ──────────────────────────────────────────────────────────────────────────────
def update_analytics_log(run_dir: str, strategy: dict, headline: str, published: bool, reel_url: str = ""):
    """কুমুলেটিভ পারফরম্যান্স লগ আপডেট করে।"""
    log_path = os.path.join(BASE_DIR, "output", "performance_log.json")
    log = []
    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                log = json.load(f)
        except Exception:
            log = []

    entry = {
        "timestamp"           : datetime.now(DHAKA_TZ).isoformat(),
        "headline"            : headline,
        "category"            : strategy.get("category", ""),
        "engagement_score"    : strategy.get("engagement_score", 0),
        "estimated_reach"     : strategy.get("estimated_reach_potential", ""),
        "sensitivity"         : strategy.get("sensitivity_level", "Normal"),
        "peak_hours"          : strategy.get("recommended_peak_hours", ""),
        "published"           : published,
        "reel_url"            : reel_url,
        "hook_analysis"       : strategy.get("hook_analysis", ""),
    }
    log.append(entry)
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    return log_path


# ──────────────────────────────────────────────────────────────────────────────
# Multi-Platform File Writer
# ──────────────────────────────────────────────────────────────────────────────
def write_platform_files(run_dir: str, strategy: dict) -> dict:
    """FB, Instagram, YouTube আউটপুট ফাইল লেখে।"""
    paths = {}

    # Facebook caption
    fb_path = os.path.join(run_dir, "facebook_caption.txt")
    with open(fb_path, "w", encoding="utf-8") as f:
        f.write("=== FACEBOOK REEL CAPTION (PRIMARY) ===\n\n")
        f.write(strategy.get("caption", "") + "\n\n")
        f.write("=== FACEBOOK CAPTION (A/B VARIANT) ===\n\n")
        f.write(strategy.get("caption_b", "") + "\n\n")
        f.write("=== PINNED FIRST COMMENT ===\n\n")
        f.write(strategy.get("first_comment", "") + "\n\n")
        f.write("=== COMMENT REPLY TEMPLATES ===\n\n")
        for i, reply in enumerate(strategy.get("comment_replies", []), 1):
            f.write(f"  {i}. {reply}\n")
    paths["facebook"] = fb_path

    # Instagram caption
    ig_path = os.path.join(run_dir, "instagram_caption.txt")
    with open(ig_path, "w", encoding="utf-8") as f:
        f.write("=== INSTAGRAM REELS CAPTION ===\n\n")
        f.write(strategy.get("instagram_caption", "") + "\n")
    paths["instagram"] = ig_path

    # YouTube description
    yt_path = os.path.join(run_dir, "youtube_description.txt")
    with open(yt_path, "w", encoding="utf-8") as f:
        f.write("=== YOUTUBE SHORTS DESCRIPTION ===\n\n")
        f.write(strategy.get("youtube_description", "") + "\n")
    paths["youtube"] = yt_path

    # Hashtags
    ht_path = os.path.join(run_dir, "hashtags.txt")
    with open(ht_path, "w", encoding="utf-8") as f:
        f.write("=== HASHTAG POOL ===\n\n")
        f.write(strategy.get("hashtag_pool", "") + "\n")
    paths["hashtags"] = ht_path

    # Strategy JSON (full)
    js_path = os.path.join(run_dir, "facebook_strategy.json")
    with open(js_path, "w", encoding="utf-8") as f:
        json.dump(strategy, f, ensure_ascii=False, indent=2)
    paths["strategy"] = js_path

    # Legacy caption file (backward compat for pipeline)
    legacy_path = os.path.join(run_dir, "ready_to_post_caption.txt")
    with open(legacy_path, "w", encoding="utf-8") as f:
        f.write("=== FACEBOOK REEL CAPTION ===\n\n")
        f.write(strategy.get("caption", "") + "\n\n")
        f.write("=== FIRST COMMENT (PIN THIS) ===\n\n")
        f.write(strategy.get("first_comment", "") + "\n\n")
        f.write(f"=== STRATEGY ===\n"
                f"Category     : {strategy.get('category', '')}\n"
                f"Best Time    : {strategy.get('recommended_peak_hours', '')}\n"
                f"Reach        : {strategy.get('estimated_reach_potential', '')}\n"
                f"Engage Score : {strategy.get('engagement_score', 0)}/100\n"
                f"Sensitivity  : {strategy.get('sensitivity_level', 'Normal')}\n"
                f"Hook         : {strategy.get('hook_analysis', '')}\n")
    paths["legacy"] = legacy_path

    return paths


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="বাঙালি ফ্যাক্টস — Facebook Page Manage Agent with Groq AI Brain"
    )
    parser.add_argument("--out",     default=os.path.join(BASE_DIR, "output"), help="আউটপুট ফোল্ডার")
    parser.add_argument("--dry-run", action="store_true", help="আপলোড ছাড়াই শুধু ব্রেন স্ট্র্যাটেজি তৈরি")
    parser.add_argument("--ab",      action="store_true", help="A/B ক্যাপশন ভেরিয়েন্ট B ব্যবহার করো")
    args = parser.parse_args()

    started = time.time()
    load_env()

    print("=" * 70)
    print("  AI Reels Creator — Facebook Page Manage Agent (Agent 7)")
    print("  Groq AI Enhanced Brain | Multi-Platform | Analytics Tracker")
    print("  চ্যানেল: বাঙালি ফ্যাক্টস (@bangaliifacts)")
    print("=" * 70)

    headline, date_label, run_id, script_txt, video_path, thumb_path = load_story_context()

    print(f"\n  মূল খবর       : {headline}")
    print(f"  তারিখ         : {date_label}  |  রান নং: #{run_id:02d}")
    print(f"  রিল ভিডিও    : {'✅ ' + video_path if os.path.exists(video_path) else '❌ ফাইল নেই'}")
    print(f"  থাম্বনেইল    : {'✅ ' + thumb_path if os.path.exists(thumb_path) else '❌ ফাইল নেই'}")

    # আউটপুট ডিরেক্টরি
    run_dir    = os.path.join(args.out, date_label, f"run_{run_id:02d}")
    latest_dir = os.path.join(args.out, "latest")
    os.makedirs(run_dir,    exist_ok=True)
    os.makedirs(latest_dir, exist_ok=True)

    # ─── ধাপ ১: Groq AI Brain ───────────────────────────────────────────────
    print("\n[১/৪] 🧠 Groq AI Brain দিয়ে এনহান্সড স্ট্র্যাটেজি বিশ্লেষণ হচ্ছে...")
    print(f"      Model: {os.environ.get('FB_GROQ_MODEL', os.environ.get('GROQ_MODEL', 'openai/gpt-oss-120b'))}")

    strategy = groq_brain.analyze_and_optimize_post(headline, script_txt)

    category    = strategy.get("category", "জাতীয়")
    peak_hours  = strategy.get("recommended_peak_hours", "")
    virality    = strategy.get("estimated_reach_potential", "High")
    eng_score   = strategy.get("engagement_score", 0)
    sensitivity = strategy.get("sensitivity_level", "Normal")
    hook        = strategy.get("hook_analysis", "")
    model_used  = strategy.get("_model_used", "")

    print(f"\n  ✅ ব্রেন অ্যানালাইসিস সম্পন্ন:")
    print(f"     🏷️  ক্যাটাগরি        : {category}")
    print(f"     ⏰ পিক পোস্টিং টাইম : {peak_hours}")
    print(f"     📈 সম্ভাব্য রিচ       : {virality}")
    print(f"     🎯 এনগেজমেন্ট স্কোর  : {eng_score}/100")
    print(f"     🔒 সেনসিটিভিটি       : {sensitivity}")
    print(f"     💡 হুক বিশ্লেষণ      : {hook[:80]}...")

    if sensitivity == "High":
        print(f"\n  ⚠️  সতর্কতা (High Sensitivity): {strategy.get('sensitivity_note', '')}")
        print("      ক্যাপশন স্বয়ংক্রিয়ভাবে সফটেন করা হয়েছে।")

    # ─── ধাপ ২: Multi-Platform ফাইল লেখা ──────────────────────────────────
    print("\n[২/৪] 📄 মাল্টি-প্ল্যাটফর্ম কন্টেন্ট ফাইল তৈরি হচ্ছে...")
    caption_to_use = strategy.get("caption_b" if args.ab else "caption", "")
    strategy["_active_caption"] = "B" if args.ab else "A"

    file_paths = write_platform_files(run_dir, strategy)

    # latest/ ফোল্ডারে কপি
    for name, src_path in file_paths.items():
        try:
            shutil.copy2(src_path, os.path.join(latest_dir, os.path.basename(src_path)))
        except Exception:
            pass

    print(f"     ✅ Facebook caption  : {file_paths['facebook']}")
    print(f"     ✅ Instagram caption : {file_paths['instagram']}")
    print(f"     ✅ YouTube desc      : {file_paths['youtube']}")
    print(f"     ✅ Hashtag pool      : {file_paths['hashtags']}")
    print(f"     ✅ Strategy JSON     : {file_paths['strategy']}")

    # ─── ধাপ ৩: Meta API Check + Publish ───────────────────────────────────
    page_id      = os.environ.get("FB_PAGE_ID", "").strip()
    access_token = os.environ.get("FB_PAGE_ACCESS_TOKEN", "").strip()
    publish_mode = os.environ.get("PUBLISH_MODE", "DIRECT").upper()

    print(f"\n[৩/৪] 🌐 মেটা ফেসবুক কানেক্টিভিটি চেক ({publish_mode} Mode)...")
    is_connected, conn_msg = meta_publisher.check_api_credentials(page_id, access_token)
    print(f"      স্ট্যাটাস: {conn_msg}")

    published = False
    reel_url  = ""

    if is_connected and not args.dry_run:
        try:
            # শিডিউলিং টাইম ক্যালকুলেশন (যদি SCHEDULE মোড হয়, বর্তমান সময় থেকে ২ ঘণ্টা পর)
            scheduled_ts = None
            if publish_mode == "SCHEDULE":
                scheduled_ts = int(time.time() + 7200) # ২ ঘণ্টা পর

            pub_result = meta_publisher.publish_reel(
                page_id=page_id,
                access_token=access_token,
                video_path=video_path,
                caption=caption_to_use,
                cover_img_path=thumb_path,
                publish_mode=publish_mode,
                scheduled_time=scheduled_ts,
            )
            published = True
            reel_url  = pub_result.get("reel_url", "")
            print(f"\n  ✅ রিল পেজে সফলভাবে পাবলিশ হয়েছে!")
            print(f"  🔗 রিল লিংক: {reel_url}")

            # First comment
            if os.environ.get("AUTO_PIN_FIRST_COMMENT", "true").lower() == "true":
                first_comment = strategy.get("first_comment", "")
                c_id = meta_publisher.post_first_comment(
                    pub_result.get("video_id"), access_token, first_comment
                )
                if c_id:
                    print("  💬 পিন কমেন্ট ড্রপ করা হয়েছে!")
        except Exception as exc:
            print(f"\n  ⚠️  ফেসবুক রিল আপলোডে ত্রুটি: {exc}")
    else:
        status = "🔑 FB ক্রেডেনশিয়াল নেই" if not is_connected else "--dry-run মোড"
        print(f"\n  ℹ️  [অফলাইন / রেডি-টু-পোস্ট মোড] ({status})")
        print(f"     পোস্ট করার জন্য সব ফাইল প্রস্তুত:")
        print(f"     ► Facebook : {file_paths['facebook']}")
        print(f"     ► Instagram: {file_paths['instagram']}")
        print(f"     ► YouTube  : {file_paths['youtube']}")
        if not is_connected:
            print("     (ফেসবুক অটো-আপলোডের জন্য .env-এ FB_PAGE_ID ও FB_PAGE_ACCESS_TOKEN দিন)")

    # ─── ধাপ ৪: Analytics Log ───────────────────────────────────────────────
    print("\n[৪/৪] 📊 পারফরম্যান্স অ্যানালিটিক্স লগ আপডেট হচ্ছে...")
    log_path = update_analytics_log(run_dir, strategy, headline, published, reel_url)
    print(f"      ✅ Analytics log: {log_path}")

    # ─── Summary ─────────────────────────────────────────────────────────────
    elapsed = round(time.time() - started, 1)
    print("\n" + "=" * 70)
    print("✅ Facebook Page Manage Agent সফলভাবে সম্পন্ন!")
    print(f"   মডেল          : {model_used}")
    print(f"   ক্যাপশন ভার্স : {'B (A/B Test)' if args.ab else 'A (Primary)'}")
    print(f"   পাবলিশড       : {'✅ হ্যাঁ — ' + reel_url if published else '❌ না (অফলাইন মোড)'}")
    print(f"   আউটপুট ফোল্ডার: {run_dir}")
    print(f"   প্রসেসিং সময়  : {elapsed} সেকেন্ড")
    print("=" * 70)


if __name__ == "__main__":
    main()
