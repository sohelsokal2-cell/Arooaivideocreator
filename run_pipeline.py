import argparse
import json
import os
import subprocess
import sys
import time

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, ".pipeline_state.json")

AGENTS = [
    {
        "id": "collector",
        "name": "১. News Collector Agent (সংবাদ সংগ্রহ ও বহু-উৎস বিশ্লেষণ)",
        "script": os.path.join(BASE_DIR, "News Collector Agent", "main.py"),
        "output_check": os.path.join(BASE_DIR, "News Collector Agent", "output", "latest", "story_data.json"),
    },
    {
        "id": "writer",
        "name": "২. Writer Agent (৪৫-৬০ সেকেন্ড রিল স্ক্রিপ্ট তৈরি)",
        "script": os.path.join(BASE_DIR, "Writer Agent", "main.py"),
        "output_check": os.path.join(BASE_DIR, "Writer Agent", "output", "latest", "script_data.json"),
    },
    {
        "id": "voice",
        "name": "৩. Voice Over Agent (প্রাকৃতিক বাংলা স্টুডিও ভয়েস-ওভার)",
        "script": os.path.join(BASE_DIR, "Voice Over Agent", "main.py"),
        "output_check": os.path.join(BASE_DIR, "Voice Over Agent", "output", "latest", "audio_data.json"),
    },
    {
        "id": "image",
        "name": "৪. Image Editor Agent (বাঙালি ফ্যাক্টস ব্র্যান্ডেড রিল স্লাইড তৈরি)",
        "script": os.path.join(BASE_DIR, "Image Editor Agent", "main.py"),
        "output_check": os.path.join(BASE_DIR, "Image Editor Agent", "output", "latest", "image_data.json"),
    },
    {
        "id": "video",
        "name": "৫. Video Creator Agent (১০৮০x১৯২০ ভার্টিক্যাল রিল ভিডিও রেন্ডারিং)",
        "script": os.path.join(BASE_DIR, "Video Creator Agent", "main.py"),
        "output_check": os.path.join(BASE_DIR, "Video Creator Agent", "output", "latest", "reel_latest.mp4"),
    },
    {
        "id": "thumbnail",
        "name": "৬. Thumbnail Creator Agent (বাঙালি ফ্যাক্টস ক্লিন থাম্বনেইল স্টুডিও)",
        "script": os.path.join(BASE_DIR, "Thumbnail creator Agent", "main.py"),
        "output_check": os.path.join(BASE_DIR, "Thumbnail creator Agent", "output", "latest", "thumbnail_reels_9x16.jpg"),
    },
    {
        "id": "facebook",
        "name": "৭. Facebook Page Manage Agent (Groq AI Brain + মেটা অটো-পাবলিশ)",
        "script": os.path.join(BASE_DIR, "Facebook Page Manage Agent", "main.py"),
        "output_check": os.path.join(BASE_DIR, "Facebook Page Manage Agent", "output", "latest", "facebook_strategy.json"),
    },
    {
        "id": "youtube",
        "name": "৮. YouTube Page Manage Agent (Groq AI Brain + YouTube Shorts অটো-আপলোড)",
        "script": os.path.join(BASE_DIR, "Youtube Page Manage Agent", "main.py"),
        "output_check": os.path.join(BASE_DIR, "Youtube Page Manage Agent", "output", "latest", "youtube_strategy.json"),
    },
]


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"completed_agents": [], "last_run_timestamp": 0}


def save_state(state):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception:
        pass


def clear_state():
    if os.path.exists(STATE_FILE):
        try:
            os.remove(STATE_FILE)
        except Exception:
            pass


def run_pipeline(force_new=False):
    start_time = time.time()
    print("=" * 70)
    print("      🚀 AI REELS CREATOR — স্মার্ট রিজ্যুমেবল পাইপলাইন")
    print("      চ্যানেল: বাঙালি ফ্যাক্টস (@bangaliifacts)")
    print("=" * 70)

    if force_new:
        clear_state()
        state = {"completed_agents": []}
        print("🔄 সম্পূর্ণ নতুন রান শুরু করা হচ্ছে (আগের ক্যাশ ক্লিয়ার করা হয়েছে)...")
    else:
        state = load_state()

    completed = state.get("completed_agents", [])

    for idx, agent in enumerate(AGENTS, start=1):
        agent_id = agent["id"]
        check_file = agent["output_check"]

        # যদি এই এজেন্ট আগেই সফল হয়ে থাকে এবং তার আউটপুট ফাইল বিদ্যমান থাকে, তবে স্কিপ করা হবে
        if agent_id in completed and os.path.exists(check_file):
            print(f"\n⏩ [{idx}/{len(AGENTS)}] পূর্বেই সম্পন্ন: {agent['name']} (স্কিপ করা হলো)")
            continue

        print(f"\n▶️ [{idx}/{len(AGENTS)}] শুরু হচ্ছে: {agent['name']}...", flush=True)
        t0 = time.time()
        cmd = [sys.executable, "-u", agent["script"]]
        res = subprocess.run(cmd)
        elapsed = round(time.time() - t0, 1)

        if res.returncode != 0:
            print(f"\n❌ ত্রুটি: {agent['name']} ব্যর্থ হয়েছে (exit code: {res.returncode})")
            print("💡 আপনি পরবর্তীবার চালালে ঠিক এই ধাপ থেকেই স্বয়ংক্রিয়ভাবে আবার শুরু হবে!")
            save_state(state)
            sys.exit(res.returncode)

        # সফল হলে স্টেট ফাইলে মার্ক করা
        if agent_id not in completed:
            completed.append(agent_id)
        state["completed_agents"] = completed
        save_state(state)
        print(f"   ✓ সফলভাবে সম্পন্ন ({elapsed} সেকেন্ডে)")

    # সব এজেন্ট সফলভাবে শেষ হলে স্টেট ক্লিয়ার করা যাতে পরবর্তী খবর নতুন করে রান হতে পারে
    clear_state()

    total_time = round(time.time() - start_time, 1)
    print("\n" + "=" * 70)
    print(f"🎉 সম্পূর্ণ এআই রিল সফলভাবে তৈরি হয়েছে! (মোট সময়: {total_time} সেকেন্ড)")
    latest_video = os.path.join(BASE_DIR, "Video Creator Agent", "output", "latest", "reel_latest.mp4")
    latest_thumb = os.path.join(BASE_DIR, "Thumbnail creator Agent", "output", "latest", "thumbnail_reels_9x16.jpg")
    latest_post = os.path.join(BASE_DIR, "Writer Agent", "output", "latest", "post_metadata.txt")

    if os.path.exists(latest_video):
        print(f"🎬 ফাইনাল রিল ভিডিও   : {latest_video}")
    if os.path.exists(latest_thumb):
        print(f"📱 রিল থাম্বনেইল কভার : {latest_thumb}")
    if os.path.exists(latest_post):
        print(f"📝 সোশ্যাল মিডিয়া পোস্ট : {latest_post}")
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Reels Creator Resumable Pipeline")
    parser.add_argument("--new", action="store_true", help="আগের অগ্রগতি ভুলে সম্পূর্ণ নতুন করে শুরু করতে")
    args = parser.parse_args()

    run_pipeline(force_new=args.new)
