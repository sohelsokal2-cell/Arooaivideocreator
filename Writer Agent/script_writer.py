import json
import os
import re

import gemini_api

_BN_DIGITS = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")


def _to_bn_digits(text):
    if not text:
        return ""
    return str(text).translate(_BN_DIGITS)


def _clean(text):
    return re.sub(r"\s+", " ", (text or "")).strip()


SYSTEM_PROMPT = (
    "তুমি একজন প্রবীণ ও অত্যন্ত দক্ষ টেলিভিশন এবং ডিজিটাল মিডিয়া নিউজ স্ক্রিপ্ট রাইটার। "
    "তোমার কাজ হলো বিভিন্ন সংবাদমাধ্যম থেকে যাচাইকৃত তথ্যের ভিত্তিতে একটি ৪৫ থেকে ৬০ সেকেন্ডের "
    "টানটান, আকর্ষণীয় ও তথ্যবহুল রিল/শর্টস ভয়েস-ওভার স্ক্রিপ্ট তৈরি করা।"
)

STRICT_RULES = [
    "১. বানানের ক্ষেত্রে ১০০% নির্ভুল হবে। বিশেষ করে জাতীয় নেতাদের নাম (যেমন: 'শেখ হাসিনা'—কখনোই 'শেক' নয়), পদবি, মন্ত্রণালয় এবং ভৌগোলিক নাম সম্পূর্ণ শুদ্ধ বানান হতে হবে।",
    "২. তথ্য উপস্থাপনে অবশ্যই স্পষ্ট রেফারেন্স ও প্রেক্ষিত থাকবে: কে বলেছেন, কবে বলেছেন, কোন আদালতে বা কোন অনুষ্ঠানে বলেছেন তা স্ক্রিপ্টে স্পষ্টভাবে তুলে ধরবে। কোনো মনগড়া বা ভাসা-ভাসা তথ্য দেবে না (যেমন: শুধু '৬৭৩টি মামলা' না বলে 'আন্তর্জাতিক অপরাধ ট্রাইব্যুনাল ও ঢাকার বিভিন্ন আদালতে মোট ৬৭৩টি মামলা' এভাবে নির্দিষ্ট করবে)।",
    "৩. কোনো পত্রিকার নাম বা সাধারণ উৎসের নাম উল্লেখ করবে না (যেমন: 'প্রথম আলো জানিয়েছে', 'ডেইলি স্টার বলছে')। আত্মবিশ্বাসী নিউজ প্রেজেন্টারের মতো সত্য ও তথ্যবহুল সরকারি/আইনি বিবরণ দেবে।",
    "৪. স্ক্রিপ্টের মোট শব্দসংখ্যা অবশ্যই ৮০ থেকে ১০০ শব্দের মধ্যে হতে হবে। বাক্যগুলো হবে একদম ছোট ছোট (৪-৭ শব্দের বাক্য), সহজ সরল কথ্য বাংলায়—যাতে সাধারণ মানুষ একবারে শুনেই বুঝতে পারে।",
    "৫. প্রথম বাক্যেই দর্শকের পুরো মনোযোগ কাড়তে একটি শক্তিশালী ও মানবিক হুক (Hook) ব্যবহার করবে। ক্লিকবেইট বা ফাঁকা আওয়াজ (যেমন: 'সত্যি কি?' কিন্তু ভেতরে কোনো উত্তর নেই—এমন) পরিহার করে সরাসরি ঘটনার রহস্য ও মূল সত্যটি বলবে।",
    "৬. সব সংখ্যা ও সাল অবশ্যই বাংলা অঙ্কে লিখবে। কঠিন বা অপ্রয়োজনীয় জটিল যুক্তবর্ণ এড়িয়ে সহজ সমার্থক শব্দ ব্যবহার করবে।",
    "৭. প্রতিটি বাক্যের শেষে স্বাভাবিক দাড়ি (।) বা কমা (,) ব্যবহার করবে যাতে ভয়েস-ওভারে বক্তা স্বাভাবিক মানুষের মতো নিঃশ্বাস ও বিরতি নিতে পারে।",
    "৮. স্ক্রিপ্টের শেষে দর্শকদের মন্তব্য ও মতামত আহ্বান জানিয়ে একটি সংক্ষিপ্ত সমাপনী প্রশ্ন বা বার্তা (Outro) রাখবে।",
]


