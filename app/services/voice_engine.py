import os
import re
import asyncio
from pathlib import Path
import edge_tts
from app.config import VOICE_MAP, OUTPUT_DIR

def format_ass_time(seconds: float) -> str:
    """Formats float seconds into ASS timestamp: H:MM:SS.cs"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs >= 100:
        cs = 99
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

def parse_srt_time(time_str: str) -> float:
    """Parses SRT time string 00:00:01,234 into float seconds."""
    time_str = time_str.strip().replace(',', '.')
    parts = time_str.split(':')
    if len(parts) == 3:
        h, m, s = parts
        return float(h) * 3600 + float(m) * 60 + float(s)
    return 0.0

def srt_to_reels_ass(srt_content: str, ass_path: Path, language: str = "bn"):
    """
    Converts SRT chunks into vibrant, modern Instagram Reels / TikTok style ASS subtitles.
    Splits long sentences into 3-5 word rhythmic chunks and highlights keywords.
    """
    ass_header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial Black,72,&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,6,3,2,60,60,400,1
Style: Punchline,Arial Black,80,&H0000FFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,105,105,1,0,1,8,4,2,50,50,420,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    dialogue_lines = []

    # Parse SRT blocks
    blocks = re.split(r'\n\s*\n', srt_content.strip())
    for block in blocks:
        lines = [line.strip() for line in block.split('\n') if line.strip()]
        if len(lines) >= 3 and '-->' in lines[1]:
            timing = lines[1]
            text = " ".join(lines[2:])

            start_str, end_str = timing.split('-->')
            start_sec = parse_srt_time(start_str)
            end_sec = parse_srt_time(end_str)
            total_duration = max(0.5, end_sec - start_sec)

            # Split into 3-5 word sub-chunks for reels tempo
            words = text.split()
            if not words:
                continue

            chunk_size = 4
            sub_chunks = [words[i:i + chunk_size] for i in range(0, len(words), chunk_size)]
            chunk_duration = total_duration / len(sub_chunks)

            for i, chunk in enumerate(sub_chunks):
                c_start = start_sec + (i * chunk_duration)
                c_end = c_start + chunk_duration

                t_start = format_ass_time(c_start)
                t_end = format_ass_time(c_end)

                chunk_text = " ".join(chunk).upper()

                # Highlight the first or last word in yellow
                words_in_chunk = chunk_text.split()
                if len(words_in_chunk) > 1:
                    styled_text = f"\\c&H0000FFFF&{words_in_chunk[0]}\\c&H00FFFFFF& " + " ".join(words_in_chunk[1:])
                else:
                    styled_text = f"\\c&H0000FFFF&{chunk_text}"

                dialogue_lines.append(
                    f"Dialogue: 0,{t_start},{t_end},Default,,0,0,0,,{{{styled_text}}}"
                )

    full_ass = ass_header + "\n".join(dialogue_lines) + "\n"
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(full_ass)

async def generate_speech(text: str, language: str = "bn", gender: str = "female", job_id: str = "temp") -> dict:
    """
    Generates neural audio and word-aligned Reels ASS subtitle file using edge-tts.
    Returns: {"audio_path": Path, "ass_path": Path, "duration": float}
    """
    lang = language.lower() if language.lower() in VOICE_MAP else "bn"
    voice = VOICE_MAP[lang].get(gender, VOICE_MAP[lang]["default"])

    audio_path = OUTPUT_DIR / f"{job_id}_voice.mp3"
    ass_path = OUTPUT_DIR / f"{job_id}_subtitles.ass"

    # Edge TTS communicate
    comm = edge_tts.Communicate(text, voice)
    submaker = edge_tts.SubMaker()

    with open(audio_path, "wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "SentenceBoundary":
                submaker.feed(chunk)

    srt_content = submaker.get_srt()
    srt_to_reels_ass(srt_content, ass_path, language=lang)

    # Calculate duration
    try:
        from moviepy import AudioFileClip
        clip = AudioFileClip(str(audio_path))
        duration = clip.duration
        clip.close()
    except Exception:
        duration = 15.0

    return {
        "audio_path": audio_path,
        "ass_path": ass_path,
        "duration": duration
    }

