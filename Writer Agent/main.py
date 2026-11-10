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

import gemini_api
import news_parser
import post_generator
import report
import script_writer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COLLECTOR_DIR = os.path.join(os.path.dirname(BASE_DIR), "News Collector Agent")
DHAKA_TZ = timezone(timedelta(hours=6))


def main():
    parser = argparse.ArgumentParser(description="Multi-Source Breaking News Reel Script Writer")
    parser.add_argument("--input", default="", help="story_data.json বা news_*.docx এর পাথ (ডিফল্ট: সর্বশেষ)")
    parser.add_argument("--out", default=os.path.join(BASE_DIR, "output"), help="আউটপুট ফোল্ডার")
    parser.add_argument("--seconds", type=int, default=52, help="রিলের লক্ষ্য সময় (সেকেন্ড, ডিফল্ট: ৫২s)")
    args = parser.parse_args()

    started = time.time()
    gemini_api.load_env()
    if not gemini_api.api_key():
        print("ত্রুটি: GEMINI_API_KEY পাওয়া যায়নি। .env ফাইলে GEMINI_API_KEY=AIza... বসান।")
        sys.exit(1)

    print("==================================================================")
    print("  AI Reels Creator — Writer Agent (Agent 2)")
    print("  রিল স্ক্রিপ্ট জেনারেশন (লক্ষ্য: ৪৫-৬০ সেকেন্ড / ৯০-১২০ শব্দ)")
    print("==================================================================")

    # ইনপুট লোড করা (Collector Agent থেকে)
    try:
        resolved_path, story_data = news_parser.load_story_input(
            path=args.input,
            collector_dir=COLLECTOR_DIR,
            base_dir=BASE_DIR,
        )
    except Exception as exc:
        print(f"ইনপুট ফাইল লোড করা যায়নি: {exc}")
        sys.exit(1)

    date_label = story_data.get("date") or datetime.now(DHAKA_TZ).strftime("%Y-%m-%d")
    run_id = story_data.get("run_id", 1)
    headline = story_data.get("headline", "ব্রেকিং নিউজ")
    sources = story_data.get("sources", [])

    print(f"ইনপুট পাথ : {resolved_path}")
    print(f"মূল খবর  : {headline}")
    print(f"সোর্স তথ্য: {len(sources)}টি সংবাদমাধ্যমের সমন্বিত রিপোর্ট")
    print(f"AI মডেল   : {os.environ.get('GEMINI_MODEL', gemini_api.FALLBACK_MODELS[0])}")

    print("\n[১/২] Gemini AI দিয়ে বহু-উৎস বিশ্লেষণ করে রিল স্ক্রিপ্ট তৈরি হচ্ছে...")
    script_result = script_writer.write_reel_script(story_data, target_seconds=args.seconds)
    script_result["headline"] = headline
    script_result["date"] = date_label
    script_result["run_id"] = run_id

    full_script = script_result.get("full_script", "")
    word_count = script_result.get("word_count", len(full_script.split()))
    est_seconds = round(word_count / 2.1, 1)

    print("\n🌟 স্ক্রিপ্ট প্রস্তুত:")
    print(f"   হুক (Hook) : {script_result.get('hook', '')}")
    print(f"   শব্দসংখ্যা : {word_count} শব্দ (আনুমানিক সময়: {est_seconds} সেকেন্ড)")
    print(f"   আউট্রো    : {script_result.get('outro', '')}")

    # আউটপুট ডিরেক্টরি
    run_dir = os.path.join(args.out, date_label, f"run_{run_id:02d}")
    os.makedirs(run_dir, exist_ok=True)

    docx_path = os.path.join(run_dir, f"script_{date_label}_run{run_id:02d}.docx")
    txt_path = os.path.join(run_dir, f"script_{date_label}_run{run_id:02d}.txt")
    json_path = os.path.join(run_dir, "script_data.json")

    print(f"\n[২/৩] স্ক্রিপ্ট ডকুমেন্ট ও ডেটা সেভ করা হচ্ছে...")
    report.write_docx_script(script_result, docx_path, date_label)
    report.write_txt_script(script_result, txt_path)
    report.write_json_script(script_result, json_path)

    print(f"\n[৩/৩] সোশ্যাল মিডিয়া পোস্ট মেটাডাটা (টাইটেল, ডেসক্রিপশন ও হ্যাশট্যাগ) জেনারেট হচ্ছে...")
    post_data = post_generator.generate_post_metadata(headline, full_script, date_label)
    post_txt_path = os.path.join(run_dir, "post_metadata.txt")
    post_json_path = os.path.join(run_dir, "post_metadata.json")

    with open(post_json_path, "w", encoding="utf-8") as f:
        json.dump(post_data, f, ensure_ascii=False, indent=2)

    formatted_post_text = post_generator.format_post_text(post_data, headline)
    with open(post_txt_path, "w", encoding="utf-8") as f:
        f.write(formatted_post_text)

    # latest ফোল্ডারে মিরর করা যাতে পরবর্তী এজেন্টরা (Voice Over Agent) সহজে পায়
    latest_dir = os.path.join(args.out, "latest")
    os.makedirs(latest_dir, exist_ok=True)
    try:
        shutil.copy2(docx_path, os.path.join(latest_dir, f"script_{date_label}.docx"))
        shutil.copy2(txt_path, os.path.join(latest_dir, f"script_{date_label}.txt"))
        shutil.copy2(json_path, os.path.join(latest_dir, "script_data.json"))
        shutil.copy2(post_txt_path, os.path.join(latest_dir, "post_metadata.txt"))
        shutil.copy2(post_json_path, os.path.join(latest_dir, "post_metadata.json"))
    except Exception as exc:
        print(f"সতর্কতা: latest ফোল্ডারে কপি করতে সমস্যা ({exc})")

    elapsed = round(time.time() - started, 1)
    print("\n==================================================================")
    print("✅ রিল স্ক্রিপ্ট ও সোশ্যাল মিডিয়া পোস্ট তৈরি সম্পন্ন!")
    print(f"  মোট শব্দ       : {word_count} শব্দ")
    print(f"  আনুমানিক সময়   : {est_seconds} সেকেন্ড (৪৫-৬০ সেকেন্ড রেঞ্জের মধ্যে)")
    print(f"  ডকুমেন্ট       : {docx_path}")
    print(f"  টেক্সট ফাইল     : {txt_path}")
    print(f"  JSON ডেটা      : {json_path}")
    print(f"  সোশ্যাল মেটাডাটা: {post_txt_path}")
    print(f"  প্রসেসিং সময়   : {elapsed} সেকেন্ড")
    print("==================================================================")
    print("\nসোশ্যাল মিডিয়া পোস্ট প্রিভিউ:\n")
    print(formatted_post_text)
    print("==================================================================")
    print("\nস্ক্রিপ্ট প্রিভিউ:\n")
    print(full_script)
    print("\n==================================================================")


if __name__ == "__main__":
    main()
