import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import audio_mixer
import caption_renderer
import outro_renderer
import video_engine

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
VOICE_AGENT_DIR = os.path.join(PROJECT_DIR, "Voice Over Agent")
IMAGE_AGENT_DIR = os.path.join(PROJECT_DIR, "Image Editor Agent")
DHAKA_TZ = timezone(timedelta(hours=6))


def load_pipeline_data():
    audio_meta_path = os.path.join(VOICE_AGENT_DIR, "output", "latest", "audio_data.json")
    if not os.path.exists(audio_meta_path):
        raise FileNotFoundError(f"অডিও মেটাডাটা পাওয়া যায়নি: {audio_meta_path}")

    with open(audio_meta_path, "r", encoding="utf-8") as fh:
        audio_data = json.load(fh)

    slides_dir = os.path.join(IMAGE_AGENT_DIR, "output", "latest", "slides")
    if not os.path.exists(slides_dir):
        raise FileNotFoundError(f"রিল স্লাইড ফোল্ডার পাওয়া যায়নি: {slides_dir}")

    return audio_data, slides_dir


def main():
    parser = argparse.ArgumentParser(description="Bangalii Facts AI Reel Creator with Dynamic Captions & Ambient BGM")
    parser.add_argument("--out", default=os.path.join(BASE_DIR, "output"), help="আউটপুট ফোল্ডার")
    parser.add_argument("--bgm-volume", type=float, default=0.18, help="ব্যাকগ্রাউন্ড মিউজিক ভলিউম (ডিফল্ট: 0.18)")
    parser.add_argument("--no-captions", action="store_true", help="ডায়নামিক ক্যাপশন বন্ধ রাখা")
    parser.add_argument("--no-bgm", action="store_true", help="ব্যাকগ্রাউন্ড মিউজিক বন্ধ রাখা")
    args = parser.parse_args()

    started = time.time()
    print("==================================================================")
    print("  AI Reels Creator — Video Creator Agent")
    print("  ডায়নামিক ক্যাপশন ও ব্যাকগ্রাউন্ড মিউজিক সহ ১০৮০ x ১৯২০ রিল তৈরি")
    print("==================================================================")

    try:
        audio_data, slides_dir = load_pipeline_data()
    except Exception as exc:
        print(f"ইনপুট ডেটা লোড ব্যর্থ: {exc}")
        sys.exit(1)

    headline = audio_data.get("headline", "ব্রেকিং নিউজ")
    date_label = audio_data.get("date") or datetime.now(DHAKA_TZ).strftime("%Y-%m-%d")
    run_id = audio_data.get("run_id", 1)
    voice_name = audio_data.get("voice", "Charon")
    segments = audio_data.get("segments", [])
    total_audio_duration = audio_data.get("total_duration", 0.0)
    full_audio_file = audio_data.get("full_audio")

    print(f"মূল খবর       : {headline}")
    print(f"তারিখ         : {date_label}  |  রান নং: #{run_id:02d}")
    print(f"ভয়েস কণ্ঠ      : {voice_name} (Gemini AI Native)")
    print(f"মোট দৃশ্য      : {len(segments)}টি (মোট সময়: {total_audio_duration}s)")
    print(f"ফিচারস        : ডায়নামিক ক্যাপশন: {'চালু' if not args.no_captions else 'বন্ধ'} | BGM: {'চালু' if not args.no_bgm else 'বন্ধ'}")

    # আউটপুট ডিরেক্টরি
    run_dir = os.path.join(args.out, date_label, f"run_{run_id:02d}")
    temp_clips_dir = os.path.join(run_dir, "temp_scene_clips")
    temp_caps_dir = os.path.join(run_dir, "temp_caption_pills")
    os.makedirs(temp_clips_dir, exist_ok=True)
    os.makedirs(temp_caps_dir, exist_ok=True)

    # ধাপ ১: ব্যাকগ্রাউন্ড মিউজিক মিক্সিং
    mixed_audio_path = None
    if not args.no_bgm and full_audio_file and os.path.exists(full_audio_file):
        print("\n[১/৩] হালকা অ্যাম্বিয়েন্ট ব্যাকগ্রাউন্ড মিউজিক মিক্স করা হচ্ছে...")
        mixed_audio_path = os.path.join(run_dir, "final_mixed_audio.mp3")
        audio_mixer.mix_voiceover_and_bgm(
            vocal_path=full_audio_file,
            output_path=mixed_audio_path,
            bgm_volume=args.bgm_volume,
        )

    # ধাপ ২: প্রতিটি দৃশ্যের রেন্ডারিং
    rendered_clips = []
    print("\n[২/৩] ডায়নামিক ক্যাপশন ও সিনেমাটিক জুম সহ দৃশ্যগুলো রেন্ডার হচ্ছে...")

    for idx, seg in enumerate(segments, start=1):
        scene_num = seg.get("scene_num", idx)
        duration = float(seg.get("duration", 8.0))
        # দৃশ্য পরিবর্তনের জন্য প্রতিটি দৃশ্যের শেষে অতিরিক্ত ০.৫ সেকেন্ড প্যাডিং
        # যাতে ভয়েস-ওভার পজের সাথে সিন পারফেক্ট সিঙ্ক থাকে এবং কোনো কথা না কাটে
        padded_duration = round(duration + 0.5, 2)
        scene_text = seg.get("text", "")
        audio_file = seg.get("audio_file")
        if not audio_file or not os.path.exists(audio_file):
            audio_file = os.path.join(VOICE_AGENT_DIR, "output", "latest", f"segments_{voice_name.lower()}", f"{scene_num:02d}_scene_{scene_num:02d}.mp3")

        slide_name = f"slide_{scene_num:02d}.jpg"
        slide_path = os.path.join(slides_dir, slide_name)
        if not os.path.exists(slide_path):
            slide_path = os.path.join(slides_dir, "slide_01.jpg")

        # ডায়নামিক ক্যাপশন ওভারলে জেনারেট করা
        caption_overlays = []
        if not args.no_captions and scene_text:
            caption_overlays = caption_renderer.generate_scene_caption_overlays(
                scene_text=scene_text,
                duration_sec=duration,
                temp_dir=temp_caps_dir,
                scene_num=scene_num,
            )

        zoom_dir = "in" if idx % 2 != 0 else "out"
        scene_clip_path = os.path.join(temp_clips_dir, f"clip_scene_{scene_num:02d}.mp4")

        cap_count = len(caption_overlays)
        print(f"  [{idx:02d}/{len(segments):02d}] দৃশ্য {scene_num}: {duration}s (+0.5s pause) | Zoom-{zoom_dir.upper()} | {cap_count}টি ক্যাপশন ফেজ...")

        video_engine.render_scene_clip(
            slide_path=slide_path,
            audio_path=audio_file,
            duration_sec=padded_duration,
            output_path=scene_clip_path,
            zoom_direction=zoom_dir,
            caption_overlays=caption_overlays,
        )
        rendered_clips.append(scene_clip_path)

    # ব্র্যান্ডেড আউটরো স্লাইড ও ক্লিপ রেন্ডার করা (চ্যানেল লোগো + ফলো করুন বাটন)
    print("\n  [আউটরো] বাঙালি ফ্যাক্টস ব্র্যান্ডেড ফলো আউটরো তৈরি হচ্ছে...")
    outro_img_path = os.path.join(temp_clips_dir, "outro_slide.jpg")
    outro_renderer.render_outro_slide(outro_img_path)

    outro_clip_path = os.path.join(temp_clips_dir, "clip_outro.mp4")
    outro_duration = 3.5  # ৩.৫ সেকেন্ডের মনোমুগ্ধকর আউটরো
    video_engine.render_scene_clip(
        slide_path=outro_img_path,
        audio_path=audio_file,  # ডামি রেফারেন্স
        duration_sec=outro_duration,
        output_path=outro_clip_path,
        zoom_direction="in",
        caption_overlays=None,
    )
    rendered_clips.append(outro_clip_path)

    # আউটরো সহ সম্পূর্ণ অডিওর জন্য BGM প্রসারিত করা (যদি BGM থাকে)
    if mixed_audio_path and os.path.exists(mixed_audio_path):
        extended_mixed_audio = os.path.join(run_dir, "final_mixed_with_outro.mp3")
        ffmpeg_bin = video_engine.get_ffmpeg()
        total_full_duration = round(total_audio_duration + outro_duration, 2)
        # অডিওকে পুরো দৈর্ঘ্য পর্যন্ত ব্যাকগ্রাউন্ড অ্যাম্বিয়েন্ট সহ সুন্দরভাবে ফেড আউট করা
        cmd_ext = [
            ffmpeg_bin, "-y",
            "-i", mixed_audio_path,
            "-af", f"apad=whole_dur={total_full_duration},afade=t=out:st={total_full_duration - 1.0}:d=1.0",
            "-c:a", "libmp3lame",
            "-b:a", "192k",
            extended_mixed_audio,
        ]
        subprocess.run(cmd_ext, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(extended_mixed_audio):
            mixed_audio_path = extended_mixed_audio

    # ধাপ ৩: সমস্ত ক্লিপ একত্রিত করে ফাইনাল রিল তৈরি করা
    print("\n[৩/৩] সম্পূর্ণ ভিডিও জোড়া দিয়ে ফাইনাল রিল তৈরি করা হচ্ছে...")
    final_video_name = f"reel_{date_label}_run{run_id:02d}.mp4"
    final_video_path = os.path.join(run_dir, final_video_name)

    video_engine.concatenate_clips(
        clip_paths=rendered_clips,
        output_path=final_video_path,
        final_audio_path=mixed_audio_path,
    )

    # latest ফোল্ডারে মিরর করা
    latest_dir = os.path.join(args.out, "latest")
    os.makedirs(latest_dir, exist_ok=True)
    latest_video_path = os.path.join(latest_dir, "reel_latest.mp4")
    try:
        shutil.copy2(final_video_path, latest_video_path)
    except Exception as exc:
        print(f"সতর্কতা: latest ফোল্ডারে কপি করতে সমস্যা ({exc})")

    file_size_mb = round(os.path.getsize(final_video_path) / (1024 * 1024), 2)
    elapsed = round(time.time() - started, 1)

    print("\n==================================================================")
    print("🎬 ডায়নামিক ক্যাপশন ও BGM সহ এআই রিল সফলভাবে রেন্ডার হয়েছে!")
    print(f"  ভিডিও ফাইল     : {final_video_path}")
    print(f"  লেটেস্ট কপি    : {latest_video_path}")
    print(f"  ভিডিও সাইজ     : {file_size_mb} MB")
    print(f"  মোট সময়কাল     : {total_audio_duration} সেকেন্ড")
    print(f"  রেজুলেশন       : ১০৮০ x ১৯২০ (৯:১৬ ভার্টিক্যাল রিল)")
    print(f"  রেন্ডার সময়    : {elapsed} সেকেন্ড")
    print("==================================================================")


if __name__ == "__main__":
    main()
