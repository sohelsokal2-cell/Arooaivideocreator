import os
import logging
from app.config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

SYSTEM_PROMPTS = {
    "bn": """তুমি একজন অত্যন্ত চটপটে, আধুনিক ও হাস্যরসাত্মক স্ট্যান্ড-আপ কমেডিয়ান।
তোমাকে ইনস্টাগ্রাম রিলস ও টিকটকের জন্য ১৫-২৫ সেকেন্ডের (৩০ থেকে ৫০ শব্দের মধ্যে) একটি দুর্দান্ত কমেডি স্ক্রিপ্ট লিখতে হবে।

বৈশিষ্ট্য:
1. প্রথম ২ সেকেন্ডেই দর্শকদের মনোযোগ টানার মতো শক্তিশালী হুক থাকতে হবে।
2. দৈনন্দিন জীবনের কোনো প্যারা, স্ট্রেস, রিলেশনশিপ বা ফানি অভিজ্ঞতা নিয়ে কথা বলবে।
3. শেষের লাইনে থাকবে একটি অভাবনীয় হাসির টুইস্ট বা পাঞ্চলাইন!
4. মুখের স্বাভাবিক ডায়লগ হবে, কোনো অতিরিক্ত জটিল ভাষা নয়।
5. স্ক্রিপ্টে কোনো স্টেজ ডিরেকশন (যেমন [হাসি], [হাত নাড়া]) লিখবে না। শুধুমাত্র কথা বলার ডায়লগটুকু লিখবে।""",

    "hi": """आप एक बहुत ही स्मार्ट, मॉडर्न और मजेदार स्टैंड-अप कॉमेडियन हैं।
आपको इंस्टाग्राम रील्स और टिकटॉक के लिए 15-25 सेकंड (30 से 50 शब्दों में) का एक मजेदार स्टैंड-अप कॉमेडी स्क्रिप्ट लिखना है।

विशेषताएं:
1. पहली 2 सेकंड में ही हुक होना चाहिए (যেমন: "जब भी डिप्रेशन, टेंशन या मरने का ख्याल मन में आए...")
2. रिलेटेबल रोजमर्रा की जिंदगी, स्ट्रेस, प्यार या ऑफिस पर बात हो।
3. अंत में एक जबरदस्त पंचलाइन / ट्विस्ट होना चाहिए जो लोगों को हंसा दे।
4. बिल्कुल नेचुरल बोलचाल की हिंदी/हिंग्लिश होनी चाहिए।
5. कोई स्टेज डायरेक्शन (जैसे [हंसना], [ताली]) न लिखें। केवल बोलने वाले डायलॉग ही लिखें।""",

    "en": """You are a witty, charismatic, and relatable modern stand-up comedian.
Write a 15-25 second (30-50 words) punchy, viral stand-up comedy script for Instagram Reels / YouTube Shorts.

Rules:
1. Strong hook in the first 2 seconds (e.g. relatable everyday life frustration, dating, overthinking, anxiety).
2. Climax with an unexpected, hilarious punchline twist at the end.
3. Natural conversational tone like a real stand-up comic on stage with a mic.
4. Output ONLY the spoken dialogue. Do NOT include stage directions like [laughter], [pauses], or [applause]."""
}

async def generate_script(language: str = "bn", topic: str = "auto") -> dict:
    """
    Generates a comedic standup script using Gemini API.
    Returns: {"topic": str, "script": str, "language": str}
    """
    lang = language.lower()
    if lang not in SYSTEM_PROMPTS:
        lang = "bn"

    system_instruction = SYSTEM_PROMPTS[lang]

    user_query = f"Topic: {topic}" if topic and topic.lower() != "auto" else "Pick an ultra-relatable, funny everyday observation or adult life problem."

    if not GEMINI_API_KEY:
        # Fallback pre-crafted comedy scripts if API key is not yet set
        fallbacks = {
            "bn": {
                "topic": "ডিপ্রেশন ও ঘুম",
                "script": "যখনই ডিপ্রেশন বা লাইফে চরম প্যারা শুরু হয়, আমি কিন্তু কখনো কান্নাকাটি করি না। আমি সোজা চাদর মুড়ি দিয়ে ১০ ঘণ্টা ঘুমিয়ে যাই! কারণ আমি মরে গেলে সমস্যা শেষ, কিন্তু ঘুমিয়ে থাকলে সমস্যাও কিছুক্ষণ কনফিউশনে থাকে!"
            },
            "hi": {
                "topic": "टेंशन और हल",
                "script": "जब भी डिप्रेशन, टेंशन या मरने का ख्याल मन में आए, तो गंदी फिल्म देख लेना। ऊपर का टेंशन नीचे आ जाएगा, फिर मरने की जगह मारने की सोचोगे!"
            },
            "en": {
                "topic": "Adulting & Money",
                "script": "My doctor told me that stress and anxiety take years off your life. Good news is, that's fewer years I actually have to afford rent!"
            }
        }
        res = fallbacks.get(lang, fallbacks["bn"])
        return {
            "topic": res["topic"],
            "script": res["script"],
            "language": lang
        }

    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = f"{system_instruction}\n\nTask: {user_query}\nGive me ONLY the spoken script, without quotes."
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=prompt,
        )
        script_text = response.text.strip().replace('"', '')
        return {
            "topic": topic if topic and topic.lower() != "auto" else "Trending Comedy",
            "script": script_text,
            "language": lang
        }
    except Exception as e:
        logger.error(f"Error calling Gemini API: {e}")
        # Return fallback on error
        return {
            "topic": topic,
            "script": "Life is funny until you check your bank balance on Monday morning. Then it's a horror movie.",
            "language": lang
        }

