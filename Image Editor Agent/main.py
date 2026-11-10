import argparse
import json
import os
import re
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

import card_composer
import watermark_cleaner

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
COLLECTOR_DIR = os.path.join(PROJECT_DIR, "News Collector Agent")
WRITER_DIR = os.path.join(PROJECT_DIR, "Writer Agent")
DHAKA_TZ = timezone(timedelta(hours=6))

BN_MONTHS = {
    1: "জানুয়ারি", 2: "ফেব্রুয়ারি", 3: "মার্চ", 4: "এপ্রিল",
    5: "মে", 6: "জুন", 7: "জুলাই", 8: "আগস্ট",
    9: "সেপ্টেম্বর", 10: "অক্টোবর", 11: "নভেম্বর", 12: "ডিসেম্বর"
}
_BN_DIGITS = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")


def _to_bn_digits(n):
    return str(n).translate(_BN_DIGITS)


def format_bangla_date(dt=None):
    if dt is None:
        dt = datetime.now(DHAKA_TZ)
    day = _to_bn_digits(f"{dt.day:02d}")
    month = BN_MONTHS.get(dt.month, "")
    year = _to_bn_digits(dt.year)
    return f"{day} {month} {year}"


def _clean_caption(text, max_len=75):
    """ক্যাপশনকে কার্ডের নিচে ১-২ লাইনে সুন্দরভাবে বসার উপযোগী করে।"""
    text = re.sub(r"\s+", " ", text or "").strip()
    # প্রথম বাক্য নেওয়া
    for punc in ["।", "?", "!"]:
        if punc in text:
            first_sentence = text.split(punc)[0].strip() + punc
            if len(first_sentence) <= max_len:
                return first_sentence
    if len(text) > max_len:
        return text[:max_len - 3].rstrip() + "..."
    return text


def load_input_data():
    """
    Collector ও Writer Agent-এর সর্বশেষ আউটপুট লোড করে।
    """
    # 1. স্ক্রিপ্ট ও সিন ডেটা
    script_file = os.path.join(WRITER_DIR, "output", "latest", "script_data.json")
    script_data = {}
    if os.path.exists(script_file):
        with open(script_file, "r", encoding="utf-8") as fh:
            script_data = json.load(fh)

    # 2. ছবি ফোল্ডার
    images_dir = os.path.join(COLLECTOR_DIR, "output", "latest", "images")
    if not os.path.exists(images_dir):
        # ফলব্যাক: তারিখভিত্তিক ফোল্ডার খোঁজা
        collector_out = os.path.join(COLLECTOR_DIR, "output")
        for root, _dirs, files in os.walk(collector_out):
            if any(f.endswith(".jpg") for f in files) and "images" in root:
                images_dir = root
                break

    return script_data, images_dir


