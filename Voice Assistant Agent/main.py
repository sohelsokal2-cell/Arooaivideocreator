"""
Voice Assistant Agent — Interactive CLI & Voice Orchestrator
=============================================================
বাঙালি ফ্যাক্টস (@bangaliifacts) এআই ভয়েস সহকারী।
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

import groq_brain
import intent_handler
import tts_output

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
            if k:
                os.environ[k] = v

load_env()

def print_banner():
    print("=" * 70)
    print("  🎙️ AI REELS CREATOR — বাংলা ভয়েস অ্যাসিস্ট্যান্ট")
    print("  চ্যানেল: বাঙালি ফ্যাক্টস (@bangaliifacts)")
    print("  Groq AI Brain + Edge-TTS ভয়েস রেসপন্স")
    print("=" * 70)
    print("💡 আপনি টাইপ করতে পারেন:")
    print("   • 'নতুন রিল বানাও' (পুরো পাইপলাইন রান করবে)")
    print("   • 'আজকের খবর কি?' (সংগৃহীত সংবাদ জানাবে)")
    print("   • 'লিংক দেখাও' (ফেসবুক ও ইউটিউব পাবলিশ লিংক দেবে)")
    print("   • 'স্ট্যাটাস কি?' (সিস্টেমের অবস্থা বলবে)")
    print("   • 'বিদায়' বা 'exit' (বন্ধ করার জন্য)")
    print("-" * 70)

def main():
    parser = argparse.ArgumentParser(description="বাঙালি ফ্যাক্টস এআই ভয়েস অ্যাসিস্ট্যান্ট")
    parser.add_argument("--query", type=str, default="", help="সরাসরি একটি কমান্ড দিয়ে এক্সিকিউট করতে")
    parser.add_argument("--no-tts", action="store_true", help="ভয়েস আউটপুট বন্ধ রাখতে")
    args = parser.parse_args()

    print_banner()

    voice = os.environ.get("VA_TTS_VOICE", "bn-BD-NabanitaNeural")
    auto_play = os.environ.get("VA_AUTO_PLAY_AUDIO", "true").lower() == "true" and not args.no_tts

    # Single execution mode
    if args.query:
        process_query(args.query, voice, auto_play)
        return

    # Interactive Loop
    while True:
        try:
            print("\n🗣️ আপনি বলুন/লিখুন (Enter চাপুন):")
            user_input = input(">>> ").strip()
            if not user_input:
                continue

            should_stop = process_query(user_input, voice, auto_play)
            if should_stop:
                break
        except (KeyboardInterrupt, EOFError):
            print("\n👋 অ্যাসিস্ট্যান্ট বন্ধ করা হচ্ছে...")
            break

def process_query(user_input: str, voice: str, auto_play: bool) -> bool:
    context = intent_handler.get_pipeline_context()
    print("   🧠 প্রসেসিং চলছে...", end="\r")

    analysis = groq_brain.analyze_user_query(user_input, context)
    intent = analysis.get("intent", "chat")
    spoken = analysis.get("spoken_response", "")

    print(f"\n🤖 অ্যাসিস্ট্যান্ট ({intent}):")
    print(f"   💬 {spoken}")

    # Speak response using TTS
    if auto_play and spoken:
        print("   🔊 কথা বলছে...", end="\r")
        tts_output.speak_text(spoken, voice=voice, auto_play=True)
        print("                   ", end="\r")

    # Action execution
    if intent in ["run_pipeline", "get_news", "get_links", "check_status"]:
        res = intent_handler.execute_intent(intent)
        if res.get("msg"):
            print(f"\n📋 ফলাফল:\n{res['msg']}")
            if auto_play and intent in ["get_news", "get_links"]:
                tts_output.speak_text(res["msg"][:120], voice=voice, auto_play=True)

    if intent == "stop":
        return True

    return False

if __name__ == "__main__":
    main()