def build_reel_prompt(story_data, target_seconds=50):
    headline = story_data.get("headline", "")
    synthesis = story_data.get("overall_synthesis", "")
    sources = story_data.get("sources", [])

    facts_lines = []
    for s in sources:
        pts = s.get("key_points", [])
        body_snippet = (s.get("body") or "")[:400]
        pts_str = " | ".join(pts) if pts else ""
        facts_lines.append(f"- তথ্য ও বিবরণ: {body_snippet}")
        if pts_str:
            facts_lines.append(f"  মূল বক্তব্য/পয়েন্ট: {pts_str}")

    combined_facts = "\n".join(facts_lines)

    prompt = (
        f"সংবাদের মূল বিষয়: {headline}\n"
        f"সার্বিক প্রেক্ষাপট: {synthesis}\n\n"
        f"যাচাইকৃত তথ্যাবলী (সরাসরি সংবাদ বিবরণ থেকে):\n{combined_facts}\n\n"
        f"লক্ষ্য সময়: প্রায় {target_seconds} সেকেন্ড (৯০ থেকে ১২০ শব্দ)।\n\n"
        "নিয়মাবলী:\n" + "\n".join(STRICT_RULES) + "\n\n"
        "আউটপুট ফরম্যাট (শুধু বৈধ JSON):\n"
        "{\n"
        '  "hook": "প্রথম ৩-৪ সেকেন্ডের শক্তিশালী উদ্বোধনী হুক বাক্য",\n'
        '  "body": "মূল ঘটনার বিবরণ ও গুরুত্বপূর্ণ বক্তব্যের তথ্যবহুল অংশ (৩-৫ বাক্য)",\n'
        '  "outro": "দর্শকদের উদ্দেশ্যে মতামত আহ্বানমূলক সমাপনী প্রশ্ন বা বাক্য",\n'
        '  "full_script": "হুক, বডি ও আউট্রো মিলিয়ে একটানা সম্পূর্ণ ভয়েস-ওভার স্ক্রিপ্ট",\n'
        '  "word_count": 105,\n'
        '  "scenes": [\n'
        '    {"scene_num": 1, "text": "হুক বাক্য...", "image_index": 1},\n'
        '    {"scene_num": 2, "text": "ঘটনার সূচনা...", "image_index": 2},\n'
        '    {"scene_num": 3, "text": "মূল বক্তব্য বা তথ্য...", "image_index": 3},\n'
        '    {"scene_num": 4, "text": "প্রেক্ষাপট বা অতিরিক্ত তথ্য...", "image_index": 4},\n'
        '    {"scene_num": 5, "text": "সমাপনী প্রশ্ন...", "image_index": 5}\n'
        '  ]\n'
        "}"
    )
    return prompt


def write_reel_script(story_data, target_seconds=50):
    user_prompt = build_reel_prompt(story_data, target_seconds=target_seconds)

    try:
        parsed = gemini_api.ask_gemini(
            user_prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=0.4,
            max_output_tokens=1500,
        )

        full_script = _clean(parsed.get("full_script") or f"{parsed.get('hook', '')} {parsed.get('body', '')} {parsed.get('outro', '')}")
        full_script = _to_bn_digits(full_script)

        # সোর্স নাম যাতে কোনোভাবে না আসে তা ফিল্টার করা
        for forbidden in ["প্রথম আলো", "ডেইলি স্টার", "যুগান্তর", "কালের কণ্ঠ", "সমকাল", "ইত্তেফাক", "রয়টার্স", "বিবিসি"]:
            full_script = full_script.replace(f"{forbidden} জানিয়েছে,", "").replace(f"{forbidden} সূত্রে,", "").replace(forbidden, "")

        parsed["full_script"] = _clean(full_script)
        parsed["word_count"] = len(parsed["full_script"].split())

        # সিনগুলোর সংখ্যা বাংলা করা
        scenes = parsed.get("scenes", [])
        for sc in scenes:
            sc["text"] = _clean(_to_bn_digits(sc.get("text", "")))

        return parsed

    except Exception as exc:
        print(f"[writer] Gemini API দিয়ে স্ক্রিপ্ট তৈরিতে সমস্যা ({exc}) — স্বয়ংক্রিয় ফলব্যাক ব্যবহার হচ্ছে")
        # Fallback script generation
        headline = story_data.get("headline", "")
        synthesis = story_data.get("overall_synthesis", "")
        hook = f"আজকের সবচেয়ে বড় ব্রেকিং সংবাদ: {headline}!"
        body = f"{synthesis} এ ঘটনায় সংশ্লিষ্ট মহল থেকে তীব্র প্রতিক্রিয়া জানানো হয়েছে এবং পরিস্থিতি গুরুত্বের সাথে পর্যবেক্ষণ করা হচ্ছে।"
        outro = "এই বিষয়ে আপনার কী মতামত? কমেন্টে জানান।"
        full = _clean(_to_bn_digits(f"{hook} {body} {outro}"))

        return {
            "hook": hook,
            "body": body,
            "outro": outro,
            "full_script": full,
            "word_count": len(full.split()),
            "estimated_seconds": 45,
            "scenes": [
                {"scene_num": 1, "text": hook, "image_index": 1},
                {"scene_num": 2, "text": synthesis, "image_index": 2},
                {"scene_num": 3, "text": outro, "image_index": 3},
            ],
            "fallback": True,
        }
