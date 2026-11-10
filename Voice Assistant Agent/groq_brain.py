"""
Voice Assistant Agent — Groq AI Brain & Intent Engine
======================================================
ইউজারের প্রম্পট বা কমান্ড বিশ্লেষণ করে ইনটেন্ট (Intent) এবং রেসপন্স তৈরি করে।
"""

import json
import os
import re
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def load_env():
    env_path = os.path.join(BASE_DIR, ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k:
                os.environ[k] = v

load_env()

API_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PROMPT = """\
আপনি 'বাঙালি ফ্যাক্টস' (@bangaliifacts) এআই রিলস ক্রিয়েটর স্টুডিওর অফিসিয়াল ভয়েস অ্যাসিস্ট্যান্ট।
আপনার দায়িত্ব হল ইউজারকে আন্তরিক, সংক্ষিপ্ত এবং পেশাদার বাংলায় সহায়তা করা এবং ইউজারের কথার উদ্দেশ্য (Intent) শনাক্ত করা।

কমান্ড অপশনসমূহ (Intents):
1. run_pipeline: ইউজার যদি নতুন রিল বানাতে, পাইপলাইন চালাতে, বা ভিডিও জেনারেট করতে বলে (e.g. "নতুন রিল বানাও", "পাইপলাইন চালাও", "create new reel")।
2. check_status: পাইপলাইনের অবস্থা বা শেষ রান জানতে চাইলে (e.g. "স্ট্যাটাস কি", "আগের রিল কি হয়েছে", "status check")।
3. get_news: আজকের খবর বা সংগৃহীত খবর জানতে চাইলে (e.g. "আজকের খবর কি", "কোন নিউজ নিয়ে কাজ করছ")।
4. get_links: প্রকাশিত ফেসবুক রিল বা ইউটিউব শর্টস এর লিংক জানতে চাইলে (e.g. "ভিডিওর লিংক দাও", "কোথায় পাবলিশ হয়েছে")।
5. chat: সাধারণ কথা, শুভেচ্ছা বা প্রশ্ন (e.g. "কেমন আছো", "তুমি কি কাজ করো")।
6. stop: অ্যাসিস্ট্যান্ট বন্ধ বা প্রস্থান করার নির্দেশ (e.g. "বিদায়", "বন্ধ করো", "exit", "quit")।

আউটপুট ফরম্যাট:
শুধুমাত্র এবং কঠোরভাবে একটি ভ্যালিড JSON অবজেক্ট রিটার্ন করবেন। কোনো অতিরিক্ত টেক্সট বা মার্কডাউন কোড ব্লক (```json) দেবেন না।

JSON স্কিমা:
{
  "intent": "run_pipeline | check_status | get_news | get_links | chat | stop",
  "spoken_response": "ইউজারকে শোনানোর জন্য মিষ্টি ও প্রাণবন্ত বাংলা উত্তর (১-৩ বাক্য)",
  "details": "অতিরিক্ত বিস্তারিত তথ্য যদি থাকে, না থাকলে খালি স্ট্রিং"
}
"""

def _extract_json(text: str) -> dict | None:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    s = text.find("{")
    e = text.rfind("}")
    if s != -1 and e != -1:
        try:
            return json.loads(text[s:e + 1])
        except json.JSONDecodeError:
            pass
    return None

def analyze_user_query(user_message: str, context_summary: str = "") -> dict:
    load_env()
    key = os.environ.get("VA_GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))
    model = os.environ.get("VA_GROQ_MODEL", os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b"))

    if not key:
        raise RuntimeError("VA_GROQ_API_KEY পাওয়া যায়নি। .env ফাইলে বসান।")

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    user_payload_prompt = f"""ইউজারের বার্তা: "{user_message}"

বর্তমান পাইপলাইন কনটেক্সট:
{context_summary}

এই বার্তার ইনটেন্ট এবং বাংলা রেসপন্স JSON আকারে দিন।"""

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_payload_prompt},
        ],
        "temperature": 0.5,
        "max_tokens": 500,
    }

    try:
        res = requests.post(API_URL, headers=headers, json=payload, timeout=20)
        if res.status_code == 200:
            content = res.json()["choices"][0]["message"]["content"]
            parsed = _extract_json(content)
            if parsed and "intent" in parsed:
                return parsed
    except Exception as exc:
        print(f"      ⚠️  ভয়েস অ্যাসিস্ট্যান্ট ব্রেন সতর্কতা: {exc}")

    # Fallback keyword matching
    msg_l = user_message.lower()
    if any(w in msg_l for w in ["রিল", "বানাও", "চালাও", "pipeline", "run"]):
        return {
            "intent": "run_pipeline",
            "spoken_response": "ঠিক আছে, আমি এখনই সম্পূর্ণ পাইপলাইন শুরু করছি। একটু অপেক্ষা করুন।",
            "details": "Triggering run_pipeline.py"
        }
    elif any(w in msg_l for w in ["খবর", "নিউজ", "news"]):
        return {
            "intent": "get_news",
            "spoken_response": "আমি আজকের সর্বশেষ আলোচিত সংবাদের তথ্য প্রস্তুত করছি।",
            "details": "Fetching news"
        }
    elif any(w in msg_l for w in ["লিংক", "link", "ইউটিউব", "ফেসবুক"]):
        return {
            "intent": "get_links",
            "spoken_response": "সর্বশেষ প্রকাশিত ফেসবুক এবং ইউটিউব রিলের লিংক আমি তুলে ধরছি।",
            "details": "Fetching published links"
        }
    elif any(w in msg_l for w in ["status", "অবস্থা", "স্ট্যাটাস"]):
        return {
            "intent": "check_status",
            "spoken_response": "আমি পাইপলাইনের বর্তমান অবস্থা চেক করে দিচ্ছি।",
            "details": "Checking pipeline state"
        }
    elif any(w in msg_l for w in ["exit", "quit", "বন্ধ", "বাই", "বিদায়"]):
        return {
            "intent": "stop",
            "spoken_response": "ধন্যবাদ! বাঙালি ফ্যাক্টস এর সাথে থাকার জন্য। আপনার দিনটি শুভ হোক।",
            "details": "Exiting"
        }

    return {
        "intent": "chat",
        "spoken_response": "আমি বাঙালি ফ্যাক্টস এর ভয়েস অ্যাসিস্ট্যান্ট। আপনি আমাকে নতুন রিল বানাতে বা খবরের আপডেট জানতে বলতে পারেন।",
        "details": ""
    }

