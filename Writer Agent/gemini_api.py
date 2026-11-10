import json
import os
import re
import sys
import time

import requests

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
FALLBACK_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-3.5-flash",
    "gemini-flash-latest",
    "gemini-3.8-flash",
]


def load_env(path=None):
    path = path or os.path.join(BASE_DIR, ".env")
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8-sig") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def api_key():
    load_env()
    return os.environ.get("GEMINI_API_KEY", "").strip()


LAST_MODEL = ""
# model -> ব্ল্যাকলিস্ট শেষ হওয়ার সময় (epoch সেকেন্ড)
# অস্থায়ী গ্লিচ (503 বা timeout)-এর জন্য মাত্র ১৫-২০ সেকেন্ড সাময়িক বিরতি,
# কিন্তু 404 (মডেল নেই)-এর জন্য লম্বা বিরতি রাখা হয়।
FAILED_MODELS = {}


def mark_failed_model(model, minutes=0.25):
    FAILED_MODELS[model] = time.time() + minutes * 60


def model_order():
    load_env()
    now = time.time()
    for model in list(FAILED_MODELS):
        if FAILED_MODELS[model] <= now:
            del FAILED_MODELS[model]  # সময়সীমা শেষ — আবার চেষ্টা করা হলো
    preferred = os.environ.get("GEMINI_MODEL", "").strip()
    order = []
    for model in [preferred] + FALLBACK_MODELS:
        if model and model not in order:
            order.append(model)
    # সব মডেল ব্ল্যাকলিস্টেড হলে আবার সেগুলোই ঘুরিয়ে রিট্রাই স্টর্ম না বানিয়ে
    # স্পষ্ট ব্যর্থতা দেওয়া হয় (ask_gemini শেষে last_error ছুড়ে দেবে)।
    return [m for m in order if m not in FAILED_MODELS]


def _parse_json(text):
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no json object in response")
    return json.loads(text[start:end + 1])


def _extract_text(data):
    feedback = data.get("promptFeedback") or {}
    if feedback.get("blockReason"):
        raise RuntimeError(f"blocked: {feedback['blockReason']}")
    candidates = data.get("candidates") or []
    if not candidates:
        raise RuntimeError("candidates ফাঁকা")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts).strip()
    if not text:
        finish = (candidates[0].get("finishReason") or "").upper()
        raise RuntimeError(f"response ফাঁকা (finishReason={finish})")
    return text


def ask_gemini(user_content, system_prompt="", temperature=0.75, max_output_tokens=600):
    global LAST_MODEL
    key = api_key()
    if not key:
        raise RuntimeError("GEMINI_API_KEY পাওয়া যায়নি (.env ফাইলে GEMINI_API_KEY=... বসান)")
    payload = {
        "contents": [{"role": "user", "parts": [{"text": user_content}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_output_tokens,
            "responseMimeType": "application/json",
        },
    }
    if system_prompt:
        payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}
    last_error = None
    for model in model_order():
        url = f"{API_BASE}/{model}:generateContent"
        resp = None
        for attempt in range(2):
            try:
                resp = requests.post(url, params={"key": key}, json=payload, timeout=(10, 35))
            except Exception as exc:
                last_error = RuntimeError(f"{model}: {type(exc).__name__}: {exc}")
                mark_failed_model(model, minutes=0.25)
                resp = None
                break
            if resp.status_code == 429:
                time.sleep(2 * (attempt + 1))
                continue
            if resp.status_code == 503:
                time.sleep(1.5 * (attempt + 1))
                continue
            break
        if resp is None:
            continue
        if resp.status_code == 429:
            mark_failed_model(model, minutes=0.5)
            last_error = RuntimeError(f"{model}: rate limited (429)")
            continue
        if resp.status_code == 503:
            mark_failed_model(model, minutes=0.25)
            last_error = RuntimeError(f"{model}: temporarily unavailable (503)")
            continue
        if resp.status_code in (401, 403):
            raise RuntimeError(f"Gemini API {resp.status_code}: {resp.text[:300]}")
        if resp.status_code == 404:
            # 404 = এই API key-তে মডেল নেই — লম্বা সময়ের জন্য বাদ
            mark_failed_model(model, minutes=240)
            last_error = RuntimeError(f"{model}: not available (404)")
            continue
        if resp.status_code != 200:
            last_error = RuntimeError(f"{model} -> {resp.status_code}: {resp.text[:300]}")
            continue
        try:
            data = resp.json()
        except Exception as exc:
            last_error = RuntimeError(f"{model}: {type(exc).__name__}: {exc}")
            continue
        # MAX_TOKENS-এ কাটা পড়লে token budget দ্বিগুণ করে একবার আবার চাওয়া হয়;
        # thinking-মডেলে রিজনিং টোকেন budget খেয়ে আউটপুট ফাঁকা রাখে, তাই দ্বিতীয় চেষ্টায় thinking off।
        tokens_now = max_output_tokens
        parsed = None
        for round_i in range(2):
            try:
                parsed = _parse_json(_extract_text(data))
                break
            except Exception as exc:
                last_error = RuntimeError(f"{model}: {type(exc).__name__}: {str(exc)[:200]}")
                finish = ""
                try:
                    finish = ((data.get("candidates") or [{}])[0].get("finishReason") or "").upper()
                except Exception:
                    pass
                if finish != "MAX_TOKENS" or round_i == 1:
                    break
                tokens_now = tokens_now * 2 + 100
                retry = dict(payload)
                retry["generationConfig"] = {
                    "temperature": temperature,
                    "maxOutputTokens": tokens_now,
                    "responseMimeType": "application/json",
                    "thinkingConfig": {"thinkingBudget": 0},
                }
                try:
                    resp = requests.post(url, params={"key": key}, json=retry, timeout=30)
                    if resp.status_code != 200:
                        # thinkingConfig কিছু পুরোনো মডেল 400 করতে পারে — পরের মডেলে যাই
                        last_error = RuntimeError(f"{model} retry -> {resp.status_code}: {resp.text[:200]}")
                        break
                    data = resp.json()
                except Exception as exc2:
                    last_error = RuntimeError(f"{model}: {type(exc).__name__}: {exc2}")
                    break
        if parsed is not None:
            if LAST_MODEL != model:
                LAST_MODEL = model
                print(f"      (মডেল: {model})")
            return parsed
        continue
    raise last_error or RuntimeError("কোনো Gemini model পাওয়া যায়নি")
