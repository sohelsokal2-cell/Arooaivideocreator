"""
Gemini AI Voice Engine — Multi-API Key (10 API Failover Pool) সহ ১০০% প্রাকৃতিক বাংলা ভয়েস-ওভার।
"""

import asyncio
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import time

import imageio_ffmpeg
import requests

import audio_merger
import text_normalizer

# ---------------------------------------------------------------
# Supported Voices
# ---------------------------------------------------------------
SUPPORTED_VOICES = {
    "kore": {
        "id": "Kore",
        "name": "Kore",
        "gender": "Female",
        "description": "মিষ্টি, সাবলীল ও বাস্তব নারী কণ্ঠ (ডেমো অডিওর মতো)",
    },
    "aoede": {
        "id": "Aoede",
        "name": "Aoede",
        "gender": "Female",
        "description": "স্পষ্ট ও পেশাদার টিভি সংবাদ উপস্থাপিকার নারী কণ্ঠ",
    },
    "charon": {
        "id": "Charon",
        "name": "Charon",
        "gender": "Male",
        "description": "গম্ভীর ও ব্যক্তিত্বসম্পন্ন পুরুষ সংবাদ উপস্থাপকের কণ্ঠ",
    },
}

DEFAULT_VOICE = "Kore"
_API_MODEL = "gemini-2.5-flash-preview-tts"
_ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{_API_MODEL}:generateContent"

# প্রতি রানে কোন ইঞ্জিন কতগুলো সেগমেন্ট বানিয়েছে — মিশ্র-ইঞ্জিন অডিও চাপা না পড়ে রিপোর্টে আসে।
_ENGINE_STATS = {"gemini": 0, "edge": 0}


def reset_engine_stats():
    _ENGINE_STATS["gemini"] = 0
    _ENGINE_STATS["edge"] = 0


def engine_stats():
    return dict(_ENGINE_STATS)


def _edge_fallback_enabled() -> bool:
    return os.environ.get("FALLBACK_TO_EDGE_TTS", "true").strip().lower() not in ("0", "false", "no", "off")


