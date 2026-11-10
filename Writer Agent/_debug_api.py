import requests

import gemini_api

key = gemini_api.api_key()
URL = "https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"
user_text = (
    "Banglay 2 line e salam bolo. "
    'Shudhu JSON output de: {"script":"..."}'
)


def call(model, extra=None, max_tokens=4096):
    payload = {
        "contents": [{"role": "user", "parts": [{"text": user_text}]}],
        "generationConfig": {
            "temperature": 0.5,
            "maxOutputTokens": max_tokens,
            "responseMimeType": "application/json",
        },
    }
    if extra:
        payload["generationConfig"].update(extra)
    r = requests.post(URL.format(m=model), params={"key": key}, json=payload, timeout=120)
    print("=====", model, extra, r.status_code)
    if r.status_code != 200:
        print(r.text[:400])
        return
    data = r.json()
    cand = (data.get("candidates") or [{}])[0]
    parts = (cand.get("content") or {}).get("parts") or []
    print("parts:", len(parts), "| keys per part:", [sorted(p.keys()) for p in parts])
    text = "".join(p.get("text", "") for p in parts)
    print("TEXT:", text[:400])
    print("finishReason:", cand.get("finishReason"))
    print()


call("gemini-2.0-flash-lite")
call("gemini-2.5-flash")
call("gemini-2.5-flash", {"thinkingConfig": {"thinkingBudget": 0}})
call("gemini-2.0-flash", {"thinkingConfig": {"thinkingBudget": 0}})
