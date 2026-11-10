import os
import subprocess
import wave
import imageio_ffmpeg
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
BGM_DIR = os.path.join(ASSETS_DIR, "bgm")
SFX_DIR = os.path.join(ASSETS_DIR, "sfx")


def get_ffmpeg():
    return imageio_ffmpeg.get_ffmpeg_exe()


def ensure_ambient_bgm(output_path=None, duration_sec=65):
    """
    যদি ব্যাকগ্রাউন্ড মিউজিক না থাকে, তবে অটোমেটিক ব্রডকাস্ট নিউজ অ্যাম্বিয়েন্ট ট্র্যাক তৈরি করে।
    """
    if not output_path:
        os.makedirs(BGM_DIR, exist_ok=True)
        output_path = os.path.join(BGM_DIR, "news_pulse_ambient.wav")

    # কাস্টম কোনো mp3 থাকলে সেটাই রিটার্ন করবে
    if os.path.exists(BGM_DIR):
        for f in os.listdir(BGM_DIR):
            if f.lower().endswith((".mp3", ".wav")) and f != "news_pulse_ambient.wav":
                return os.path.join(BGM_DIR, f)

    if os.path.exists(output_path) and os.path.getsize(output_path) > 100000:
        return output_path

    sr = 44100
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
    beat_interval = 60.0 / 112.0
    pulse = np.zeros_like(t)

    for b in range(int(duration_sec / beat_interval)):
        beat_t = b * beat_interval
        idx_start = int(beat_t * sr)
        pulse_len = int(0.14 * sr)
        if idx_start + pulse_len < len(t):
            local_t = np.linspace(0, 0.14, pulse_len, endpoint=False)
            decay = np.exp(-25 * local_t)
            freq = 75 - 25 * (local_t / 0.14)
            pulse[idx_start:idx_start+pulse_len] += np.sin(2 * np.pi * freq * local_t) * decay * 0.45

    pad = (
        np.sin(2 * np.pi * 146.8 * t) * 0.15 +
        np.sin(2 * np.pi * 174.6 * t) * 0.12 +
        np.sin(2 * np.pi * 220.0 * t) * 0.10 +
        np.sin(2 * np.pi * 73.4 * t) * 0.20
    )
    lfo = 0.6 + 0.4 * np.sin(2 * np.pi * 0.2 * t)
    pad = pad * lfo * 0.35

    combined = pulse + pad
    combined = combined / (np.max(np.abs(combined)) + 1e-6) * 0.7
    fade_len = int(1.5 * sr)
    combined[:fade_len] *= np.linspace(0, 1, fade_len)
    combined[-fade_len:] *= np.linspace(1, 0, fade_len)

    audio_int16 = (combined * 32767).astype(np.int16)
    with wave.open(output_path, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(audio_int16.tobytes())

    return output_path


def ensure_whoosh_sfx(output_path=None):
    if not output_path:
        os.makedirs(SFX_DIR, exist_ok=True)
        output_path = os.path.join(SFX_DIR, "whoosh.wav")

    if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
        return output_path

    sr = 44100
    dur = 0.35
    t = np.linspace(0, dur, int(sr * dur), endpoint=False)
    noise = np.random.uniform(-1, 1, len(t))
    env = np.sin(np.pi * (t / dur)) ** 2
    sweep = np.sin(2 * np.pi * (200 + 400 * np.sin(np.pi * t / dur)) * t)
    audio = (noise * 0.4 + sweep * 0.6) * env * 0.35
    audio_int16 = (audio * 32767).astype(np.int16)
    with wave.open(output_path, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(audio_int16.tobytes())

    return output_path


def mix_voiceover_and_bgm(vocal_path, output_path, bgm_volume=0.18):
    """
    ভয়েস-ওভারের সাথে স্পন্দিত ও প্রামাণ্য নিউজ ব্যাকগ্রাউন্ড মিউজিক মিক্স করে।
    """
    ffmpeg = get_ffmpeg()
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    bgm_path = ensure_ambient_bgm()

    filter_complex = (
        f"[0:a]volume=1.0[vocal];"
        f"[1:a]volume={bgm_volume}[bgm];"
        f"[vocal][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]"
    )

    cmd = [
        ffmpeg, "-y",
        "-i", vocal_path,
        "-stream_loop", "-1", "-i", bgm_path,
        "-filter_complex", filter_complex,
        "-map", "[aout]",
        "-c:a", "libmp3lame",
        "-b:a", "192k",
        output_path,
    ]

    res = subprocess.run(cmd, capture_output=True, text=True, errors="ignore")
    if res.returncode != 0:
        print(f"[audio_mixer] সতর্কবার্তা: BGM মিক্সিং সমস্যা ({res.stderr[:200]}), মূল ভোকাল ব্যবহার হচ্ছে")
        return vocal_path
    return output_path

