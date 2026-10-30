#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║       AI Stand-Up Comedy Reels Creator  🎤🎬                    ║
║  One command → Full 9:16 vertical MP4 with captions + beat       ║
╚══════════════════════════════════════════════════════════════════╝

Usage:
    python create_reel.py                        # Bangla, auto topic
    python create_reel.py --lang hi              # Hindi
    python create_reel.py --lang en --topic "dating apps"
    python create_reel.py --lang bn --topic "পরীক্ষার আগে রাত"
"""

import argparse
import asyncio
import sys
import os
import time
import subprocess
from pathlib import Path

# Fix unicode output on Windows terminal
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ─── Project Root ──────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from app.config import (
    GEMINI_API_KEY, OUTPUT_DIR, DEFAULT_CHARACTER_PATH,
    PUNCHLINE_BEAT_PATH, VOICE_MAP
)
from app.services.script_generator import generate_script
from app.services.voice_engine import generate_speech

# ─── Helpers ───────────────────────────────────────────────────────────────────

def banner():
    print("\n" + "═" * 62)
    print("  🎤  AI Stand-Up Comedy Reels Creator")
    print("═" * 62 + "\n")

def step(n: int, msg: str):
    print(f"\n[{n}/5] {msg}")
    print("─" * 50)

def success(msg: str):
    print(f"  ✅  {msg}")

def info(msg: str):
    print(f"  ℹ️   {msg}")

def error(msg: str):
    print(f"  ❌  {msg}")

# ─── Step 4: Audio-Reactive Motion Video ───────────────────────────────────────

def generate_motion_video(
    image_path: Path,
    audio_path: Path,
    output_path: Path,
    fps: int = 24
) -> Path:
    """
    Creates a 9:16 vertical video from a still image + audio.
    Applies audio-amplitude-driven zoom + subtle vertical head-bob
    so the character visually reacts to the voice.
    """
    import cv2
    import numpy as np
    from moviepy import AudioFileClip, ImageClip

    info("Loading audio for amplitude analysis...")
    audio = AudioFileClip(str(audio_path))
    duration = audio.duration
    n_frames = int(duration * fps)

    # ── Build per-frame amplitude array ──
    # Sample audio at fps rate → amplitude curve
    try:
        audio_arr = audio.to_soundarray(fps=fps)          # shape (n, channels)
        if audio_arr.ndim > 1:
            audio_arr = audio_arr.mean(axis=1)             # mono
        # Pad / trim to exactly n_frames
        if len(audio_arr) < n_frames:
            audio_arr = np.pad(audio_arr, (0, n_frames - len(audio_arr)))
        else:
            audio_arr = audio_arr[:n_frames]
        # Normalize 0→1
        peak = np.abs(audio_arr).max()
        if peak > 0:
            amp = np.abs(audio_arr) / peak
        else:
            amp = np.zeros(n_frames)
        # Smooth amplitude curve (rolling average over 0.15 s)
        kernel_size = max(1, int(fps * 0.15))
        kernel = np.ones(kernel_size) / kernel_size
        amp = np.convolve(amp, kernel, mode="same")
    except Exception:
        info("Amplitude analysis failed — using default sine animation.")
        t_arr = np.linspace(0, duration, n_frames)
        amp = 0.5 + 0.5 * np.sin(t_arr * 1.5)

    # ── Read & prepare source image ──
    img_bgr = cv2.imread(str(image_path))
    if img_bgr is None:
        raise FileNotFoundError(f"Character image not found: {image_path}")

    TARGET_W, TARGET_H = 720, 1280  # 9:16

    # Resize image to cover target while keeping aspect ratio
    ih, iw = img_bgr.shape[:2]
    scale_to_fit = max(TARGET_W / iw, TARGET_H / ih) * 1.1  # 10% headroom for zoom
    fit_w = int(iw * scale_to_fit)
    fit_h = int(ih * scale_to_fit)
    img_base = cv2.resize(img_bgr, (fit_w, fit_h), interpolation=cv2.INTER_LANCZOS4)

    # ── Write video frame-by-frame ──
    info(f"Rendering {n_frames} frames @ {fps}fps  ({duration:.1f}s)...")
    temp_video = output_path.with_suffix(".raw.mp4")

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(temp_video), fourcc, fps, (TARGET_W, TARGET_H))

    for i in range(n_frames):
        a = float(amp[i])
        t = i / fps

        # Zoom: 1.0 (quiet) → 1.06 (loud)
        zoom = 1.0 + 0.06 * a
        # Vertical bob: slow sine oscillation + slight amplitude nudge
        bob_px = int(fit_h * 0.015 * np.sin(t * 1.2) + fit_h * 0.01 * a)

        zh = int(fit_h * zoom)
        zw = int(fit_w * zoom)
        zoomed = cv2.resize(img_base, (zw, zh), interpolation=cv2.INTER_LINEAR)

        # Center-crop 720×1280 with bob offset
        y_center = zh // 2 + bob_px
        x_center = zw // 2
        y1 = max(0, y_center - TARGET_H // 2)
        x1 = max(0, x_center - TARGET_W // 2)
        y2 = y1 + TARGET_H
        x2 = x1 + TARGET_W
        # Clamp
        if y2 > zh:
            y2 = zh; y1 = max(0, y2 - TARGET_H)
        if x2 > zw:
            x2 = zw; x1 = max(0, x2 - TARGET_W)

        frame = zoomed[y1:y2, x1:x2]
        # Safety: ensure exact size
        if frame.shape[:2] != (TARGET_H, TARGET_W):
            frame = cv2.resize(frame, (TARGET_W, TARGET_H))

        writer.write(frame)

        if i % (fps * 2) == 0:
            pct = int(i / n_frames * 100)
            print(f"    ▶ {pct}%", end="\r", flush=True)

    writer.release()
    print()  # newline after progress

    # ── Merge audio with OpenCV-written video using FFmpeg ──
    import imageio_ffmpeg
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    cmd = [
        ffmpeg_exe, "-y",
        "-i", str(temp_video),
        "-i", str(audio_path),
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
        "-c:a", "aac", "-shortest",
        str(output_path)
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        error(f"FFmpeg audio merge failed:\n{result.stderr.decode(errors='replace')}")
        # Just rename raw video as fallback
        temp_video.rename(output_path)
    else:
        try:
            temp_video.unlink()
        except Exception:
            pass

    audio.close()
    success(f"Motion video → {output_path.name}  ({output_path.stat().st_size // 1024} KB)")
    return output_path


# ─── Step 5: Burn Captions + Punchline Beat ────────────────────────────────────

def compose_final_video(
    raw_video: Path,
    ass_path: Path,
    job_id: str,
    add_beat: bool = True
) -> Path:
    import imageio_ffmpeg
    import shutil

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    final_output = OUTPUT_DIR / f"{job_id}_final.mp4"
    temp_beat_mix = OUTPUT_DIR / f"{job_id}_beatmix.mp4"
    current_video = raw_video

    # ── Mix punchline beat ──
    if add_beat and PUNCHLINE_BEAT_PATH.exists():
        info("Mixing punchline beat...")
        try:
            from moviepy import VideoFileClip, AudioFileClip, CompositeAudioClip
            v = VideoFileClip(str(raw_video))
            beat = AudioFileClip(str(PUNCHLINE_BEAT_PATH))
            start_t = max(0, v.duration - 3.8)
            beat_sub = (
                beat.subclipped(0, min(beat.duration, v.duration - start_t))
                    .with_start(start_t)
                    .with_volume_scaled(0.7)
            )
            mixed = CompositeAudioClip([v.audio, beat_sub])
            v_beat = v.with_audio(mixed)
            v_beat.write_videofile(
                str(temp_beat_mix),
                fps=24, codec="libx264", audio_codec="aac",
                preset="ultrafast", logger=None
            )
            v.close(); beat.close()
            current_video = temp_beat_mix
            success("Punchline beat mixed.")
        except Exception as e:
            info(f"Beat mix skipped ({e})")

    # ── Burn ASS subtitles ──
    info("Burning animated captions...")
    escaped_ass = str(ass_path).replace("\\", "/").replace(":", "\\:")
    sub_filter = f"ass='{escaped_ass}'"

    cmd = [
        ffmpeg_exe, "-y",
        "-i", str(current_video),
        "-vf", sub_filter,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
        "-c:a", "copy",
        str(final_output)
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0:
        error(f"Caption burn failed:\n{res.stderr.decode(errors='replace')[:600]}")
        shutil.copy(str(current_video), str(final_output))
        info("Saved video without captions as fallback.")
    else:
        success(f"Captions burned → {final_output.name}")

    # Cleanup temp beat-mix
    if temp_beat_mix.exists() and temp_beat_mix != final_output:
        try: temp_beat_mix.unlink()
        except Exception: pass

    return final_output


# ─── Main Pipeline ─────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(
        description="AI Stand-Up Comedy Reels Creator 🎤",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("--lang", choices=["bn", "hi", "en"], default="bn",
                        help="Language: bn=Bangla, hi=Hindi, en=English (default: bn)")
    parser.add_argument("--topic", default="auto",
                        help="Comedy topic. Use 'auto' to let AI pick. (default: auto)")
    parser.add_argument("--gender", choices=["female", "male"], default="female",
                        help="Voice gender (default: female)")
    parser.add_argument("--no-beat", action="store_true",
                        help="Skip the punchline beat sound effect")
    args = parser.parse_args()

    banner()

    job_id = f"reel_{int(time.time())}"
    lang_labels = {"bn": "বাংলা 🇧🇩", "hi": "हिंदी 🇮🇳", "en": "English 🇺🇸"}

    # ── [1/5] Generate Script ──────────────────────────────────────────────────
    step(1, f"Generating script  |  Language: {lang_labels[args.lang]}  |  Topic: {args.topic}")
    if not GEMINI_API_KEY:
        info("No GEMINI_API_KEY found — using built-in fallback script.")

    data = await generate_script(language=args.lang, topic=args.topic)
    topic = data["topic"]
    script = data["script"]

    print(f"\n  📝  Topic : {topic}")
    print(f"  💬  Script:\n")
    for line in script.split(". "):
        print(f"      {line.strip()}")
    print()

    answer = input("  ▶ Proceed? [Y/n]: ").strip().lower()
    if answer == "n":
        print("\n  ↩️  Cancelled. Run again with a different topic or language.\n")
        return

    # ── [2/5] Generate Voice + Subtitles ──────────────────────────────────────
    step(2, "Generating neural voice & animated subtitles...")
    voice_data = await generate_speech(
        text=script,
        language=args.lang,
        gender=args.gender,
        job_id=job_id
    )
    audio_path: Path = voice_data["audio_path"]
    ass_path: Path = voice_data["ass_path"]
    duration: float = voice_data["duration"]
    success(f"Audio: {audio_path.name}  ({duration:.1f}s)")
    success(f"Subtitles: {ass_path.name}")

    # ── [3/5] Prepare Character ────────────────────────────────────────────────
    step(3, "Preparing comedian character...")
    if DEFAULT_CHARACTER_PATH.exists():
        char_path = DEFAULT_CHARACTER_PATH
        success(f"Using: {char_path.name}")
    else:
        error("Default comedian image not found!")
        error(f"Expected: {DEFAULT_CHARACTER_PATH}")
        print("\n  Please add a portrait image to assets/characters/default_comedian.png")
        return

    # ── [4/5] Render Motion Video ──────────────────────────────────────────────
    step(4, "Rendering audio-reactive motion video  (CPU only)...")
    raw_video = OUTPUT_DIR / f"{job_id}_raw.mp4"
    try:
        generate_motion_video(
            image_path=char_path,
            audio_path=audio_path,
            output_path=raw_video
        )
    except Exception as e:
        error(f"Motion render failed: {e}")
        import traceback; traceback.print_exc()
        return

    # ── [5/5] Compose Final Reel ───────────────────────────────────────────────
    step(5, "Composing final reel (captions + punchline beat)...")
    try:
        final_video = compose_final_video(
            raw_video=raw_video,
            ass_path=ass_path,
            job_id=job_id,
            add_beat=not args.no_beat
        )
    except Exception as e:
        error(f"Composition failed: {e}")
        import traceback; traceback.print_exc()
        return

    # ── Done! ──────────────────────────────────────────────────────────────────
    print("\n" + "═" * 62)
    print("  🎉  YOUR REEL IS READY!")
    print(f"  📂  {final_video}")
    print("═" * 62 + "\n")

    # Open output folder in Explorer
    try:
        subprocess.Popen(f'explorer /select,"{final_video}"')
    except Exception:
        pass


if __name__ == "__main__":
    asyncio.run(main())

