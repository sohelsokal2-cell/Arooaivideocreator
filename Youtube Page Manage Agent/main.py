"""
Youtube Page Manage Agent — Main Orchestrator
==============================================
AI Reels Creator পাইপলাইনের ৮ নম্বর এজেন্ট।
Groq AI Brain + YouTube Data API v3 দিয়ে Shorts অটোমেশন।

Features:
  - Groq AI YouTube Brain (নিজস্ব YT_GROQ_API_KEY)
  - A/B Title variants
  - SEO Description + Tags (500 chars) + Chapters
  - Thumbnail auto-set
  - Pinned First Comment + Reply Templates
  - Analytics tracking (yt_performance_log.json)
  - Peak hours per category
  - Sensitivity auto-filter (demonetization guard)
  - PUBLIC / UNLISTED / PRIVATE / SCHEDULE mode
  - Offline / dry-run mode
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

BASE_DIR         = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR      = os.path.dirname(BASE_DIR)
VIDEO_AGENT_DIR  = os.path.join(PROJECT_DIR, "Video Creator Agent")
THUMB_AGENT_DIR  = os.path.join(PROJECT_DIR, "Thumbnail creator Agent")
WRITER_AGENT_DIR = os.path.join(PROJECT_DIR, "Writer Agent")
COLLECTOR_DIR    = os.path.join(PROJECT_DIR, "News Collector Agent")
DHAKA_TZ         = timezone(timedelta(hours=6))

sys.path.insert(0, BASE_DIR)
import groq_brain
import yt_uploader


# ──────────────────────────────────────────────────────────────────────────────
# Env Loader
# ──────────────────────────────────────────────────────────────────────────────
def load_env():
    env_path = os.path.join(BASE_DIR, ".env")
    if not os.path.exists(env_path):
        return
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
# Output File Writer
# ──────────────────────────────────────────────────────────────────────────────
def write_output_files(run_dir: str, strategy: dict) -> dict:
    paths = {}

    # YouTube title + description
    yt_path = os.path.join(run_dir, "youtube_upload_package.txt")
    tags_str = ", ".join(strategy.get("tags", []))
    with open(yt_path, "w", encoding="utf-8") as f:
        f.write("=== YOUTUBE SHORTS TITLE (PRIMARY) ===\n\n")
        f.write(strategy.get("title", "") + "\n\n")
        f.write("=== YOUTUBE TITLE (A/B VARIANT) ===\n\n")
        f.write(strategy.get("title_b", "") + "\n\n")
        f.write("=== DESCRIPTION ===\n\n")
        f.write(strategy.get("description", "") + "\n\n")
        f.write("=== TAGS ===\n\n")
        f.write(tags_str + "\n\n")
        f.write("=== CHAPTERS ===\n\n")
        f.write(strategy.get("chapters", "") + "\n\n")
        f.write("=== THUMBNAIL TEXT SUGGESTION ===\n\n")
        f.write(strategy.get("thumbnail_text", "") + "\n\n")
        f.write("=== PINNED COMMENT ===\n\n")
        f.write(strategy.get("pinned_comment", "") + "\n\n")
        f.write("=== COMMENT REPLY TEMPLATES ===\n\n")
        for i, reply in enumerate(strategy.get("comment_replies", []), 1):
            f.write(f"  {i}. {reply}\n")
        f.write(f"\n=== STRATEGY ===\n"
                f"Category     : {strategy.get('category', '')}\n"
                f"Best Time    : {strategy.get('recommended_peak_hours', '')}\n"
                f"Reach        : {strategy.get('estimated_reach_potential', '')}\n"
                f"Engage Score : {strategy.get('engagement_score', 0)}/100\n"
                f"Sensitivity  : {strategy.get('sensitivity_level', 'Normal')}\n"
                f"YT Category  : {strategy.get('yt_category_id', 25)}\n"
                f"Hook         : {strategy.get('hook_analysis', '')}\n")
    paths["youtube_package"] = yt_path

    # Strategy JSON
    js_path = os.path.join(run_dir, "youtube_strategy.json")
    with open(js_path, "w", encoding="utf-8") as f:
        json.dump(strategy, f, ensure_ascii=False, indent=2)
    paths["strategy"] = js_path

    return paths


# ──────────────────────────────────────────────────────────────────────────────
# Analytics Logger
# ──────────────────────────────────────────────────────────────────────────────
def update_analytics_log(strategy: dict, headline: str, uploaded: bool, video_url: str = ""):
    log_path = os.path.join(BASE_DIR, "output", "yt_performance_log.json")
    log = []
    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                log = json.load(f)
        except Exception:
            log = []
    entry = {
        "timestamp"        : datetime.now(DHAKA_TZ).isoformat(),
        "headline"         : headline,
        "title"            : strategy.get("title", ""),
        "category"         : strategy.get("category", ""),
        "engagement_score" : strategy.get("engagement_score", 0),
        "estimated_reach"  : strategy.get("estimated_reach_potential", ""),
        "sensitivity"      : strategy.get("sensitivity_level", "Normal"),
        "uploaded"         : uploaded,
        "video_url"        : video_url,
        "hook_analysis"    : strategy.get("hook_analysis", ""),
    }
    log.append(entry)
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    return log_path


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="বাঙালি ফ্যাক্টস — YouTube Page Manage Agent with Groq AI Brain"
    )
    parser.add_argument("--out",     default=os.path.join(BASE_DIR, "output"), help="আউটপুট ফোল্ডার")
    parser.add_argument("--dry-run", action="store_true", help="আপলোড ছাড়াই শুধু ব্রেন স্ট্র্যাটেজি")
    parser.add_argument("--ab",      action="store_true", help="A/B variant title B ব্যবহার")
    parser.add_argument("--mode",    default="", help="Override publish mode: PUBLIC/UNLISTED/PRIVATE")
    args = parser.parse_args()

    started = time.time()
    load_env()

    publish_mode = (args.mode or os.environ.get("YT_PUBLISH_MODE", "PUBLIC")).upper()

    print("=" * 70)
    print("  AI Reels Creator — YouTube Page Manage Agent (Agent 8)")
    print("  Groq AI Brain | YouTube Shorts | SEO Optimizer | Analytics")
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
    print("\n[১/৪] 🧠 Groq AI Brain দিয়ে YouTube Shorts স্ট্র্যাটেজি বিশ্লেষণ হচ্ছে...")
    print(f"      Model: {os.environ.get('YT_GROQ_MODEL', 'openai/gpt-oss-120b')}")

    strategy   = groq_brain.analyze_and_optimize_video(headline, script_txt)
    category   = strategy.get("category", "জাতীয়")
    peak_hours = strategy.get("recommended_peak_hours", "")
    virality   = strategy.get("estimated_reach_potential", "High")
    eng_score  = strategy.get("engagement_score", 0)
    sensitivity= strategy.get("sensitivity_level", "Normal")
    hook       = strategy.get("hook_analysis", "")
    model_used = strategy.get("_model_used", "")
    title_used = strategy.get("title_b" if args.ab else "title", "")

    print(f"\n  ✅ YouTube Brain অ্যানালাইসিস সম্পন্ন:")
    print(f"     🎬 Title (A)          : {strategy.get('title', '')[:70]}...")
    print(f"     🎬 Title (B variant)  : {strategy.get('title_b', '')[:70]}...")
    print(f"     🏷️  ক্যাটাগরি         : {category}")
    print(f"     ⏰ পিক আপলোড টাইম    : {peak_hours}")
    print(f"     📈 সম্ভাব্য রিচ        : {virality}")
    print(f"     🎯 এনগেজমেন্ট স্কোর   : {eng_score}/100")
    print(f"     🔒 সেনসিটিভিটি        : {sensitivity}")
    print(f"     💡 হুক বিশ্লেষণ       : {hook[:80]}...")
    print(f"     🏷️  থাম্বনেইল টেক্সট  : {strategy.get('thumbnail_text', '')}")

    if sensitivity == "High":
        print(f"\n  ⚠️  সতর্কতা (High Sensitivity — Demonetization Guard): {strategy.get('sensitivity_note', '')}")
        print("      Title/Description স্বয়ংক্রিয়ভাবে সফটেন করা হয়েছে।")

    # ─── ধাপ ২: Output ফাইল লেখা ───────────────────────────────────────────
    print("\n[২/৪] 📄 YouTube আপলোড প্যাকেজ ফাইল তৈরি হচ্ছে...")
    strategy["_active_title"] = "B" if args.ab else "A"
    file_paths = write_output_files(run_dir, strategy)

    for src_path in file_paths.values():
        try:
            shutil.copy2(src_path, os.path.join(latest_dir, os.path.basename(src_path)))
        except Exception:
            pass

    print(f"     ✅ YouTube package : {file_paths['youtube_package']}")
    print(f"     ✅ Strategy JSON   : {file_paths['strategy']}")

    # ─── ধাপ ৩: YouTube API Check + Upload ─────────────────────────────────
    print(f"\n[৩/৪] 🌐 YouTube API কানেক্টিভিটি চেক ({publish_mode} Mode)...")
    is_connected, conn_msg = yt_uploader.check_credentials()
    print(f"      স্ট্যাটাস: {conn_msg}")

    uploaded  = False
    video_url = ""

    if is_connected and not args.dry_run:
        try:
            tags = strategy.get("tags", [])
            # YouTube tag limit: 500 total chars
            tag_str = ""
            filtered_tags = []
            for t in tags:
                if len(tag_str) + len(t) + 2 <= 500:
                    filtered_tags.append(t)
                    tag_str += t + ", "

            publish_at_iso = None
            if publish_mode == "SCHEDULE":
                # ২ ঘণ্টা পরের ISO 8601 টাইম (UTC)
                publish_at_iso = (datetime.now(timezone.utc) + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S.000Z")

            result = yt_uploader.upload_shorts(
                video_path=video_path,
                title=title_used,
                description=strategy.get("description", ""),
                tags=filtered_tags,
                category_id=strategy.get("yt_category_id", 25),
                privacy=publish_mode,
                thumbnail_path=thumb_path,
                publish_at=publish_at_iso,
            )
            uploaded  = True
            video_url = result.get("shorts_url", "")
            print(f"\n  ✅ YouTube Shorts সফলভাবে আপলোড হয়েছে!")
            print(f"  🔗 Shorts লিংক: {video_url}")

            # Pinned Comment
            if os.environ.get("YT_AUTO_PIN_COMMENT", "true").lower() == "true":
                vid_id  = result.get("video_id")
                comment = strategy.get("pinned_comment", "")
                c_id    = yt_uploader.post_pinned_comment(vid_id, comment)
                if c_id:
                    print("  💬 পিন কমেন্ট পোস্ট হয়েছে!")
        except Exception as exc:
            print(f"\n  ⚠️  YouTube আপলোডে ত্রুটি: {exc}")
    else:
        status = "🔑 YT Credentials নেই" if not is_connected else "--dry-run মোড"
        print(f"\n  ℹ️  [অফলাইন / রেডি-টু-আপলোড মোড] ({status})")
        print(f"     ► YouTube Package: {file_paths['youtube_package']}")
        if not is_connected:
            print("     (আপলোডের জন্য .env-এ YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN দিন)")

    # ─── ধাপ ৪: Analytics Log ───────────────────────────────────────────────
    print("\n[৪/৪] 📊 YouTube Analytics লগ আপডেট হচ্ছে...")
    log_path = update_analytics_log(strategy, headline, uploaded, video_url)
    print(f"      ✅ Analytics log: {log_path}")

    # ─── Summary ─────────────────────────────────────────────────────────────
    elapsed = round(time.time() - started, 1)
    print("\n" + "=" * 70)
    print("✅ YouTube Page Manage Agent সফলভাবে সম্পন্ন!")
    print(f"   মডেল          : {model_used}")
    print(f"   Title ভার্স   : {'B (A/B Test)' if args.ab else 'A (Primary)'}")
    print(f"   Publish Mode  : {publish_mode}")
    print(f"   আপলোড হয়েছে  : {'✅ হ্যাঁ — ' + video_url if uploaded else '❌ না (অফলাইন মোড)'}")
    print(f"   আউটপুট ফোল্ডার: {run_dir}")
    print(f"   প্রসেসিং সময়  : {elapsed} সেকেন্ড")
    print("=" * 70)


if __name__ == "__main__":
    main()

