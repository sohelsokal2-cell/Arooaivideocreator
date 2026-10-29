import os
import subprocess
import asyncio
from pathlib import Path
import imageio_ffmpeg
from app.config import PUNCHLINE_BEAT_PATH, OUTPUT_DIR

def get_ffmpeg_binary() -> str:
    """Returns the bundled or system ffmpeg binary path."""
    try:
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"

async def compose_final_video(raw_video_path: Path, ass_path: Path, job_id: str, add_beat: bool = True) -> Path:
    """
    Composes the final Reels video:
    1. Layers comedic punchline beat sound effect towards the end.
    2. Burns dynamic Reels-style ASS subtitles onto the video.
    Returns: Path to the final ready-to-share MP4 video.
    """
    loop = asyncio.get_event_loop()
    final_output = OUTPUT_DIR / f"{job_id}_final.mp4"
    temp_audio_mixed = OUTPUT_DIR / f"{job_id}_mixed.mp4"

    def _process():
        ffmpeg_exe = get_ffmpeg_binary()

        # Step 1: Optional punchline beat mix using MoviePy
        current_video = raw_video_path
        if add_beat and PUNCHLINE_BEAT_PATH.exists():
            try:
                from moviepy import VideoFileClip, AudioFileClip, CompositeAudioClip
                v_clip = VideoFileClip(str(raw_video_path))
                v_dur = v_clip.duration

                beat_clip = AudioFileClip(str(PUNCHLINE_BEAT_PATH))
                beat_dur = beat_clip.duration

                # Align beat to the last 3.5 seconds
                start_time = max(0, v_dur - 3.8)
                sub_beat = beat_clip.subclipped(0, min(beat_dur, v_dur - start_time)).with_start(start_time).with_volume_scaled(0.7)

                original_audio = v_clip.audio
                mixed_audio = CompositeAudioClip([original_audio, sub_beat])
                v_with_beat = v_clip.with_audio(mixed_audio)

                v_with_beat.write_videofile(
                    str(temp_audio_mixed),
                    fps=24,
                    codec="libx264",
                    audio_codec="aac",
                    preset="ultrafast",
                    logger=None
                )
                v_clip.close()
                beat_clip.close()
                current_video = temp_audio_mixed
            except Exception as e:
                print(f"Error mixing punchline beat: {e}, continuing with original audio.")
                current_video = raw_video_path

        # Step 2: Burn ASS subtitles with FFmpeg
        # Format path for FFmpeg subtitle filter (escape colons and backslashes for Windows)
        escaped_ass = str(ass_path).replace("\\", "/").replace(":", "\\:")
        sub_filter = f"ass='{escaped_ass}'"

        cmd = [
            ffmpeg_exe,
            "-y",
            "-i", str(current_video),
            "-vf", sub_filter,
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "22",
            "-c:a", "copy",
            str(final_output)
        ]

        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if p.returncode != 0:
            print(f"FFmpeg subtitle burn error: {p.stderr}. Returning uncaptioned video as fallback.")
            if current_video != final_output:
                import shutil
                shutil.copy(current_video, final_output)

        # Cleanup intermediate mixed video
        if temp_audio_mixed.exists() and temp_audio_mixed != final_output:
            try:
                os.remove(temp_audio_mixed)
            except Exception:
                pass

        return final_output

    return await loop.run_in_executor(None, _process)

