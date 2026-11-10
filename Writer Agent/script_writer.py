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


def normalize_spoken_bengali(text):
    """
    ভয়েস-ওভারের জন্য লিখিত টেক্সটকে মানুষের স্বাভাবিক কথ্য রূপ দেয়।
    যেমন: সময় '৬:৩০' বা '৬টা ৩০' কে 'সাড়ে ছয়টা' রূপান্তর করা।
    """
    if not text:
        return ""
    
    # সময়ের কথ্য রূপ
    text = re.sub(r"([০-৯0-9]+)\s*[:.]\s*৩০\s*মিনিট[েএ]?", r"সাড়ে \1টায়", text)
    text = re.sub(r"([০-৯0-9]+)\s*টা\s*৩০\s*মিনিট[েএ]?", r"সাড়ে \1টায়", text)
    text = re.sub(r"([০-৯0-9]+)\s*[:.]\s*১৫\s*মিনিট[েএ]?", r"সোয়া \1টায়", text)
    text = re.sub(r"([০-৯0-9]+)\s*[:.]\s*৪৫\s*মিনিট[েএ]?", r"পৌনে \1টায়", text)
    
    # সংখ্যা রূপান্তর
    text = _to_bn_digits(text)
    return text


SYSTEM_PROMPT = (
    "তুমি একজন প্রবীণ ও অত্যন্ত দক্ষ অনুসন্ধানী সাংবাদিক এবং ডিজিটাল ভিডিও কনটেন্ট ডিরেক্টর। "
    "তোমার কাজ হলো যাচাইকৃত সংবাদের ওপর ভিত্তি করে একটি পূর্ণাঙ্গ ৪৫ থেকে ৫৫ সেকেন্ডের "
    "(অবশ্যই ৯০ থেকে ১১০ শব্দ) টানটান, আকর্ষণীয় ও গভীর তথ্যবহুল বাংলা রিল স্ক্রিপ্ট তৈরি করা।"
)

STRICT_RULES = [
    "১. [শব্দসংখ্যা ও সময়কাল]: স্ক্রিপ্টের শব্দসংখ্যা অবশ্যই ৯০ থেকে ১১০ শব্দের মধ্যে হতে হবে। ৬০-৭০ শব্দের ছোট বা অসম্পূর্ণ স্ক্রিপ্ট লেখা নিষিদ্ধ। রিলের লক্ষ্য সময় ৪৫ থেকে ৫৫ সেকেন্ড।",
    "২. [বানানের নির্ভুলতা]: বানান ১০০% খাঁটি হবে। জাতীয় ব্যক্তিত্বদের নাম (যেমন: 'শেখ হাসিনা'—কখনোই 'শেক' নয়), পদবি, মন্ত্রণালয় এবং ভৌগোলিক নাম নির্ভুল হতে হবে।",
    "৩. [গভীর তথ্য ও প্রেক্ষিত]: সংবাদে বর্ণিত মূল ঘটনার সাথে সাথে প্রেক্ষাপট, কারণ ও প্রভাব যুক্ত করবে। কে বলেছেন, কোথায় বলেছেন, কী আলোচনা হয়েছে এবং এর ফলাফল কী হতে পারে—তা সুনির্দিষ্টভাবে বলবে।",
    "৪. [কথ্য ভাষা ও মানুষের মতো প্রবাহ]: বাক্যগুলো হবে ছোট ছোট (৫-৮ শব্দ), সহজ কথ্য বাংলায়। সময় লেখার সময় 'সন্ধ্যা ৬:৩০ মিনিট' না লিখে 'সন্ধ্যা সাড়ে ছয়টা' বা 'সকাল সাড়ে সাতটা'র মতো স্বাভাবিক কথ্য রূপ ব্যবহার করবে।",
    "৫. [শক্তিশালী হুক]: প্রথম ৩ সেকেন্ডেই দর্শকের মনোযোগ কাড়তে একটি শক্তিশালী প্রশ্নাতীত ও চাঞ্চল্যকর হুক দিয়ে শুরু করবে। কোনো ক্লিকবেইট ছাড়া সরাসরি মূল ঘটনাটি বলবে।",
    "৬. [সংবাদপত্রের নাম বাদ]: কোনো পত্রিকার নাম বা প্রচারমাধ্যমের নাম (যেমন: প্রথম আলো, বিবিসি, সমকাল) মুখে বলবে না। নিরপেক্ষ ও আত্মবিশ্বাসী নিউজ প্রেজেন্টারের ভাষায় বলবে।",
    "৭. [স্মার্ট ও ক্যাটাগরি-ভিত্তিক আউট্রো]: বাঁধাধরা 'আপনার মতামত জানান' পরিহার করে সংবাদের প্রসঙ্গের সাথে মিলিয়ে একটি চিন্তাশীল সমাপনী প্রশ্ন রাখবে (যেমন: এই সমঝোতা কি আন্তর্জাতিক অঙ্গনে নতুন মোড় নেবে? আপনার মতামত লিখুন)।",
    "৮. [ভিজ্যুয়াল দৃশ্য নির্দেশনা (Visual Cue)]: প্রতিটি সিনের সাথে ভিডিও এডিটরের জন্য পরিষ্কার দৃশ্য নির্দেশনা (Visual Cue) দেবে (যেমন: বৈঠকের টেবিলের ছবি, মানচিত্র ও বিমান রুট, দুই নেতার করমর্দন ইত্যাদি)।",
]


