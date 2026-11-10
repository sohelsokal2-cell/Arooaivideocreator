import argparse
import glob
import json
import os
import shutil
import sys
import time
from datetime import datetime, timedelta, timezone
from PIL import Image

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
COLLECTOR_DIR = os.path.join(ROOT_DIR, "News Collector Agent")
DHAKA_TZ = timezone(timedelta(hours=6))

import composer

BN_DIGITS = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")
MONTHS_BN = {
    1: "জানুয়ারি", 2: "ফেব্রুয়ারি", 3: "মার্চ", 4: "এপ্রিল",
    5: "মে", 6: "জুন", 7: "জুলাই", 8: "আগস্ট",
    9: "সেপ্টেম্বর", 10: "অক্টোবর", 11: "নভেম্বর", 12: "ডিসেম্বর",
}

def format_bangla_date(dt=None):
    if dt is None:
        dt = datetime.now(DHAKA_TZ)
    day = f"{dt.day:02d}".translate(BN_DIGITS)
    month = MONTHS_BN.get(dt.month, "")
    year = str(dt.year).translate(BN_DIGITS)
    return f"{day} {month} {year}"


def load_story_context():
    story_json = os.path.join(COLLECTOR_DIR, "output", "latest", "story_data.json")
    headline = "ব্রেকিং নিউজ"
    date_label = datetime.now(DHAKA_TZ).strftime("%Y-%m-%d")
    run_id = 1

    if os.path.exists(story_json):
        try:
            with open(story_json, "r", encoding="utf-8") as f:
                data = json.load(f)
                headline = data.get("headline", headline)
                date_label = data.get("date", date_label)
                run_id = data.get("run_id", run_id)
        except Exception:
            pass

    return headline, date_label, run_id


def get_news_images():
    img_dir = os.path.join(COLLECTOR_DIR, "output", "latest", "images")
    if not os.path.exists(img_dir):
        return []
    return sorted(glob.glob(os.path.join(img_dir, "*.jpg")) + glob.glob(os.path.join(img_dir, "*.png")))


def main():
    parser = argparse.ArgumentParser(description="Official Bangalii Facts Thumbnail Creator Agent")
    parser.add_argument("--out", default=os.path.join(BASE_DIR, "output"), help="আউটপুট ফোল্ডার")
    args = parser.parse_args()

    started = time.time()
    print("==================================================================")
    print("  AI Reels Creator — Thumbnail Creator Agent")
    print("  বাঙালি ফ্যাক্টস অফিশিয়াল ব্র্যান্ডেড থাম্বনেইল স্টুডিও")
    print("==================================================================")

    headline, date_label, run_id = load_story_context()
    bangla_date = format_bangla_date()

    print(f"মূল খবর      : {headline}")
    print(f"বাংলা তারিখ   : {bangla_date}")
    print(f"রান আইডি     : #{run_id:02d}")

    images = get_news_images()
    if not images:
        print("ত্রুটি: কোনো সংবাদ ছবি পাওয়া যায়নি।")
        sys.exit(1)

    run_dir = os.path.join(args.out, date_label, f"run_{run_id:02d}")
    latest_dir = os.path.join(args.out, "latest")
    os.makedirs(run_dir, exist_ok=True)
    os.makedirs(latest_dir, exist_ok=True)

    main_img = Image.open(images[0]).convert("RGB")

    print("\n[১/২] রেফারেন্স অনুযায়ী নিখুঁত বাঙালি ফ্যাক্টস কার্ড তৈরি হচ্ছে...")
    clean_card = composer.build_premium_clean_card(
        news_img=main_img,
        headline=headline,
        date_str=bangla_date,
        card_w=980,
        photo_h=490,
    )

    card_save_path = os.path.join(run_dir, "clean_news_card.png")
    clean_card.save(card_save_path, "PNG")

    print("\n[২/২] অফিশিয়াল রিল কভার (৯:১৬) ও ইউটিউব থাম্বনেইল (১৬:৯) প্রস্তুত হচ্ছে...")
    # ৯:১৬ রিল কভার (রেফারেন্সের হুবহু)
    thumb_9x16 = composer.compose_reels_9x16_thumbnail(clean_card, bg_image=main_img)
    thumb_9x16_path = os.path.join(run_dir, "thumbnail_reels_9x16.jpg")
    thumb_9x16.save(thumb_9x16_path, "JPEG", quality=95)

    # ১৬:৯ ইউটিউব থাম্বনেইল
    thumb_16x9 = composer.compose_youtube_16x9_thumbnail(clean_card, bg_image=main_img)
    thumb_16x9_path = os.path.join(run_dir, "thumbnail_youtube_16x9.jpg")
    thumb_16x9.save(thumb_16x9_path, "JPEG", quality=95)

    # latest ফোল্ডারে মিরর
    shutil.copy2(card_save_path, os.path.join(latest_dir, "clean_news_card.png"))
    shutil.copy2(thumb_9x16_path, os.path.join(latest_dir, "thumbnail_reels_9x16.jpg"))
    shutil.copy2(thumb_16x9_path, os.path.join(latest_dir, "thumbnail_youtube_16x9.jpg"))

    elapsed = round(time.time() - started, 1)
    print("\n==================================================================")
    print("✅ অফিশিয়াল বাঙালি ফ্যাক্টস থাম্বনেইল সফলভাবে প্রস্তুত হয়েছে!")
    print(f"  রিল কভার থাম্বনেইল (৯:১৬) : {os.path.join(latest_dir, 'thumbnail_reels_9x16.jpg')}")
    print(f"  ইউটিউব থাম্বনেইল (১৬:৯) : {os.path.join(latest_dir, 'thumbnail_youtube_16x9.jpg')}")
    print(f"  ক্লিন কার্ড ফাইল (PNG)    : {os.path.join(latest_dir, 'clean_news_card.png')}")
    print(f"  প্রসেসিং সময়           : {elapsed} সেকেন্ড")
    print("==================================================================")


if __name__ == "__main__":
    main()
