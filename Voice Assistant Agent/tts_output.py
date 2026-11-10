"""
Voice Assistant Agent — TTS Output Engine (Edge-TTS)
=====================================================
উচ্চমানের বাংলা কণ্ঠ (bn-BD-NabanitaNeural) দিয়ে টেক্সটকে অডিওতে রূপান্তর ও প্লে করে।
"""

import asyncio
import os
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

try:
    import edge_tts
    import imageio_ffmpeg
    HAS_TTS = True
except ImportError:
    HAS_TTS = False

def play_audio(audio_path: str):
    """FFmpeg/FFplay বা সিস্টেম প্লেয়ার দিয়ে অডিও শোনায়।"""
    if not os.path.exists(audio_path):
        return
    try:
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        ffplay_exe = os.path.join(os.path.dirname(ffmpeg_exe), "ffplay.exe")
        if os.path.exists(ffplay_exe):
            subprocess.run([ffplay_exe, "-nodisp", "-autoexit", "-loglevel", "quiet", audio_path], check=True)
            return
    except Exception:
        pass

    # Windows default playback
    if sys.platform == "win32":
        try:
            os.startfile(audio_path)
        except Exception:
            pass

async def _synthesize_async(text: str, voice: str, out_file: str):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(out_file)

def speak_text(text: str, voice: str = "bn-BD-NabanitaNeural", auto_play: bool = True) -> str | None:
    """টেক্সট থেকে বাংলা অডিও তৈরি করে এবং স্বয়ংক্রিয়ভাবে প্লে করে।"""
    if not HAS_TTS or not text.strip():
        return None

    out_file = os.path.join(OUTPUT_DIR, "assistant_reply.mp3")
    try:
        asyncio.run(_synthesize_async(text, voice, out_file))
        if auto_play and os.path.exists(out_file):
            play_audio(out_file)
        return out_file
    except Exception as exc:
        print(f"      ⚠️  টিটিএস স্পিচ সতর্কতা: {exc}")
        return None

