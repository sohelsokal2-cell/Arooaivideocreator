import re

ONES = {
    0: "শূন্য", 1: "এক", 2: "দুই", 3: "তিন", 4: "চার", 5: "পাঁচ", 6: "ছয়", 7: "সাত", 8: "আট", 9: "নয়",
    10: "দশ", 11: "এগারো", 12: "বারো", 13: "তেরো", 14: "চৌদ্দ", 15: "পনেরো", 16: "ষোলো", 17: "সতেরো", 18: "আঠারো", 19: "উনিশ",
    20: "বিশ", 21: "একুশ", 22: "বাইশ", 23: "তেইশ", 24: "চব্বিশ", 25: "পঁচিশ", 26: "ছাব্বিশ", 27: "সাতাশ", 28: "আঠাশ", 29: "উনত্রিশ",
    30: "ত্রিশ", 31: "একত্রিশ", 32: "বত্রিশ", 33: "তেত্রিশ", 34: "চৌত্রিশ", 35: "পঁয়ত্রিশ", 36: "ছত্রিশ", 37: "সাঁইত্রিশ", 38: "আটত্রিশ", 39: "উনচল্লিশ",
    40: "চল্লিশ", 41: "একচল্লিশ", 42: "বিয়াল্লিশ", 43: "তেতাল্লিশ", 44: "চুয়াল্লিশ", 45: "পঁয়তাল্লিশ", 46: "ছেচল্লিশ", 47: "সাতচল্লিশ", 48: "আটচল্লিশ", 49: "উনপঞ্চাশ",
    50: "পঞ্চাশ", 51: "একান্ন", 52: "বায়ান্ন", 53: "তিপ্পান্ন", 54: "চুয়ান্ন", 55: "পঞ্চান্ন", 56: "ছাপ্পান্ন", 57: "সাতান্ন", 58: "আটান্ন", 59: "উনষাট",
    60: "ষাট", 61: "একষট্টি", 62: "বাষট্টি", 63: "তেষট্টি", 64: "চৌষট্টি", 65: "পঁয়ষট্টি", 66: "ছেষট্টি", 67: "সাতষট্টি", 68: "আটষট্টি", 69: "উনসত্তর",
    70: "সত্তর", 71: "একাত্তর", 72: "বাহাত্তর", 73: "তিয়াত্তর", 74: "চৌহাত্তর", 75: "পঁচাত্তর", 76: "ছিয়াত্তর", 77: "সাতাত্তর", 78: "আটাত্তর", 79: "উনাশি",
    80: "আশি", 81: "একাশি", 82: "বিরাশি", 83: "তিরাশি", 84: "চৌরাশি", 85: "পঁচাশি", 86: "ছিয়াশি", 87: "সাতাশি", 88: "অষ্টআশি", 89: "ঊননব্বই",
    90: "নব্বই", 91: "একানব্বই", 92: "বানব্বই", 93: "তিরানব্বই", 94: "চৌরানব্বই", 95: "পঁচানব্বই", 96: "ছিয়ানব্বই", 97: "সাতানব্বই", 98: "আটানব্বই", 99: "নিরানব্বই"
}

BN_DIGITS = {"০": "0", "১": "1", "২": "2", "৩": "3", "৪": "4", "৫": "5", "৬": "6", "৭": "7", "৮": "8", "৯": "9"}

# "নয় শত"-এর মতো কৃত্রিম উচ্চারণ এড়িয়ে প্রচলিত বাংলা রূপ (নয়শ, আটশ, ...)।
HUNDREDS = {
    1: "একশ", 2: "দুইশ", 3: "তিনশ", 4: "চারশ", 5: "পাঁচশ",
    6: "ছয়শ", 7: "সাতশ", 8: "আটশ", 9: "নয়শ",
}

