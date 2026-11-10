import json
import os
import re
import sys
import time

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import requests
from history_manager import is_already_covered_today, _similarity, _tokens

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
API_URL = "https://api.groq.com/openai/v1/chat/completions"

FALLBACK_MODELS = [
    "openai/gpt-oss-120b",
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-20b",
]

LAST_MODEL = ""
RATE_LIMITED = set()


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
    return os.environ.get("GROQ_API_KEY", "").strip()


def model_order():
    load_env()
    preferred = os.environ.get("GROQ_MODEL", "").strip()
    order = []
    for model in [preferred] + FALLBACK_MODELS:
        if model and model not in order:
            order.append(model)
    return [m for m in order if m not in RATE_LIMITED]


def _parse_json(text):
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"no json object found in response: {text[:150]}")
    return json.loads(text[start:end + 1])


def call_groq(system_prompt, user_prompt, max_tokens=2500):
    global LAST_MODEL
    key = api_key()
    if not key:
        raise RuntimeError("GROQ_API_KEY পাওয়া যায়নি (.env ফাইলে GROQ_API_KEY=... বসান)")

    models = model_order()
    if not models:
        raise RuntimeError("সব Groq মডেল এই মুহূর্তে অনুপলব্ধ — .env-এ GROQ_MODEL যাচাই করুন")

    last_error = None
    for model in models:
        payload = {
            "model": model,
            "temperature": 0.2,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if model.startswith("openai/"):
            payload["reasoning_effort"] = "low"

        resp = None
        for attempt in range(2):
            try:
                resp = requests.post(
                    API_URL,
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json=payload,
                    timeout=60,
                )
            except Exception as exc:
                last_error = RuntimeError(f"{model}: {type(exc).__name__}: {exc}")
                resp = None
                break
            if resp.status_code == 429:
                time.sleep(2 * (attempt + 1))
                continue
            break

        if resp is None:
            continue
        if resp.status_code == 429:
            RATE_LIMITED.add(model)
            last_error = RuntimeError(f"{model}: rate limited")
            continue
        if resp.status_code in (401, 403):
            raise RuntimeError(f"Groq API {resp.status_code}: {resp.text[:300]}")
        if resp.status_code == 404 or "model_not_found" in resp.text[:400]:
            RATE_LIMITED.add(model)
            last_error = RuntimeError(f"{model}: not available")
            continue
        if resp.status_code != 200:
            last_error = RuntimeError(f"{model} -> {resp.status_code}: {resp.text[:300]}")
            continue

        try:
            content = resp.json()["choices"][0]["message"]["content"]
            parsed = _parse_json(content)
            if LAST_MODEL != model:
                LAST_MODEL = model
                print(f"      (সক্রিয় Groq মডেল: {model})")
            return parsed
        except Exception as exc:
            last_error = RuntimeError(f"{model}: {type(exc).__name__}: {exc}")
            continue

    raise last_error or RuntimeError("Groq মডেল থেকে কোনো রেসপন্স পাওয়া যায়নি")


def pick_breaking_story(candidates, today_str):
    """
    আজকের শীর্ষ ব্রেকিং খবর নির্বাচন করা যা আজ আগে প্রসেস করা হয়নি।
    """
    # আজকের পূর্বে প্রসেস হওয়া খবর ফিল্টার করা
    fresh_candidates = []
    for cand in candidates:
        title = cand.get("title", "")
        desc = cand.get("description", "")
        if not is_already_covered_today(title, desc, today_str):
            fresh_candidates.append(cand)

    if not fresh_candidates:
        print("[picker] সতর্কতা: আজকের নতুন কোনো খবর বাকি নেই অথবা সব ফিল্টার হয়েছে। সব ক্যান্ডিডেট ব্যবহার করা হচ্ছে।")
        fresh_candidates = candidates

    # AI প্রম্পট তৈরি (শীর্ষ ২০-২৫টি খবর দেওয়া)
    sample_pool = fresh_candidates[:30]
    items_text = []
    for idx, c in enumerate(sample_pool):
        items_text.append(f"[{idx}] উৎস: {c.get('site', 'অজ্ঞাত')} | শিরোনাম: {c.get('title')} | বিবরণ: {(c.get('description') or '')[:150]}")

    system_prompt = (
        "তুমি একজন পেশাদার বাংলাদেশী সংবাদ সম্পাদক। তোমার কাজ আজকের শীর্ষ ব্রেকিং ও সবচেয়ে গুরুত্বপূর্ণ বা আলোচিত "
        "একটি খবর বাছাই করা। সোশ্যাল মিডিয়ায় তথ্যবহুল ও আকর্ষণীয় রিল বা ভিডিও বানানোর জন্য যা সবচেয়ে উপযোগী। "
        "আউটপুট অবশ্যই শুধু ভ্যালিড JSON ফরম্যাটে দিতে হবে।"
    )

    user_prompt = (
        f"আজকের তারিখ: {today_str}\n\n"
        "নিচে আজকের বিভিন্ন সংবাদপত্রের তাজা খবর দেওয়া হলো:\n"
        + "\n".join(items_text) +
        "\n\nঅনুগ্রহ করে এই তালিকা থেকে আজকের সবচেয়ে বড় বা আলোচিত ব্রেকিং ১টি খবর বাছাই কর।\n"
        "আউটপুট ফরম্যাট (শুধু JSON):\n"
        "{\n"
        '  "selected_index": 0,\n'
        '  "headline": "ব্রেকিং বাংলা শিরোনাম",\n'
        '  "core_event": "মূল ঘটনাটি কী তা নিয়ে স্পষ্ট ২ বাক্যের সারসংক্ষেপ",\n'
        '  "search_keywords": ["কিওয়ার্ড ১", "কিওয়ার্ড ২", "কিওয়ার্ড ৩"]\n'
        "}\n"
        "নোট: search_keywords এমন প্রধান নাম/শব্দ হবে যা দিয়ে অন্য পত্রিকাতেও একই খবর সার্চ করা যায়।"
    )

    try:
        result = call_groq(system_prompt, user_prompt)
        sel_idx = int(result.get("selected_index", 0))
        if 0 <= sel_idx < len(sample_pool):
            chosen = sample_pool[sel_idx]
        else:
            chosen = sample_pool[0]

        return {
            "headline": result.get("headline") or chosen["title"],
            "core_event": result.get("core_event") or chosen.get("description", ""),
            "search_keywords": result.get("search_keywords") or [w for w in _tokens(chosen["title"])][:3],
            "primary_candidate": chosen,
            "via_ai": True,
        }
    except Exception as exc:
        print(f"[picker] AI দিয়ে বাছাইয়ে সমস্যা: {exc} — অ্যালগরিদমিক নিয়মে বাছা হচ্ছে")
        chosen = sample_pool[0]
        return {
            "headline": chosen["title"],
            "core_event": chosen.get("description") or chosen["title"],
            "search_keywords": list(_tokens(chosen["title"]))[:3],
            "primary_candidate": chosen,
            "via_ai": False,
        }


def _norm_site(name):
    clean = re.sub(r"\d+[hmsd]$|\d+\s*(ঘণ্টা|মিনিট|দিন|ঘন্টা).*$", "", (name or "")).strip().lower()
    mapping = {
        "প্রথম আলো": "prothomalo", "prothom alo": "prothomalo", "prothomalo": "prothomalo",
        "যুগান্তর": "jugantor", "jugantor": "jugantor",
        "ডেইলি স্টার": "thedailystar", "the daily star": "thedailystar", "thedailystar": "thedailystar",
        "ইত্তেফাক": "ittefaq", "ittefaq": "ittefaq", "daily ittefaq": "ittefaq",
        "সমকাল": "samakal", "samakal": "samakal",
        "কালের কণ্ঠ": "kalerkantho", "kaler kantho": "kalerkantho", "kalerkantho": "kalerkantho",
        "বাংলাদেশ প্রতিদিন": "bd-pratidin", "bangladesh pratidin": "bd-pratidin",
        "বিডিনিউজ২৪": "bdnews24", "bdnews24": "bdnews24",
        "জাগোনিউজ২৪": "jagonews24", "jagonews24": "jagonews24",
        "বাংলা ট্রিবিউন": "banglatribune", "bangla tribune": "banglatribune",
    }
    for k, v in mapping.items():
        if k in clean:
            return v
    return clean


def match_and_synthesize_sources(chosen_story, candidate_list):
    """
    বাছাইকৃত খবরের সাথে অন্য কোন কোন পত্রিকার রিপোর্ট মিলছে তা নিশ্চিত করা এবং তাদের দৃষ্টিভঙ্গি সংশ্লেষণ করা।
    """
    story_headline = chosen_story["headline"]
    story_event = chosen_story["core_event"]

    # ক্যান্ডিডেটদের সংক্ষেপিত তালিকা তৈরি
    items_to_evaluate = []
    for idx, c in enumerate(candidate_list[:25]):
        items_to_evaluate.append(
            f"[{idx}] পত্রিকা: {c.get('site', 'অজ্ঞাত')} | শিরোনাম: {c.get('title')} | সারসংক্ষেপ: {(c.get('description') or '')[:180]}"
        )

    system_prompt = (
        "তুমি একজন বিশেষজ্ঞ আন্তর্জাতিক ও জাতীয় সংবাদ বিশ্লেষক। তোমাকে একটি প্রধান ব্রেকিং খবর এবং অন্য কিছু সংবাদ দেওয়া হলো। "
        "তোমার কাজ হলো:\n"
        "১. কোন কোন সংবাদ ঠিক এই একই ঘটনা/বিষয়ের ওপর রিপোর্ট করেছে তা শনাক্ত করা (matched_indices)।\n"
        "২. বিভিন্ন পত্রিকার তথ্যের ভিত্তিতে একটি সার্বিক সারসংক্ষেপ তৈরি করা (overall_synthesis)।\n"
        "৩. প্রতিটি পত্রিকা কোন বিশেষ দিক বা বক্তব্য তুলে ধরেছে তা উল্লেখ করা।\n"
        "আউটপুট অবশ্যই শুধু ভ্যালিড JSON হতে হবে।"
    )

    user_prompt = (
        f"প্রধান খবর:\nশিরোনাম: {story_headline}\nঘটনা: {story_event}\n\n"
        "মূল্যায়ন করার মতো অন্যান্য সংবাদ প্রতিবেদন:\n"
        + "\n".join(items_to_evaluate) +
        "\n\nJSON ফরম্যাট:\n"
        "{\n"
        '  "overall_synthesis": "সব সোর্সের তথ্যের সমন্বয়ে ঘটনার সার্বিক ৩-৪ বাক্যের বিবরণ",\n'
        '  "matched_sources": [\n'
        "    {\n"
        '      "index": 0,\n'
        '      "angle": "এই পত্রিকা কোন দিক বা কার বক্তব্য তুলে ধরেছে",\n'
        '      "key_points": ["মূল পয়েন্ট ১", "মূল পয়েন্ট ২"]\n'
        "    }\n"
        "  ]\n"
        "}"
    )

    try:
        data = call_groq(system_prompt, user_prompt, max_tokens=3000)
        overall_synthesis = data.get("overall_synthesis", story_event)
        matched_results = []
        seen_sites = set()

        for match_item in data.get("matched_sources", []):
            idx = int(match_item.get("index", -1))
            if 0 <= idx < len(candidate_list):
                cand = candidate_list[idx]
                site_name = cand.get("site", "সংবাদমাধ্যম")
                norm_key = _norm_site(site_name)
                if norm_key in seen_sites:
                    continue
                seen_sites.add(norm_key)

                matched_results.append({
                    "site": site_name,
                    "title": cand.get("title", ""),
                    "url": cand.get("url", ""),
                    "published": cand.get("published"),
                    "img": cand.get("img"),
                    "og_image": cand.get("og_image"),
                    "extra_images": cand.get("extra_images", []),
                    "body": cand.get("body") or cand.get("description", ""),
                    "angle": match_item.get("angle", ""),
                    "key_points": match_item.get("key_points", []),
                })

        return overall_synthesis, matched_results

    except Exception as exc:
        print(f"[match] AI দিয়ে ম্যাচিংয়ে সমস্যা: {exc} — টেক্সট মিলের ভিত্তিতে নেওয়া হচ্ছে")
        # Fallback: Token overlap check
        matched_results = []
        seen_sites = set()
        chosen_tokens = _tokens(story_headline + " " + story_event)
        for cand in candidate_list:
            cand_tokens = _tokens(cand.get("title", "") + " " + (cand.get("description") or ""))
            overlap = len(chosen_tokens & cand_tokens)
            if overlap >= 2:
                site = cand.get("site", "সংবাদমাধ্যম")
                if site in seen_sites:
                    continue
                seen_sites.add(site)
                matched_results.append({
                    "site": site,
                    "title": cand.get("title", ""),
                    "url": cand.get("url", ""),
                    "published": cand.get("published"),
                    "img": cand.get("img"),
                    "og_image": cand.get("og_image"),
                    "extra_images": cand.get("extra_images", []),
                    "body": cand.get("body") or cand.get("description", ""),
                    "angle": cand.get("description", "")[:120],
                    "key_points": [cand.get("title", "")],
                })
        return story_event, matched_results
