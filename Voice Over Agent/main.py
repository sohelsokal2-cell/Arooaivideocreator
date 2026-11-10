import argparse
import json
import os
import re
import shutil
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
_ENV_PATH = os.path.join(BASE_DIR, ".env")
if os.path.exists(_ENV_PATH):
    with open(_ENV_PATH, "r", encoding="utf-8-sig") as _fh:
        for _line in _fh:
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _k, _, _v = _line.partition("=")
            _k = _k.strip()
            _v = _v.strip().strip('"').strip("'")
            if _k and _k not in os.environ:
                os.environ[_k] = _v

import imageio_ffmpeg
import script_parser
import tts_engine

WRITER_DIR = os.path.join(os.path.dirname(BASE_DIR), "Writer Agent")


def get_audio_duration(file_path):
    """FFmpeg দিয়ে অডিও ফাইলের প্রকৃত দৈর্ঘ্য (সেকেন্ডে) নির্ণয় করা।"""
    try:
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        res = subprocess.run([ffmpeg, "-i", file_path], capture_output=True, text=True, errors="ignore")
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", res.stderr)
        if m:
            h, mi, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
            return round(h * 3600 + mi * 60 + s, 2)
    except Exception:
        pass
    return 0.0


def resolve_input_file(path_arg):
    if path_arg:
        full = os.path.abspath(path_arg)
        if not os.path.exists(full):
            print(f"ত্রুটি: স্ক্রিপ্ট ফাইল পাওয়া যায়নি: {full}")
            sys.exit(1)
        return full

    found = script_parser.find_latest_script(BASE_DIR, WRITER_DIR)
    if not found:
        print("কোনো script_data.json বা script_*.docx/txt পাওয়া যায়নি।")
        print("Writer Agent-এ স্ক্রিপ্ট তৈরি করুন অথবা --input দিন।")
        sys.exit(1)
    return found


