import asyncio
from app.services.voice_engine import generate_speech

async def test_voices():
    print("--- Testing Voice & Subtitle Engine ---")
    test_cases = [
        ("bn", "যখনই ডিপ্রেশন বা প্যারা শুরু হয়, আমি কিন্তু কান্নাকাটি করি না।"),
        ("hi", "जब भी डिप्रेशन या टेंशन आए, तो ऊपर का टेंशन नीचे आ जाएगा।"),
        ("en", "Stress and anxiety take years off your life, which saves rent!")
    ]

    for lang, sample_text in test_cases:
        res = await generate_speech(sample_text, language=lang, job_id=f"test_{lang}")
        print(f"\n[Language: {lang.upper()}]")
        print(f"Audio Path: {res['audio_path']} (Exists: {res['audio_path'].exists()})")
        print(f"ASS Subtitles: {res['ass_path']} (Exists: {res['ass_path'].exists()})")
        print(f"Duration: {res['duration']:.2f}s")
        assert res['audio_path'].exists(), "Audio file was not created!"
        assert res['ass_path'].exists(), "ASS subtitle file was not created!"

if __name__ == "__main__":
    asyncio.run(test_voices())

