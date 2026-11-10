import os
import subprocess
import sys
import tempfile
import imageio_ffmpeg


def get_ffmpeg():
    """Return path to ffmpeg binary from imageio-ffmpeg."""
    return imageio_ffmpeg.get_ffmpeg_exe()


def get_sample_rate(file_path, default=24000):
    """Detect sample rate of an audio file to avoid mismatched concat streams."""
    try:
        ffmpeg = get_ffmpeg()
        res = subprocess.run(
            [ffmpeg, "-i", file_path],
            capture_output=True, text=True, errors="ignore"
        )
        import re
        m = re.search(r"(\d{4,6})\s*Hz", res.stderr)
        if m:
            return int(m.group(1))
    except Exception:
        pass
    return default


def create_silence(duration_sec, output_path, sample_rate=24000):
    """Generate a silence MP3 file matching the source sample rate."""
    ffmpeg = get_ffmpeg()
    cmd = [
        ffmpeg,
        "-y",
        "-f", "lavfi",
        "-i", f"anullsrc=r={sample_rate}:cl=mono",
        "-t", str(duration_sec),
        "-acodec", "libmp3lame",
        "-b:a", "192k",
        output_path,
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return output_path


def _export_ogg_if_requested(output_path, also_ogg):
    """Telegram-compat Opus export. একক/বহু-সেগমেন্ট দুটো পথেই কল করা হয়।"""
    if not also_ogg:
        return
    ffmpeg = get_ffmpeg()
    ogg_path = os.path.splitext(output_path)[0] + ".ogg"
    res = subprocess.run(
        [ffmpeg, "-y", "-i", output_path, "-c:a", "libopus", "-b:a", "64k", ogg_path],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )
    if res.returncode != 0:
        print(f"[audio_merger] OGG রূপান্তর ব্যর্থ (ffmpeg {res.returncode}): {ogg_path}", file=sys.stderr)


def merge_audio_files(file_paths, output_path, pause_sec=0.8, also_ogg=False):
    """
    Merge multiple MP3 audio files with a silence pause between them.
    Also optionally export a Telegram-compatible .ogg (Opus) file.
    """
    if not file_paths:
        raise ValueError("No files provided for merging")

    if len(file_paths) == 1:
        # Just copy or re-encode
        ffmpeg = get_ffmpeg()
        cmd = [ffmpeg, "-y", "-i", file_paths[0], output_path]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        _export_ogg_if_requested(output_path, also_ogg)
        return output_path

    ffmpeg = get_ffmpeg()
    with tempfile.TemporaryDirectory() as tmpdir:
        sr = get_sample_rate(file_paths[0])
        silence_file = os.path.join(tmpdir, "pause.mp3")
        if pause_sec > 0:
            create_silence(pause_sec, silence_file, sample_rate=sr)

        list_file = os.path.join(tmpdir, "concat.txt")
        with open(list_file, "w", encoding="utf-8") as f:
            for idx, fp in enumerate(file_paths):
                abs_p = os.path.abspath(fp).replace("\\", "/")
                f.write(f"file '{abs_p}'\n")
                if pause_sec > 0 and idx < len(file_paths) - 1:
                    silence_p = os.path.abspath(silence_file).replace("\\", "/")
                    f.write(f"file '{silence_p}'\n")

        # Concat using ffmpeg
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        cmd = [
            ffmpeg,
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_file,
            "-c", "copy",
            output_path,
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode != 0:
            # Fallback with re-encoding in case bitrates differ slightly
            cmd_reencode = [
                ffmpeg,
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", list_file,
                "-c:a", "libmp3lame",
                "-b:a", "192k",
                output_path,
            ]
            subprocess.run(cmd_reencode, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Optional .ogg conversion (Telegram style voice note)
    _export_ogg_if_requested(output_path, also_ogg)

    return output_path