# ---------------------------------------------------------------
# Multi-API Key Failover Manager (Supports 6+ API Keys)
# ---------------------------------------------------------------
class ApiKeyManager:
    def __init__(self):
        self.keys = []
        self._current_idx = 0
        self._load_keys()

    def _load_keys(self):
        """
        Load all Gemini API keys from .env files or environment variables.
        Supports:
          - GEMINI_API_KEY_1, GEMINI_API_KEY_2, ... GEMINI_API_KEY_6, ... GEMINI_API_KEY_N
          - GEMINI_API_KEY (single or comma-separated)
        """
        base = os.path.dirname(os.path.abspath(__file__))
        env_files = [
            os.path.join(base, ".env"),
            os.path.join(os.path.dirname(base), "Writer Agent", ".env"),
        ]

        # 1. Parse env files to ensure all variables exist in os.environ
        for ef in env_files:
            if os.path.exists(ef):
                try:
                    with open(ef, "r", encoding="utf-8-sig") as f:
                        for line in f:
                            line = line.strip()
                            if not line or line.startswith("#") or "=" not in line:
                                continue
                            k, _, v = line.partition("=")
                            k = k.strip()
                            v = v.strip().strip('"').strip("'")
                            # প্রসেসে আগে থেকেই থাকা মান overwrite করা হয় না।
                            if k and v and k not in os.environ:
                                os.environ[k] = v
                except Exception as exc:
                    print(f"[env] {ef} পড়া যায়নি: {type(exc).__name__}: {exc}", file=sys.stderr)

        found = []

        # 2. Collect numeric keys in order: GEMINI_API_KEY_1, GEMINI_API_KEY_2, ...
        numbered_keys = []
        pattern = re.compile(r"^GEMINI_API_KEY_(\d+)$", re.IGNORECASE)

        for k, v in os.environ.items():
            m = pattern.match(k.strip())
            if m:
                idx = int(m.group(1))
                val = v.strip().strip('"').strip("'")
                if val:
                    numbered_keys.append((idx, val))

        # Sort strictly by index (1, 2, 3, 4, 5, 6, ...)
        numbered_keys.sort(key=lambda x: x[0])
        for _, key_val in numbered_keys:
            if key_val not in found:
                found.append(key_val)

        # 3. Check generic GEMINI_API_KEY or comma-separated list
        generic = os.getenv("GEMINI_API_KEY", "").strip().strip('"').strip("'")
        if generic:
            for piece in generic.split(","):
                piece = piece.strip()
                if piece and piece not in found:
                    found.append(piece)

        self.keys = found
        self._current_idx = 0

    def get_current_key(self) -> str:
        if not self.keys:
            self._load_keys()
        if not self.keys:
            raise RuntimeError(
                "কোনো GEMINI_API_KEY পাওয়া যায়নি!\n"
                "অনুগ্রহ করে Voice Over Agent ফোল্ডারের .env ফাইলে\n"
                "GEMINI_API_KEY_1=...\n"
                "GEMINI_API_KEY_2=...\n"
                "...\n"
                "GEMINI_API_KEY_10=...\n"
                "হিসেবে আপনার ফ্রি Gemini API কীগুলো বসান।"
            )
        return self.keys[self._current_idx]

    def current_label(self) -> str:
        idx = self._current_idx + 1
        total = max(len(self.keys), 1)
        return f"API Key #{idx}/{total}"

    def switch_to_next_key(self, reason: str = "429 Quota Exceeded") -> str:
        """Switch to next key in the pool and return the new key."""
        old_idx = self._current_idx
        next_idx = (self._current_idx + 1) % max(len(self.keys), 1)
        self._current_idx = next_idx
        print(
            f"\n[API Failover] {reason}! "
            f"স্বয়ংক্রিয়ভাবে API Key #{old_idx + 1} থেকে #{next_idx + 1}-এ সুইচ করা হচ্ছে..."
        )
        return self.keys[self._current_idx]

    def reset_to_start(self):
        """Reset index back to the first key for a fresh retry round."""
        self._current_idx = 0


# Global Key Pool
key_manager = ApiKeyManager()


# ---------------------------------------------------------------
# Emergency Backup TTS (Edge-TTS — 100% Free & Unlimited Quota)
# ---------------------------------------------------------------
# Edge-এ বাংলা কণ্ঠ মাত্র দুটি, তাই তৃতীয় কণ্ঠের জন্য rate/pitch আলাদা করে
# তিনটি ভয়েসকেই শোনাযোগ্যভাবে পৃথক রাখা হয় (আগে Kore ও Aoede হুবহু একই ছিল)।
_EDGE_VOICE_PROFILES = {
    "kore":   ("bn-BD-NabanitaNeural", "-5%", "+0Hz"),
    "aoede":  ("bn-BD-NabanitaNeural", "+8%", "+25Hz"),
    "charon": ("bn-BD-PradeepNeural", "+0%", "+0Hz"),
}


def _synthesize_edge_tts(text: str, output_path: str, voice_name: str = DEFAULT_VOICE) -> str:
    """
    Emergency fallback synthesizer using Edge-TTS.
    Called only if all Gemini API keys in the pool hit quota, ensuring 100% completion.
    """
    try:
        import edge_tts
    except ImportError:
        raise RuntimeError("edge-tts ইনস্টল করা নেই। pip install edge-tts চালান।")

    spoken_text = text_normalizer.normalize_text(text)
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    temp_mp3 = output_path + ".edge_temp.mp3"

    v_lower = (voice_name or "").strip().lower()
    edge_voice, rate, pitch = _EDGE_VOICE_PROFILES.get(v_lower, _EDGE_VOICE_PROFILES["kore"])

    async def _run_edge():
        communicate = edge_tts.Communicate(spoken_text, edge_voice, rate=rate, pitch=pitch)
        await communicate.save(temp_mp3)

    asyncio.run(_run_edge())

    if os.path.exists(temp_mp3) and os.path.getsize(temp_mp3) > 0:
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except Exception:
                pass
        os.replace(temp_mp3, output_path)
        return output_path

    raise RuntimeError(f"Edge-TTS রূপান্তর ব্যর্থ: {output_path}")