def main():
    parser = argparse.ArgumentParser(
        description="Bangla AI Voice Over Generator (Gemini Studio Quality Natural Voice)"
    )
    parser.add_argument("--input", default="", help="স্ক্রিপ্ট ফাইলের পাথ (.json, .docx অথবা .txt)")
    parser.add_argument(
        "--voice",
        default=os.environ.get("DEFAULT_VOICE", "Kore"),
        help="ভয়েস নির্বাচন: Kore (মিষ্টি ও সাবলীল নারী কণ্ঠ), Aoede (সংবাদ উপস্থাপিকা নারী), Charon (পুরুষ)",
    )
    parser.add_argument(
        "--pause",
        type=float,
        default=float(os.environ.get("PAUSE_SECONDS", "0.8")),
        help="দৃশ্যের মাঝে স্বাভাবিক বিরতি (সেকেন্ডে, ডিফল্ট: 0.8)",
    )
    parser.add_argument("--out", default="", help="আউটপুট ফোল্ডার (ডিফল্ট: output/<তারিখ>)")
    parser.add_argument("--force", action="store_true", help="পূর্বে তৈরি ক্যাশ অগ্রাহ্য করে নতুন করে তৈরি করা")

    args = parser.parse_args()

    started_total = time.time()
    script_path = resolve_input_file(args.input)
    date_label, sections, script_meta = script_parser.parse_script(script_path)

    if not sections:
        print(f"স্ক্রিপ্টে কোনো কথ্য অংশ পাওয়া যায়নি: {script_path}")
        sys.exit(1)

    headline = script_meta.get("headline", "ব্রেকিং রিল")
    run_id = script_meta.get("run_id", 1)

    # আউটপুট ডিরেক্টরি নির্ধারণ
    if args.out:
        out_dir = os.path.abspath(args.out)
    else:
        out_dir = os.path.join(BASE_DIR, "output", date_label, f"run_{run_id:02d}")
    os.makedirs(out_dir, exist_ok=True)

    v_name = tts_engine.resolve_voice_name(args.voice)
    v_info = tts_engine.SUPPORTED_VOICES.get(v_name.lower(), {})
    total_words = sum(len(s["text"].split()) for s in sections)

    print("==================================================================")
    print("  AI Reels Creator — Voice Over Agent (Agent 3)")
    print("  স্টুডিও কোয়ালিটি প্রাকৃতিক বাংলা ভয়েস-ওভার তৈরি")
    print("==================================================================")
    print(f"ইনপুট স্ক্রিপ্ট : {script_path}")
    print(f"মূল বিষয়       : {headline}")
    print(f"নির্বাচিত কণ্ঠ   : {v_name} ({v_info.get('gender', 'Male')} — {v_info.get('description', '')})")
    print(f"মোট দৃশ্য/সেকশন: {len(sections)}টি (মোট {total_words} শব্দ)")
    print(f"দৃশ্যের বিরতি  : {args.pause} সেকেন্ড")
    print(f"আউটপুট ফোল্ডার  : {out_dir}")
    print("==================================================================")

    def on_prog(curr, tot, sec, vi, cached=False):
        w_count = len(sec["text"].split())
        title_snip = sec.get("title", f"দৃশ্য {curr}")
        status = "[সংরক্ষিত ক্যাশ ✓]" if cached else "[Gemini AI স্টুডিও জেনারেশন]..."
        print(f"  [{curr:02d}/{tot:02d}] {title_snip:<25} ({w_count} শব্দ) {status}")

    # ভয়েস জেনারেশন ও মার্জ
    t0 = time.time()
    result = tts_engine.process_sections(
        sections=sections,
        output_dir=out_dir,
        voice=v_name,
        pause_sec=args.pause,
        also_ogg=False,
        force=args.force,
        on_progress=on_prog,
    )

    elapsed = round(time.time() - t0, 1)

    if result.get("failed"):
        print("\n❌ কিছু সেগমেন্ট তৈরি ব্যর্থ হয়েছে। ইন্টারনেট সংযোগ বা API Key যাচাই করুন।")
        sys.exit(1)

    full_audio = result.get("full_audio")
    total_duration = get_audio_duration(full_audio) if full_audio else 0.0

    # সেগমেন্টের বিস্তারিত ডেটা প্রস্তুত করা
    segment_details = []
    for idx, (sec, s_file) in enumerate(zip(sections, result.get("segment_files", [])), start=1):
        s_dur = get_audio_duration(s_file)
        segment_details.append({
            "scene_num": idx,
            "title": sec.get("title", f"দৃশ্য {idx}"),
            "text": sec["text"],
            "image_index": sec.get("image_index", idx),
            "audio_file": s_file,
            "duration": s_dur,
        })

    # অডিও মেটাডাটা JSON সেভ করা
    audio_meta = {
        "headline": headline,
        "date": date_label,
        "run_id": run_id,
        "voice": v_name,
        "total_words": total_words,
        "total_duration": total_duration,
        "full_audio": full_audio,
        "segments_dir": result.get("segments_dir"),
        "segments": segment_details,
    }

    json_path = os.path.join(out_dir, "audio_data.json")
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(audio_meta, fh, ensure_ascii=False, indent=2)

    # latest ফোল্ডারে মিরর করা যাতে Video Creator Agent সহজেই সরাসরি পায়
    latest_dir = os.path.join(BASE_DIR, "output", "latest")
    os.makedirs(latest_dir, exist_ok=True)
    try:
        shutil.copy2(full_audio, os.path.join(latest_dir, f"full_voiceover_{v_name.lower()}.mp3"))
        shutil.copy2(json_path, os.path.join(latest_dir, "audio_data.json"))
        latest_seg_dir = os.path.join(latest_dir, f"segments_{v_name.lower()}")
        if os.path.exists(latest_seg_dir):
            shutil.rmtree(latest_seg_dir)
        shutil.copytree(result.get("segments_dir"), latest_seg_dir)
    except Exception as exc:
        print(f"সতর্কতা: latest ফোল্ডারে কপি করতে সমস্যা ({exc})")

    file_size_kb = round(os.path.getsize(full_audio) / 1024, 1) if full_audio else 0

    print("\n==================================================================")
    print("✅ প্রাকৃতিক বাংলা ভয়েস-ওভার সফলভাবে তৈরি হয়েছে!")
    print(f"  কণ্ঠ মডেল      : {v_name} (Gemini AI Native Studio Audio)")
    print(f"  মোট সময়কাল    : {total_duration} সেকেন্ড (৪৫-৬০ সেকেন্ড লক্ষ্যমাত্রা পূর্ণ)")
    print(f"  সম্পূর্ণ অডিও   : {full_audio} ({file_size_kb} KB)")
    print(f"  সেগমেন্ট অডিও   : {result.get('segments_dir')} ({len(segment_details)}টি ফাইল)")
    print(f"  অডিও মেটাডাটা  : {json_path}")
    print(f"  প্রসেসিং সময়   : {elapsed} সেকেন্ড")
    print("==================================================================")


if __name__ == "__main__":
    main()