def build_reel_prompt(story_data, target_seconds=50):
    headline = story_data.get("headline", "")
    synthesis = story_data.get("overall_synthesis", "")
    core_event = story_data.get("core_event", "")
    sources = story_data.get("sources", [])

    facts_lines = []
    for s in sources:
        pts = s.get("key_points", [])
        body_snippet = (s.get("body") or "")[:600]
        pts_str = " | ".join(pts) if pts else ""
        facts_lines.append(f"- তথ্য ও বিবরণ: {body_snippet}")
        if pts_str:
            facts_lines.append(f"  মূল বক্তব্য/পয়েন্ট: {pts_str}")

    combined_facts = "\n".join(facts_lines)

    prompt = (
        f"সংবাদের শিরোনাম: {headline}\n"
        f"মূল ঘটনা: {core_event}\n"
        f"সার্বিক প্রেক্ষাপট: {synthesis}\n\n"
        f"সংগৃহীত পূর্ণাঙ্গ তথ্য বিবরণ:\n{combined_facts}\n\n"
        f"লক্ষ্য সময়: ৪৫-৫৫ সেকেন্ড। শব্দসংখ্যা: অবশ্যই ৯০ থেকে ১১০ শব্দ।\n\n"
        "নিয়মাবলী:\n" + "\n".join(STRICT_RULES) + "\n\n"
        "আউটপুট ফরম্যাট (শুধু বৈধ JSON):\n"
        "{\n"
        '  "hook": "প্রথম ৩-৪ সেকেন্ডের শক্তিশালী উদ্বোধনী হুক বাক্য (১২-১৫ শব্দ)",\n'
        '  "body": "ঘটনার সম্পূর্ণ প্রেক্ষাপট, সুনির্দিষ্ট তথ্য ও আলোচনার বিস্তারিত বিবরণ (৭০-৮০ শব্দ)",\n'
        '  "outro": "সংবাদের সাথে প্রাসঙ্গিক আকর্ষণীয় ও চিন্তাশীল সমাপনী প্রশ্ন (১০-১৫ শব্দ)",\n'
        '  "full_script": "হুক, বডি ও আউট্রো মিলিয়ে একটানা সম্পূর্ণ ভয়েস-ওভার স্ক্রিপ্ট (মোট ৯০-১১০ শব্দ)",\n'
        '  "word_count": 98,\n'
        '  "scenes": [\n'
        '    {"scene_num": 1, "text": "হুক বাক্য...", "visual_cue": "উদ্বোধনী দৃশ্য বা মূল ব্যক্তিত্বের ছবি", "image_index": 1},\n'
        '    {"scene_num": 2, "text": "ঘটনার মূল বিবরণ...", "visual_cue": "বৈঠক বা সম্মেলন হলের ছবি", "image_index": 2},\n'
        '    {"scene_num": 3, "text": "সুনির্দিষ্ট আলোচনা ও চুক্তি...", "visual_cue": "মানচিত্র বা দুই দেশের পতাকা/নেতাদের করমর্দন", "image_index": 3},\n'
        '    {"scene_num": 4, "text": "প্রেক্ষাপট ও প্রভাব...", "visual_cue": "অর্থনৈতিক বা রাজনৈতিক প্রাসঙ্গিক দৃশ্য", "image_index": 4},\n'
        '    {"scene_num": 5, "text": "সমাপনী প্রশ্ন...", "visual_cue": "চ্যানেল লোগো ও মন্তব্য বক্স ফোকাস", "image_index": 5}\n'
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
            temperature=0.35,
            max_output_tokens=2000,
        )

        full_script = _clean(parsed.get("full_script") or f"{parsed.get('hook', '')} {parsed.get('body', '')} {parsed.get('outro', '')}")
        full_script = normalize_spoken_bengali(full_script)

        # সোর্স নাম যাতে কোনোভাবে না আসে তা ফিল্টার করা
        for forbidden in ["প্রথম আলো", "ডেইলি স্টার", "যুগান্তর", "কালের কণ্ঠ", "সমকাল", "ইত্তেফাক", "রয়টার্স", "বিবিসি"]:
            full_script = full_script.replace(f"{forbidden} জানিয়েছে,", "").replace(f"{forbidden} সূত্রে,", "").replace(forbidden, "")

        parsed["full_script"] = _clean(full_script)
        parsed["word_count"] = len(parsed["full_script"].split())

        # সিনগুলোর সংখ্যা ও টেক্সট নরমালাইজ করা
        scenes = parsed.get("scenes", [])
        for sc in scenes:
            sc["text"] = _clean(normalize_spoken_bengali(sc.get("text", "")))
            if "visual_cue" not in sc:
                sc["visual_cue"] = "প্রাসঙ্গিক সংবাদ ছবি ও দৃশ্য"

        return parsed

    except Exception as exc:
        print(f"[writer] Gemini API দিয়ে স্ক্রিপ্ট তৈরিতে সমস্যা ({exc}) — উন্নত ফলব্যাক ব্যবহার হচ্ছে")
        headline = story_data.get("headline", "")
        core = story_data.get("core_event") or story_data.get("overall_synthesis", "")
        
        hook = f"আজকের আন্তর্জাতিক অঙ্গনের সবচেয়ে বড় আলোচিত সংবাদ: {headline}!"
        body = f"{core} এই গুরুত্বপূর্ণ সফরে দুই দেশের অর্থনৈতিক ও রাজনৈতিক সহযোগিতার নতুন দিগন্ত উন্মোচিত হতে যাচ্ছে বলে কূটনৈতিক সূত্র জানিয়েছে। পুরো বিশ্ব এখন এই বৈঠকের সিদ্ধান্তের দিকে নজর রাখছে।"
        outro = "এই ঐতিহাসিক পদক্ষেপ কি দুই দেশের অর্থনীতিতে নতুন জোয়ার আনবে? কমেন্টে আপনার মতামত জানান।"
        
        full = _clean(normalize_spoken_bengali(f"{hook} {body} {outro}"))

        return {
            "hook": hook,
            "body": body,
            "outro": outro,
            "full_script": full,
            "word_count": len(full.split()),
            "estimated_seconds": 50,
            "scenes": [
                {"scene_num": 1, "text": hook, "visual_cue": "ব্রেকিং শিরোনাম ও মূল নেতার পোর্ট্রেট", "image_index": 1},
                {"scene_num": 2, "text": body[:120], "visual_cue": "বৈঠক বা সম্মেলন কক্ষের ছবি", "image_index": 2},
                {"scene_num": 3, "text": body[120:], "visual_cue": "মানচিত্র ও দ্বিপাক্ষিক সম্পর্কের গ্রাফিক্স", "image_index": 3},
                {"scene_num": 4, "text": outro, "visual_cue": "চ্যানেল ব্র্যান্ডিং ও মন্তব্য আহ্বান", "image_index": 4},
            ],
            "fallback": True,
        }