# ---------------------------------------------------------------
# Synthesis Core
# ---------------------------------------------------------------
def resolve_voice_name(voice: str) -> str:
    v = (voice or "").strip().lower()
    if v in SUPPORTED_VOICES:
        return SUPPORTED_VOICES[v]["id"]
    for k, info in SUPPORTED_VOICES.items():
        if v == info["name"].lower():
            return info["id"]
    return DEFAULT_VOICE


# মডিউল-লেভেল অবস্থা: সব key-র কোটা শেষ হওয়ার সাম্প্রতিক সময় (epoch সেকেন্ড)।
# আগে এটি ১০ মিনিটের "হার্ড স্কিপ" ছিল — একটিমাত্র সেগমেন্ট ব্যর্থ হলেই বাকি
# সব সেগমেন্ট Gemini ছাড়াই Edge-এ চলে যেত (মিশ্র-মানের অডিও, কোনো সতর্কতা ছাড়াই)।
# এখন জানালাটি শুধু cooldown ladder-কে সংক্ষিপ্ত করে: প্রতিটি সেগমেন্ট আবার একবার
# সব key চেষ্টা করে, সফল হলে জানালা বাতিল হয়; কেবল আসলেই কোটা শেষ থাকলে Edge-এ যায়।
_ALL_KEYS_EXHAUSTED_UNTIL = 0.0


def _edge_fallback(text: str, output_path: str, voice_name: str) -> str:
    """সব Gemini key ব্যর্থ হলে Edge-TTS ব্যবহার; Edge-ও ব্যর্থ হলে RuntimeError।"""
    if not _edge_fallback_enabled():
        raise RuntimeError(
            "সব Gemini API Key অব্যবহারযোগ্য; FALLBACK_TO_EDGE_TTS=false থাকায় "
            "Edge-TTS ফলব্যাক ব্যবহার করা হয়নি"
        )
    _ENGINE_STATS["edge"] += 1
    print(
        f"\n⚠️ [ব্যাকআপ ইঞ্জিন] এই সেগমেন্টটি Edge-TTS দিয়ে তৈরি হচ্ছে ({voice_name})।"
        "\n   সব Gemini API Key-এর কোটা/রেট-লিমিট সক্রিয় — অডিওর মান ভিন্ন হতে পারে।"
    )
    try:
        return _synthesize_edge_tts(text, output_path, voice_name)
    except Exception as fallback_err:
        print(f"Edge-TTS ব্যাকআপ ব্যর্থ: {fallback_err}")
        raise RuntimeError(f"Gemini ও Edge-TTS দুটোই ব্যর্থ: {output_path}") from fallback_err


