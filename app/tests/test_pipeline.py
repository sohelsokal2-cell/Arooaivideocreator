import asyncio
from app.services.voice_engine import generate_speech
from app.services.character_service import get_or_create_character
from app.services.lip_sync_client import render_lip_sync
from app.services.video_composer import compose_final_video

async def test_full_pipeline():
    print("--- Running End-to-End Pipeline Test ---")
    job_id = "test_run"
    test_text = "যখনই জীবনে চরম প্যারা শুরু হয়, চাদর মুড়ি দিয়ে সোজা ঘুমিয়ে যান!"
    
    # 1. Voice
    print("1. Generating voice and subtitles...")
    voice_res = await generate_speech(test_text, language="bn", job_id=job_id)
    
    # 2. Character
    print("2. Fetching comedian character...")
    char_path = await get_or_create_character("default", job_id=job_id)
    print(f"Character ready: {char_path}")
    
    # 3. Lip-sync / Motion
    print("3. Generating video motion...")
    raw_video = await render_lip_sync(char_path, voice_res["audio_path"], job_id=job_id)
    print(f"Raw video created: {raw_video}")
    
    # 4. Final Compose (burn ASS subtitles + punchline beat)
    print("4. Compositing captions & punchline beat...")
    final_video = await compose_final_video(
        raw_video_path=raw_video,
        ass_path=voice_res["ass_path"],
        job_id=job_id,
        add_beat=True
    )
    print(f"\nSUCCESS! Final video generated at: {final_video}")
    print(f"Final file size: {final_video.stat().st_size / 1024:.2f} KB")
    assert final_video.exists() and final_video.stat().st_size > 1000, "Final video creation failed!"

if __name__ == "__main__":
    asyncio.run(test_full_pipeline())