# কঠিন যুক্তবর্ণ ও জড়ানো শব্দসমূহের ফোনেটিক ম্যাপিং (যাতে স্পষ্ট ও সাবলীল শোনায়)
PHONETIC_FIXES = [
    (re.compile(r"প্রত্যর্পণ"), "প্রোত-তোর-পন"),
    (re.compile(r"গণঅভ্যুত্থান|গণ-অভ্যুত্থান"), "গণ-অভ্যুত্থান"),
    (re.compile(r"স্বরাষ্ট্রমন্ত্রী"), "স্ব-রাষ্ট্র মন্ত্রী"),
    (re.compile(r"পররাষ্ট্র\s*মন্ত্রণালয়"), "পর-রাষ্ট্র মন্ত্রণালয়"),
    (re.compile(r"স্বরাষ্ট্র\s*মন্ত্রণালয়"), "স্ব-রাষ্ট্র মন্ত্রণালয়"),
    (re.compile(r"প্রধানমন্ত্রীর"), "প্রধান-মন্ত্রীর"),
    (re.compile(r"প্রধানমন্ত্রী"), "প্রধান-মন্ত্রী"),
    (re.compile(r"আন্তর্জাতিক"), "আন্তর্-জাতিক"),
    (re.compile(r"বিশ্ববিদ্যালয়"), "বিশ্ব-বিদ্যালয়"),
    (re.compile(r"তদন্তকারী"), "তদন্ত-কারী"),
    (re.compile(r"গ্রেপ্তার|গ্রেফতার"), "গ্রেফ-তার"),
    (re.compile(r"অস্ত্রধারী"), "অস্ত্র-ধারী"),
    (re.compile(r"মুহুর্মুহু"), "মুহুর্-মুহু"),
    (re.compile(r"শ্বাসরোধ"), "শ্বাস-রোধ"),
    (re.compile(r"ময়নাতদন্ত"), "ময়না-তদন্ত"),
    (re.compile(r"হত্যাকাণ্ড|হত্যাকান্ড"), "হত্যা-কাণ্ড"),
    (re.compile(r"সাড়ে\s*সাতটায়|সাড়ে\s*সাতটায়"), "সাতটা ত্রিশ মিনিটে"),
    (re.compile(r"সাড়ে\s*সাতটা|সাড়ে\s*সাতটা"), "সাতটা ত্রিশ মিনিট"),
    (re.compile(r"সাড়ে\s*(\d+|[\u09e6-\u09ef]+)টায়"), r"\1টা ত্রিশ মিনিটে"),
    (re.compile(r"সাড়ে\s*(\d+|[\u09e6-\u09ef]+)টা"), r"\1টা ত্রিশ মিনিট"),
]

# Common English and acronym pronunciation map
ACRONYMS = [
    (re.compile(r"\bOpenAI\b", re.IGNORECASE), "ওপেন এআই"),
    (re.compile(r"\bMyAI\b", re.IGNORECASE), "মাই এআই"),
    (re.compile(r"\bAI\b|\bA\.I\.(?!\w)"), "এআই"),
    (re.compile(r"\bIGP\b|\bI\.G\.P\.\b"), "আইজিপি"),
    (re.compile(r"\bIMF\b|\bI\.M\.F\.\b"), "আইএমএফ"),
    (re.compile(r"\bICBE\b"), "আইসিবিই"),
    (re.compile(r"\bNVIDIA\b|\bNvidia\b", re.IGNORECASE), "এনভিডিয়া"),
    (re.compile(r"\bCTA\b"), "সিটিএ"),
    (re.compile(r"\bCEO\b"), "সিইও"),
    (re.compile(r"\bVIP\b"), "ভিআইপি"),
    (re.compile(r"\bUSD\b"), "মার্কিন ডলার"),
    (re.compile(r"\bYouTube\b", re.IGNORECASE), "ইউটিউব"),
    (re.compile(r"\bGoogle\b", re.IGNORECASE), "গুগল"),
    (re.compile(r"\bMicrosoft\b", re.IGNORECASE), "মাইক্রোসফট"),
    (re.compile(r"\bFacebook\b", re.IGNORECASE), "ফেসবুক"),
    (re.compile(r"\bTelegram\b", re.IGNORECASE), "টেলিগ্রাম"),
    (re.compile(r"\bWhatsApp\b", re.IGNORECASE), "হোয়াটসঅ্যাপ"),
    (re.compile(r"\bTwitter\b", re.IGNORECASE), "টুইটার"),
]


def num_to_words(n: int) -> str:
    """Convert an integer up to crores into Bangla words."""
    if n in ONES:
        return ONES[n]
    if n < 1000:
        h = n // 100
        rem = n % 100
        h_str = HUNDREDS.get(h, ONES[h] + " শত")
        return h_str + (" " + num_to_words(rem) if rem else "")
    if n < 100000:
        th = n // 1000
        rem = n % 1000
        th_str = num_to_words(th) + " হাজার"
        return th_str + (" " + num_to_words(rem) if rem else "")
    if n < 10000000:
        lakh = n // 100000
        rem = n % 100000
        lakh_str = num_to_words(lakh) + " লাখ"
        return lakh_str + (" " + num_to_words(rem) if rem else "")
    cr = n // 10000000
    rem = n % 10000000
    cr_str = num_to_words(cr) + " কোটি"
    return cr_str + (" " + num_to_words(rem) if rem else "")


SARE_X = "সাড়ে"
DOSOMIK_X = "দশমিক"
BN_DIGIT_WORDS = [ONES[i] for i in range(10)]
def _replace_numbers(match):
    raw_num = match.group(1)
    suffix = match.group(2) or ""

    en_digits = "".join(BN_DIGITS.get(c, c) for c in raw_num if c not in (",", " "))
    try:
        val = int(en_digits)
    except ValueError:
        return match.group(0)

    words = num_to_words(val)
    if suffix:
        # টি / টা read attached to the number; other suffixes read with a space
        if suffix in ("টি", "টা"):
            return words + suffix
        return f"{words} {suffix}".strip()
    return words