def _synthesize_gemini(text: str, output_path: str, voice_name: str = DEFAULT_VOICE, max_cooldown_rounds: int = 5):
    """
    Generate audio with Gemini Native Multimodal TTS.
    Automatically fails over across the 6+ Gemini API keys upon 429 quota exhaustion.
    If all keys temporarily hit RPM limit, performs smart cooldown wait.
    """
    # এই ফাংশনের ভিতরে মডিউল-ভেরিয়েবলটি লেখা হয় (সফল-রেসপন্সের রিসেট ও exhausted জানালা)।
    # global না ঘোষণা করলে নামটি লোকাল হয়ে যায় এবং লাইন ২৬১-তে প্রথম রিডেই
    # UnboundLocalError হয় — প্রতিটি সেগমেন্ট ব্যর্থ হয়ে agent exit(1) করে।
    global _ALL_KEYS_EXHAUSTED_UNTIL
    spoken_text = text_normalizer.normalize_text(text)
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    payload = {
        "contents": [{"parts": [{"text": spoken_text}]}],
        "generationConfig": {
            "response_modalities": ["AUDIO"],
            "speech_config": {
                "voice_config": {
                    "prebuilt_voice_config": {
                        "voice_name": voice_name
                    }
                }
            }
        }
    }

    cooldown_round = 0
    total_keys = max(len(key_manager.keys), 1)
    # পুরো কলের জন্য নেটওয়ার্ক-পুনরাচেষ্টার সীমা — এটি ছাড়া নেটওয়ার্ক বন্ধ থাকলে
    # লুপটি অনন্তকাল ঘুরবে (RequestException → sleep(2) → continue)।
    network_attempts = 0

    # হার্ড স্কিপ নেই — জানালা থাকলেও প্রতিটি সেগমেন্ট একবার সব key চেষ্টা করবে।
    exhausted_recently = time.time() < _ALL_KEYS_EXHAUSTED_UNTIL
    effective_rounds = 1 if exhausted_recently else max_cooldown_rounds

    while cooldown_round <= effective_rounds:
        keys_attempted_in_round = 0

        while keys_attempted_in_round < total_keys:
            current_key = key_manager.get_current_key()
            url = f"{_ENDPOINT}?key={current_key}"

            try:
                resp = requests.post(url, json=payload, timeout=35)

                # Success
                if resp.status_code == 200:
                    try:
                        data = resp.json()
                    except Exception as exc:
                        # 200 কিন্তু JSON নয় (captive portal / HTML error page) — পরের key
                        keys_attempted_in_round += 1
                        print(f"[রেসপন্স সমস্যা] HTTP 200 কিন্তু অ-JSON বডি ({type(exc).__name__})")
                        if keys_attempted_in_round < total_keys:
                            key_manager.switch_to_next_key(reason="অ-JSON রেসপন্স")
                            time.sleep(1)
                            continue
                        break

                    candidates = data.get("candidates") or []
                    part = {}
                    if candidates:
                        parts = (candidates[0].get("content") or {}).get("parts") or []
                        if parts:
                            part = parts[0]
                    inline = part.get("inlineData")

                    if not inline:
                        # 200 কিন্তু অডিও নেই (যেমন promptFeedback.blockReason) — পরের key চেষ্টা
                        block = ((data.get("promptFeedback") or {}).get("blockReason") or "unknown")
                        keys_attempted_in_round += 1
                        print(f"[রেসপন্স সমস্যা] HTTP 200 কিন্তু অডিও রেসপন্স নেই (blockReason={block})")
                        if keys_attempted_in_round < total_keys:
                            key_manager.switch_to_next_key(reason="অডিও রেসপন্স অনুপস্থিত")
                            time.sleep(1)
                            continue
                        break

                    raw_pcm = base64.b64decode(inline["data"])

                    # Convert raw 24kHz PCM to MP3 via ffmpeg
                    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
                    proc = subprocess.Popen(
                        [
                            ffmpeg, "-y",
                            "-f", "s16le",
                            "-ar", "24000",
                            "-ac", "1",
                            "-i", "pipe:0",
                            "-c:a", "libmp3lame",
                            "-b:a", "192k",
                            output_path,
                        ],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    proc.communicate(input=raw_pcm)

                    if proc.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                        # সফল উৎপাদন — "সব কি শেষ" অনুমান বাতিল
                        _ALL_KEYS_EXHAUSTED_UNTIL = 0.0
                        _ENGINE_STATS["gemini"] += 1
                        return output_path

                    raise RuntimeError(f"ffmpeg MP3 রূপান্তর ব্যর্থ: {output_path}")

                # Bad request (400) = payload problem, not a key problem — raise immediately
                if resp.status_code == 400:
                    err_msg = ""
                    try:
                        err_msg = resp.json().get("error", {}).get("message", "")
                    except Exception:
                        pass
                    raise RuntimeError(f"Gemini API 400 Bad Request: {err_msg or resp.text[:150]}")

                # স্থায়ী অনুমতি/কী ত্রুটি (401/403): কুলডাউন ল্যাডারে ৫ মিনিট নষ্ট না করে
                # শুধু পরের কী চেষ্টা করা হয়; সব কী একই ত্রুটি দিলে স্পষ্ট ব্যর্থতা।
                if resp.status_code in (401, 403):
                    keys_attempted_in_round += 1
                    print(f"[API ত্রুটি] HTTP {resp.status_code}: এই কীটি অনুমোদিত নয় — পরের কী চেষ্টা করা হচ্ছে")
                    if keys_attempted_in_round < total_keys:
                        key_manager.switch_to_next_key(reason=f"HTTP {resp.status_code}")
                        time.sleep(0.5)
                        continue
                    raise RuntimeError(f"সব Gemini API কী-তে HTTP {resp.status_code} — কী/অনুমতি যাচাই করুন")

                # Quota (429) বা সার্ভার ওভারলোড (500/503) → Failover to next key
                if resp.status_code in (429, 500, 503):
                    keys_attempted_in_round += 1
                    err_msg = ""
                    try:
                        err_msg = resp.json().get("error", {}).get("message", "")
                    except Exception:
                        pass
                    err_msg = err_msg or f"HTTP {resp.status_code}"

                    if keys_attempted_in_round < total_keys:
                        key_manager.switch_to_next_key(reason=f"ত্রুটি ({resp.status_code}: {err_msg[:45]}...)")
                        time.sleep(1)
                        continue
                    else:
                        # All keys in pool were tried in this round
                        break

                # Other HTTP errors
                raise RuntimeError(f"Gemini API {resp.status_code}: {resp.text[:150]}")

            except requests.exceptions.RequestException as exc:
                # নেটওয়ার্ক ঝুঁকির পুনরাচেষ্টা — কিন্তু অসীম নয়: নেট বন্ধ/টাইমআউট চলতে থাকলে
                # কলটি বাতিল হয়ে উপরের স্তরে স্পষ্ট ত্রুটি যায় (আগে Infinite লুপ ছিল)।
                network_attempts += 1
                if network_attempts > 10:
                    raise RuntimeError(
                        f"নেটওয়ার্ক/সার্ভার বারবার ব্যর্থ ({type(exc).__name__}: {str(exc)[:120]}) — অনুরোধ বাতিল"
                    )
                time.sleep(2)
                continue

        # All keys reached in this round! Perform smart cooldown wait for sliding-window reset
        cooldown_round += 1
        if cooldown_round <= max_cooldown_rounds:
            wait_seconds = 5 if exhausted_recently else 20 * cooldown_round
            print(
                f"\n[রেট-লিমিট বিরতি] পুলের সকল {total_keys}টি কী-তে এই মুহূর্তে লিমিট সক্রিয়।"
                f"\n                 {wait_seconds} সেকেন্ড অপেক্ষা করা হচ্ছে... (রাউন্ড {cooldown_round}/{max_cooldown_rounds})"
            )
            time.sleep(wait_seconds)
            key_manager.switch_to_next_key(reason="কুলডাউন শেষে রোটেশন")
            continue
        else:
            # সব রাউন্ড শেষ — সম্ভবত দৈনিক/দীর্ঘ কোটা শেষ।
            # ২ মিনিটের সংক্ষিপ্ত জানালা: পরের সেগমেন্ট Gemini আবার চেষ্টা করবে,
            # কিন্তু বারবার ২০+ সেকেন্ড অপেক্ষা করে রান আটকাবে না।
            _ALL_KEYS_EXHAUSTED_UNTIL = time.time() + 120
            return _edge_fallback(text, output_path, voice_name)
    raise RuntimeError(f"অডিও তৈরি করতে ব্যর্থ হয়েছে: {text[:35]}...")


async def generate_speech_async(text: str, output_path: str, voice: str = DEFAULT_VOICE):
    """Generate audio snippet asynchronously."""
    v_name = resolve_voice_name(voice)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _synthesize_gemini, text, output_path, v_name)
    return output_path


