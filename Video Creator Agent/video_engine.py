import json
import os
import subprocess
import sys
import tempfile
import time
import imageio_ffmpeg

VIDEO_W = 1080
VIDEO_H = 1920
FPS = 30


def get_ffmpeg():
    return imageio_ffmpeg.get_ffmpeg_exe()


def render_scene_clip(slide_path, audio_path, duration_sec, output_path, zoom_direction="in", caption_overlays=None):
    """
    সিনেম্যাটিক জুম এবং ডায়নামিক ক্যাপশন সহ একটি নির্দিষ্ট দৃশ্যের ভিডিও ক্লিপ রেন্ডার করে।
    """
    ffmpeg = get_ffmpeg()
    total_frames = max(int(duration_sec * FPS), FPS)

    # জুম ডিরেকশন ও সিনেম্যাটিক ডায়নামিক মোশন (ভিডিও যাতে স্থির ছবি মনে না হয়)
    if zoom_direction == "in":
        zoom_expr = "min(zoom+0.0007,1.12)"
    else:
        zoom_expr = "max(1.12-0.0007*(on),1.00)"

    # বেস জুমপ্যান ফিল্টার
    filter_chains = [
        f"[0:v]scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=decrease,"
        f"pad={VIDEO_W}:{VIDEO_H}:(ow-iw)/2:(oh-ih)/2,"
        f"zoompan=z='{zoom_expr}':d={total_frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={VIDEO_W}x{VIDEO_H}:fps={FPS}[v_base]"
    ]

    extra_inputs = []
    last_v = "v_base"

    # ডায়নামিক ক্যাপশন ওভারলে যোগ করা (যদি থাকে)
    if caption_overlays:
        # ইনপুট ইন্ডেক্স: 0 = slide, 1 = audio, 2..N = caption images
        for idx, cap in enumerate(caption_overlays):
            cap_img = cap["image_path"]
            start_t = cap["start"]
            end_t = cap["end"]
            in_idx = 2 + idx
            extra_inputs.extend(["-i", cap_img])

            next_v = f"v_cap_{idx}"
            filter_chains.append(
                f"[{last_v}][{in_idx}:v]overlay=0:0:enable='between(t,{start_t},{end_t})'[{next_v}]"
            )
            last_v = next_v

    full_filter = ";".join(filter_chains)

    cmd = [
        ffmpeg, "-y",
        "-loop", "1", "-i", slide_path,
        "-i", audio_path,
    ] + extra_inputs + [
        "-filter_complex", full_filter,
        "-map", f"[{last_v}]",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "veryfast",
        "-crf", "19",
        "-t", str(duration_sec),
        "-an",
        output_path,
    ]

    res = subprocess.run(cmd, capture_output=True, text=True, errors="ignore")
    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg দৃশ্য রেন্ডারিং ব্যর্থ ({res.returncode}): {res.stderr[-350:]}")
    return output_path


def concatenate_clips(clip_paths, output_path, final_audio_path=None):
    """
    সমস্ত দৃশ্যের ক্লিপগুলোকে যুক্ত করে ফাইনাল রিল ভিডিও তৈরি করে।
    যদি final_audio_path (BGM মিক্সড অডিও) দেওয়া হয়, তবে সেটি যুক্ত করবে।
    """
    ffmpeg = get_ffmpeg()
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    temp_list = output_path + ".concat_list.txt"
    with open(temp_list, "w", encoding="utf-8") as f:
        for p in clip_paths:
            norm_p = p.replace("\\", "/")
            f.write(f"file '{norm_p}'\n")

    if final_audio_path and os.path.exists(final_audio_path):
        # ভিডিও কনক্যাট + ব্যাকগ্রাউন্ড মিউজিক মিক্সড ফাইনাল অডিও প্রতিস্থাপন
        cmd = [
            ffmpeg, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", temp_list,
            "-i", final_audio_path,
            "-map", "0:v",
            "-map", "1:a",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            output_path,
        ]
    else:
        cmd = [
            ffmpeg, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", temp_list,
            "-c", "copy",
            output_path,
        ]

    res = subprocess.run(cmd, capture_output=True, text=True, errors="ignore")
    try:
        os.remove(temp_list)
    except Exception:
        pass

    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg কনক্যাট ব্যর্থ: {res.stderr[-300:]}")
    return output_path