def _replace_decimals(match):
    int_part = match.group(1)
    dec_part = match.group(2)
    suffix = match.group(3) or ""

    int_en = "".join(BN_DIGITS.get(c, c) for c in int_part).replace(",", "")
    dec_en = "".join(BN_DIGITS.get(c, c) for c in dec_part)

    if int_en == "0" and dec_en == "5":
        res = "আধা"      # 0.5 -> আধা ("সাড়ে @SHUNNO@" would be nonsense)
    elif int_en == "1" and dec_en == "5":
        res = "দেড়"
    elif int_en == "2" and dec_en == "5":
        res = "আড়াই"
    elif dec_en == "5":
        # ONES-এ শুধু ০-৯৯ আছে — ১০০.৫-এর মতো সংখ্যায় আগে KeyError পড়ে
        # ASCII অঙ্কে নেমে যেত। num_to_words যেকোনো পূর্ণসংখ্যা সামলায়।
        try:
            res = f"সাড়ে {num_to_words(int(int_en))}"
        except (ValueError, KeyError):
            res = f"{int_en} দশমিক {dec_en}"
    else:
        # decimal digits are read one by one so leading zeros survive (0.05)
        try:
            int_words = num_to_words(int(int_en))
        except ValueError:
            int_words = int_en
        digit_words = []
        for d in dec_en:
            digit_words.append(BN_DIGIT_WORDS[int(d)] if d.isdigit() else d)
        res = f"{int_words} দশমিক " + " ".join(digit_words)

    if suffix:
        return f"{res} {suffix}".strip()
    return res


def _bn(d):
    return BN_DIGITS.get(d, d)


def _replace_time(match):
    """H:MM is spoken before the colon->comma normalization, e.g. "টা"-style reading, otherwise '9, 30'."""
    hh = _bn(match.group(1))
    mm = _bn(match.group(2))
    try:
        return f"{num_to_words(int(hh))}টা {num_to_words(int(mm))}"
    except Exception:
        return match.group(0)


def normalize_text(text: str) -> str:
    """Normalize Bengali text to ensure accurate pronunciation for TTS."""
    if not text:
        return ""

    # 0. convert H:MM times to words BEFORE the colon -> comma normalization below
    text = re.sub(r"(?<!\w)([\u09e6-\u09ef0-9]{1,2}):([\u09e6-\u09ef0-9]{2})(?!\w)", _replace_time, text)

    # 1. Clean symbols and colons that TTS stumbles on
    text = re.sub(r"\s*:\s*", ", ", text)
    text = re.sub(r"\s*/\s*", " বা ", text)
    text = re.sub(r"%", " শতাংশ ", text)
    text = re.sub(r"\$", " ডলার ", text)
    text = re.sub(r"&", " এবং ", text)
    text = re.sub(r"['\"\u2018\u2019\u201c\u201d`]", "", text)
    text = re.sub(r"\s*[-\u2013\u2014]{2,}\s*", " ", text)
    text = re.sub(r"\s*[-\u2013\u2014]\s*", ", ", text)

    # 2. Expand English terms & Acronyms
    for pattern, replacement in ACRONYMS:
        text = pattern.sub(replacement, text)

    # 2.1 কঠিন শব্দ ও যুক্তবর্ণ ফোনেটিকাল সহজ করা (হিউম্যান ফ্লো)
    for pattern, replacement in PHONETIC_FIXES:
        text = pattern.sub(replacement, text)

    # 3. Decimals (comma-grouped integer part now supported, e.g. 1,000.5)
    text = re.sub(r"([\u09e6-\u09ef0-9]+(?:,[\u09e6-\u09ef0-9]+)*)\.([\u09e6-\u09ef0-9]+)(?:\s*(মাসের|শতাংশ|টাকার|কোটি|টাকা|মাস|লাখ|গুণ))?", _replace_decimals, text)

    # 4. Standalone numbers with optional suffixes
    # \b fails after Bengali vowel signs, so \w-lookaround is used (handles টি/টা/টাকার endings)
    text = re.sub(r"(?<!\w)([\u09e6-\u09ef0-9]+(?:,[\u09e6-\u09ef0-9]+)*)(টাকার|শতাংশ|টাকা|জনের|গুণ|টি|টা|তম|জন|শ)?(?!\w)", _replace_numbers, text)

    # 5. Clean punctuation spacing
    text = re.sub(r"\s+([,।?!])", r"\1", text)
    text = re.sub(r"([,।?!])(?=[^\s,।?!])", r"\1 ", text)
    text = re.sub(r"!{2,}", "!", text)
    text = re.sub(r"\?{2,}", "?", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text