def generate_speech(text: str, output_path: str, voice: str = DEFAULT_VOICE):
    """Synchronous speech generation."""
    return asyncio.run(generate_speech_async(text, output_path, voice))


async def process_sections_async(
    sections: list,
    output_dir: str,
    voice: str = DEFAULT_VOICE,
    pause_sec: float = 0.8,
    also_ogg: bool = False,
    force: bool = False,
    on_progress=None,
):
    """
    Process all script sections for a given voice:
    1. Skip segments that already exist (Smart Resume / Cache) — but only if the
       recorded text-hash matches AND the mp3 actually decodes (ক্যাশে ভাঙা ফাইল রিজেনারেট হয়)।
    2. Generate individual mp3 for each new section into output_dir/segments_<voice>/
       — এক সেগমেন্ট ব্যর্থ হলে পুরো রান বাতিল নয়, ব্যর্থ শিহর হিসেবে রিপোর্ট হয়।
    3. Merge all into output_dir/full_voiceover_<voice>.mp3
    """
    v_name = resolve_voice_name(voice)
    v_tag = v_name.lower()

    segments_dir = os.path.join(output_dir, f"segments_{v_tag}")
    os.makedirs(segments_dir, exist_ok=True)
    reset_engine_stats()

    segment_files = []
    failed = []
    total = len(sections)
    hash_cache = _load_hash_cache(segments_dir)

    for idx, sec in enumerate(sections, 1):
        prefix = sec.get("filename_prefix", f"{idx:02d}")
        seg_filename = f"{prefix}.mp3"
        seg_path = os.path.join(segments_dir, seg_filename)
        # যা আসলে উচ্চারিত হবে সেটার হ্যাশ — একই তারিখে স্ক্রিপ্ট বদলালে ক্যাশ মিথ্যা হয় না
        text_hash = hashlib.md5(text_normalizer.normalize_text(sec["text"]).encode("utf-8")).hexdigest()[:12]

        cached = (
            not force
            and hash_cache.get(prefix) == text_hash
            and os.path.exists(seg_path)
            and os.path.getsize(seg_path) > 2000
            and _segment_looks_playable(seg_path)
        )
        if cached:
            if on_progress:
                on_progress(idx, total, sec, v_name, True)
            segment_files.append(seg_path)
            continue
        if not force and hash_cache.get(prefix) == text_hash and os.path.exists(seg_path):
            # হ্যাশ মিল কিন্তু ফাইল ভাঙা/অসম্পূর্ণ — ক্যাশ অগ্রাহ্য করে নতুন করে তৈরি
            print(f"  [{idx:02d}/{total:02d}] ক্যাশে ভাঙা ফাইল পাওয়া গেছে — নতুন করে তৈরি হবে: {seg_filename}")

        if on_progress:
            on_progress(idx, total, sec, v_name, False)

        try:
            await generate_speech_async(
                text=sec["text"],
                output_path=seg_path,
                voice=v_name,
            )
        except Exception as exc:
            print(f"  [{idx:02d}/{total:02d}] ❌ ব্যর্থ {prefix}: {type(exc).__name__}: {exc}")
            failed.append({"prefix": prefix, "title": sec.get("title", ""), "error": str(exc)[:200]})
            continue

        segment_files.append(seg_path)
        hash_cache[prefix] = text_hash
        _save_hash_cache(segments_dir, hash_cache)

        # Gentle throttle (1.0s) to keep request rate smooth
        await asyncio.sleep(1.0)

    result = {
        "voice": v_name,
        "segment_files": segment_files,
        "full_audio": "",
        "segments_dir": segments_dir,
        "failed": failed,
        "complete": not failed and total > 0,
        "engines": engine_stats(),
    }

    if failed:
        print(f"\n⚠️ {len(failed)}/{total} সেগমেন্ট তৈরি হয়নি: {', '.join(f['prefix'] for f in failed)}")
        print("   রান পুনর্চালনা (Smart Resume) করলে শুধু ব্যর্থগুলো নতুন করে তৈরি হবে।")
        # অসম্পূর্ণ অনুলিপি দিয়ে পুরানো সম্পূর্ণ অডিও এলোমেলো করা এড়ানো হলো:
        # ব্যর্থ সেগমেন্ট থাকলে merge হয় না।
        return result

    # Merge into a single full audio
    full_output_name = f"full_voiceover_{v_tag}.mp3"
    full_output_path = os.path.join(output_dir, full_output_name)

    audio_merger.merge_audio_files(
        file_paths=segment_files,
        output_path=full_output_path,
        pause_sec=pause_sec,
        also_ogg=also_ogg,
    )

    result["full_audio"] = full_output_path
    return result