def main():
    parser = argparse.ArgumentParser(description="Bangalii Facts Branded News Card & Reel Slide Generator")
    parser.add_argument("--out", default=os.path.join(BASE_DIR, "output"), help="আউটপুট ফোল্ডার")
    parser.add_argument("--channel", default="বাঙালি ফ্যাক্টস", help="চ্যানেলের নাম")
    parser.add_argument("--handle", default="@bangaliifacts", help="হ্যান্ডেল")
    args = parser.parse_args()

    started = time.time()
    print("==================================================================")
    print("  AI Reels Creator — Image Editor Agent")
    print(f"  ব্র্যান্ড: {args.channel} ({args.handle})")
    print("  ওয়াটারমার্ক রিমুভাল ও ৯:১৬ রিল ফ্রেম স্লাইড তৈরি")
    print("==================================================================")

    script_data, images_dir = load_input_data()
    headline = script_data.get("headline", "আজকের ব্রেকিং সংবাদ")
    scenes = script_data.get("scenes", [])
    date_label = script_data.get("date") or datetime.now(DHAKA_TZ).strftime("%Y-%m-%d")
    run_id = script_data.get("run_id", 1)
    bn_date_str = format_bangla_date()

    print(f"মূল খবর      : {headline}")
    print(f"বাংলা তারিখ   : {bn_date_str}")
    print(f"ছবি ফোল্ডার  : {images_dir}")

    # ছবি তালিকা
    img_files = []
    if os.path.exists(images_dir):
        img_files = sorted([f for f in os.listdir(images_dir) if f.lower().endswith((".jpg", ".jpeg", ".png"))])

    if not img_files:
        print("কোনো ছবি পাওয়া যায়নি। News Collector Agent থেকে ছবি সংগ্রহ করুন।")
        sys.exit(1)

    print(f"মোট ছবি পাওয়া গেছে: {len(img_files)}টি")

    # আউটপুট ফোল্ডার নির্ধারণ
    run_dir = os.path.join(args.out, date_label, f"run_{run_id:02d}")
    cards_dir = os.path.join(run_dir, "cards")
    slides_dir = os.path.join(run_dir, "slides")
    os.makedirs(cards_dir, exist_ok=True)
    os.makedirs(slides_dir, exist_ok=True)

    items_to_process = scenes if scenes else [{"scene_num": i, "text": headline, "image_index": i} for i in range(1, len(img_files) + 1)]

    processed_slides = []
    print("\n[১/২] ছবি প্রসেসিং ও ব্র্যান্ডেড রিল স্লাইড তৈরি হচ্ছে...")

    for idx, item in enumerate(items_to_process, start=1):
        scene_num = item.get("scene_num", idx)
        img_idx = item.get("image_index", idx)

        # ইমেজ ফাইল নির্বাচন
        img_filename = f"news_{img_idx:02d}.jpg"
        img_path = os.path.join(images_dir, img_filename)
        if not os.path.exists(img_path):
            img_path = os.path.join(images_dir, img_files[(idx - 1) % len(img_files)])

        # দৃশ্যভিত্তিক ক্যাপশন
        scene_text = item.get("text", headline)
        caption = _clean_caption(scene_text) if idx > 1 else _clean_caption(headline)

        print(f"  [{idx:02d}/{len(items_to_process):02d}] দৃশ্য {scene_num}: {caption[:45]}...")

        # ১. ওয়াটারমার্ক ও নিচের ব্যানার ক্লিন করা
        clean_img = watermark_cleaner.clean_source_image(img_path, strip_bottom_banner=True)

        # ২. ব্র্যান্ডেড নিউজ কার্ড তৈরি
        card = card_composer.build_news_card(
            news_img=clean_img,
            headline=caption,
            date_str=bn_date_str,
            channel_name=args.channel,
            handle=args.handle,
        )

        card_path = os.path.join(cards_dir, f"card_{scene_num:02d}.png")
        card.save(card_path, "PNG")

        # ৩. ১০৮০ x ১৯২০ (৯:১৬ রিল ফ্রেম) স্লাইড তৈরি
        reel_slide = card_composer.compose_reel_slide(card, bg_image=clean_img)
        slide_path = os.path.join(slides_dir, f"slide_{scene_num:02d}.jpg")
        reel_slide.save(slide_path, "JPEG", quality=95)

        processed_slides.append({
            "scene_num": scene_num,
            "caption": caption,
            "raw_image": img_path,
            "card_image": card_path,
            "reel_slide": slide_path,
            "dimensions": {"width": 1080, "height": 1920},
        })

    # মেটাডাটা JSON সেভ করা
    meta_data = {
        "channel": args.channel,
        "handle": args.handle,
        "date": date_label,
        "bangla_date": bn_date_str,
        "run_id": run_id,
        "headline": headline,
        "total_slides": len(processed_slides),
        "slides": processed_slides,
    }

    meta_json_path = os.path.join(run_dir, "image_data.json")
    with open(meta_json_path, "w", encoding="utf-8") as fh:
        json.dump(meta_data, fh, ensure_ascii=False, indent=2)

    # latest ফোল্ডারে মিরর করা যাতে Video Creator Agent সহজেই সরাসরি নিতে পারে
    latest_dir = os.path.join(args.out, "latest")
    latest_cards = os.path.join(latest_dir, "cards")
    latest_slides = os.path.join(latest_dir, "slides")
    os.makedirs(latest_cards, exist_ok=True)
    os.makedirs(latest_slides, exist_ok=True)

    try:
        shutil.copy2(meta_json_path, os.path.join(latest_dir, "image_data.json"))
        for s in processed_slides:
            shutil.copy2(s["card_image"], os.path.join(latest_cards, os.path.basename(s["card_image"])))
            shutil.copy2(s["reel_slide"], os.path.join(latest_slides, os.path.basename(s["reel_slide"])))
    except Exception as exc:
        print(f"সতর্কতা: latest ফোল্ডারে মিরর করতে সমস্যা ({exc})")

    elapsed = round(time.time() - started, 1)
    print("\n==================================================================")
    print("✅ ইমেজ এডিটিং ও রিল স্লাইড তৈরি সম্পন্ন!")
    print(f"  মোট স্লাইড    : {len(processed_slides)}টি (১০৮০ x ১৯২০ রিল ফ্রেম)")
    print(f"  কার্ড ফোল্ডার  : {cards_dir}")
    print(f"  রিল স্লাইড     : {slides_dir}")
    print(f"  মেটাডাটা ফাইল  : {meta_json_path}")
    print(f"  প্রসেসিং সময়   : {elapsed} সেকেন্ড")
    print("==================================================================")


if __name__ == "__main__":
    main()