def _hash_cache_path(segments_dir: str) -> str:
    return os.path.join(segments_dir, ".text_hashes.json")


def _load_hash_cache(segments_dir: str) -> dict:
    """প্রতি সেগমেন্টের টেক্সট-হ্যাশ ম্যাপ — একই তারিখে স্ক্রিপ্ট বদলালে পুরনো অডিও রোধ করে।"""
    path = _hash_cache_path(segments_dir)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                return data
        except Exception as exc:
            print(f"[cache] হ্যাশ ক্যাশ পড়া যায়নি ({type(exc).__name__}: {exc}) — সেগমেন্ট নতুন করে যাচাই হবে", file=sys.stderr)
    return {}


def _save_hash_cache(segments_dir: str, cache: dict) -> None:
    try:
        with open(_hash_cache_path(segments_dir), "w", encoding="utf-8") as fh:
            json.dump(cache, fh, ensure_ascii=False, indent=1)
    except Exception as exc:
        print(f"[cache] হ্যাশ ক্যাশ লেখা যায়নি ({type(exc).__name__}: {exc})", file=sys.stderr)


def _segment_looks_playable(seg_path: str) -> bool:
    """ffmpeg দিয়ে ফাইলটি আসলে পড়া যায় কিনা — অর্ধেক অসম্পূর্ণ মিডি-এনকোড ফাইল
    শুধু সাইজ>2KB দেখে 'ক্যাশ ✓' হিসেবে গ্রহণ করা বগ।"""
    try:
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        proc = subprocess.run(
            [ffmpeg, "-hide_banner", "-i", seg_path, "-f", "null", "-"],
            capture_output=True, text=True, timeout=30, errors="replace",
        )
        if proc.returncode != 0:
            return False
        dur = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", proc.stderr or "")
        if dur:
            hh, mm, ss = dur.groups()
            seconds = int(hh) * 3600 + int(mm) * 60 + float(ss)
            return seconds > 0.5
        # Duration বুঝলেও decode সফল হয়েছে (returncode 0) — গ্রহণ করা যায়
        return True
    except Exception as exc:
        # যাচাই করা না গেলে ভাঙা ফাইলকে সঠিক ধরে নেওয়ার চেয়ে পুনরায় তৈরি করা নিরাপদ।
        print(f"[cache] প্লেব্যাক যাচাই ব্যর্থ ({type(exc).__name__}: {exc}) — সেগমেন্ট নতুন করে তৈরি হবে", file=sys.stderr)
        return False


def process_sections(
    sections: list,
    output_dir: str,
    voice: str = DEFAULT_VOICE,
    pause_sec: float = 0.8,
    also_ogg: bool = False,
    force: bool = False,
    on_progress=None,
):
    """Synchronous wrapper for process_sections_async."""
    return asyncio.run(
        process_sections_async(
            sections=sections,
            output_dir=output_dir,
            voice=voice,
            pause_sec=pause_sec,
            also_ogg=also_ogg,
            force=force,
            on_progress=on_progress,
        )
    )
