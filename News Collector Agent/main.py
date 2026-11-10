import argparse
import os
import re
import shutil
import sys
import time
from datetime import datetime, timedelta, timezone

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import ai_picker
from history_manager import get_today_run_count, is_already_covered_today, record_story, STOPWORDS
from images import download_images
from report import write_consolidated_report
from scraper import collect_candidates, enrich_candidates, enrich_one, search_bing_news_general
from sites import parse_websites_doc

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# বাংলাদেশ সময় (UTC+6, DST নেই)
DHAKA_TZ = timezone(timedelta(hours=6))


def collect_all_candidates(sites, enrich_pool=4):
    """প্রতিটি সাইট থেকে তাজা খবরের ক্যান্ডিডেট সংগ্রহ করে।"""
    all_candidates = []
    pools_by_site = {}
    for site in sites:
        site_name = site["name"]
        print(f"[1/4] {site_name}: তাজা সংবাদ সংগ্রহ চলছে...")
        candidates = collect_candidates(site)
        if not candidates:
            print(f"      কোনো খবর পাওয়া যায়নি ({site['host']})")
            pools_by_site[site_name] = []
            continue
        # প্রাথমিক ক্যান্ডিডেটে সাইটের নাম যুক্ত করা
        for c in candidates:
            c["site"] = site_name
        # শীর্ষ কিছু ক্যান্ডিডেট enrich করা
        enriched = enrich_candidates(candidates, pool=enrich_pool)
        pools_by_site[site_name] = enriched
        all_candidates.extend(enriched)
        print(f"      {len(enriched)}টি খবর সংগৃহীত")
    return all_candidates, pools_by_site


def find_cross_source_coverage(chosen_story, all_candidates, min_sources=3):
    """
    বাছাইকৃত খবরের জন্য অন্য কোন কোন পত্রিকায় রিপোর্ট প্রকাশিত হয়েছে তা খুঁজে বের করে।
    যদি বিদ্যমান পুল থেকে যথেষ্ট সোর্স না মেলে, তবে লাইভ সার্চ (যেমন Bing) দিয়ে অতিরিক্ত সোর্স আনা হয়।
    """
    keywords = chosen_story.get("search_keywords", [])
    primary = chosen_story.get("primary_candidate", {})
    primary_site = primary.get("site")
    primary_url = primary.get("url")

    # নিশ্চিত করা যাতে প্রাইমারি ক্যান্ডিডেট enrich করা থাকে
    if not primary.get("body"):
        enrich_one(primary)

    # সম্ভাব্য সোর্স ক্যান্ডিডেটদের একটি তালিকা তৈরি
    candidate_matches = []
    seen_urls = {primary_url}
    candidate_matches.append(primary)

    # ১. অন্যান্য পত্রিকাগুলোর ক্যান্ডিডেট পুলে খোঁজা
    for cand in all_candidates:
        if cand["url"] in seen_urls:
            continue
        # সাধারণ কিওয়ার্ড বা টোকেন মিল থাকলে বিবেচনায় নেওয়া
        title = (cand.get("title") or "").strip()
        desc = (cand.get("description") or "").strip()
        cand_text = title + " " + desc
        if any(kw.lower() in cand_text.lower() for kw in keywords if len(kw) > 2):
            seen_urls.add(cand["url"])
            candidate_matches.append(cand)

    # ২. অতিরিক্ত সোর্স খোঁজা (যদি সাইটের পুলে কম পাওয়া যায়)
    if len(candidate_matches) < min_sources + 2:
        queries_to_try = []
        if keywords:
            queries_to_try.append(keywords[0])
            words = [w for w in re.findall(r"[\w\u0980-\u09FF]+", chosen_story.get("headline", "")) if len(w) > 3 and w not in STOPWORDS]
            if len(words) >= 2:
                q2 = " ".join(words[:2])
                if q2 not in queries_to_try:
                    queries_to_try.append(q2)
            if len(keywords) > 1 and keywords[1] not in queries_to_try:
                queries_to_try.append(keywords[1])

        for q in queries_to_try:
            if len(candidate_matches) >= min_sources + 3:
                break
            print(f"   [ক্রস-সার্চ] অতিরিক্ত সোর্স খুঁজতে অনুসন্ধান চলছে: '{q}'...")
            bing_results = search_bing_news_general(q, max_items=8)
            for b_cand in bing_results:
                if b_cand["url"] not in seen_urls and b_cand.get("site") != primary_site:
                    seen_urls.add(b_cand["url"])
                    candidate_matches.append(b_cand)

    # ৩. ক্যান্ডিডেটদের পূর্ণাঙ্গ বডি ও ছবি enrich করা
    print(f"   [ক্রস-সার্চ] {len(candidate_matches)}টি সম্ভাব্য রিপোর্ট যাচাই ও enrich করা হচ্ছে...")
    enriched_matches = []
    for cand in candidate_matches:
        if not cand.get("body"):
            enrich_one(cand)
        enriched_matches.append(cand)

    return enriched_matches


def main():
    parser = argparse.ArgumentParser(description="Multi-Source Breaking News Collector")
    parser.add_argument("--out", default=os.path.join(BASE_DIR, "output"), help="আউটপুট ফোল্ডার")
    parser.add_argument("--min-sources", type=int, default=3, help="ন্যূনতম কতটি সোর্স সংগ্রহ করতে হবে")
    args = parser.parse_args()

    started = time.time()
    ai_picker.load_env()
    if not ai_picker.api_key():
        print("ত্রুটি: GROQ_API_KEY পাওয়া যায়নি। .env ফাইলে GROQ_API_KEY=gsk_... বসান।")
        sys.exit(1)

    # বাংলাদেশ সময় ও আজকের রান নম্বর নির্ধারণ
    date_label = datetime.now(DHAKA_TZ).strftime("%Y-%m-%d")
    run_id = get_today_run_count(date_label) + 1

    print("==================================================================")
    print(f"  AI Reels Creator — News Collector Agent (Agent 1)")
    print(f"  তারিখ: {date_label}  |  আজকের রান নং: #{run_id:02d}")
    print("==================================================================")

    # ওয়েবসাইট তালিকা লোড
    try:
        sites = parse_websites_doc()
    except Exception as exc:
        print(f"ওয়েবসাইট তালিকা পড়া যায়নি: {exc}")
        sys.exit(1)

    print(f"মোট সাইট: {len(sites)}টি | লক্ষ্য: আজকের শীর্ষ ব্রেকিং খবর + বহু-উৎস বিশ্লেষণ")

    # ধাপ ১: সব সাইট থেকে তাজা খবরের পুল সংগ্রহ
    all_candidates, pools_by_site = collect_all_candidates(sites, enrich_pool=4)
    if not all_candidates:
        print("কোনো খবর সংগ্রহ করা যায়নি। ইন্টারনেট সংযোগ বা ওয়েবসাইট স্ট্যাটাস পরীক্ষা করুন।")
        sys.exit(1)

    # ধাপ ২: আজকের পূর্বে কাভার না করা শীর্ষ ব্রেকিং খবর বাছাই
    print(f"\n[2/4] Groq AI দিয়ে আজকের শীর্ষ তাজা সংবাদ নির্বাচন করা হচ্ছে...")
    chosen_story = ai_picker.pick_breaking_story(all_candidates, date_label)
    print(f"\n🌟 নির্বাচিত ব্রেকিং সংবাদ:")
    print(f"   শিরোনাম : {chosen_story['headline']}")
    print(f"   সারসংক্ষেপ : {chosen_story['core_event']}")
    print(f"   অনুসন্ধান শব্দ : {', '.join(chosen_story.get('search_keywords', []))}")
    print(f"   প্রাথমিক উৎস   : {chosen_story['primary_candidate'].get('site', 'অজ্ঞাত')}")

    # ধাপ ৩: অন্যান্য সোর্স থেকে একই খবরের বিশ্লেষণ সংগ্রহ
    print(f"\n[3/4] বিভিন্ন সংবাদমাধ্যমে এই খবরের প্রতিক্রিয়া ও বিবরণ খোঁজা হচ্ছে...")
    matched_candidates = find_cross_source_coverage(
        chosen_story, all_candidates, min_sources=args.min_sources
    )

    overall_synthesis, verified_sources = ai_picker.match_and_synthesize_sources(
        chosen_story, matched_candidates
    )

    # নিশ্চিত করা যেন প্রাথমিক সোর্সটি তালিকায় থাকে
    primary_cand = chosen_story["primary_candidate"]
    primary_site_name = primary_cand.get("site", "প্রধান উৎস")
    if not any(s["site"] == primary_site_name for s in verified_sources):
        verified_sources.insert(0, {
            "site": primary_site_name,
            "title": primary_cand.get("title", chosen_story["headline"]),
            "url": primary_cand.get("url", ""),
            "published": primary_cand.get("published"),
            "img": primary_cand.get("img"),
            "og_image": primary_cand.get("og_image"),
            "extra_images": primary_cand.get("extra_images", []),
            "body": primary_cand.get("body") or primary_cand.get("description", ""),
            "angle": "মূল ঘটনা প্রতিবেদন",
            "key_points": [chosen_story["core_event"]],
        })

    print(f"\n   সফলভাবে {len(verified_sources)}টি সংবাদমাধ্যমের বিবরণ সমন্বয় করা হয়েছে:")
    for s in verified_sources:
        print(f"   - [{s['site']}] {s['title'][:60]}")

    # আউটপুট ডিরেক্টরি প্রস্তুতকরণ (তারিখ এবং রান অনুযায়ী সাজানো)
    run_dir = os.path.join(args.out, date_label, f"run_{run_id:02d}")
    images_dir = os.path.join(run_dir, "images")
    os.makedirs(images_dir, exist_ok=True)

    # ধাপ ৪: ছবি ডাউনলোড করা
    print(f"\n[4/4] সংবাদমাধ্যমগুলো থেকে ছবি ডাউনলোড করা হচ্ছে -> {images_dir}...")
    for idx, s in enumerate(verified_sources, start=1):
        s["number"] = idx
    download_images(verified_sources, images_dir)

    # ধাপ ৫: সমন্বিত ডকুমেন্ট (.docx) ও ডেটা (.json) তৈরি করা
    docx_name = f"news_{date_label}_run{run_id:02d}.docx"
    docx_path = os.path.join(run_dir, docx_name)
    json_path = os.path.join(run_dir, "story_data.json")

    story_data = {
        "run_id": run_id,
        "date": date_label,
        "headline": chosen_story["headline"],
        "core_event": chosen_story["core_event"],
        "overall_synthesis": overall_synthesis,
        "search_keywords": chosen_story.get("search_keywords", []),
        "primary_source": primary_site_name,
        "sources": verified_sources,
        "timestamp": datetime.now(DHAKA_TZ).isoformat(),
    }

    write_consolidated_report(story_data, docx_path, json_path)

    # লেটেস্ট রানে সহজে পাওয়ার জন্য কপি তৈরি
    latest_dir = os.path.join(args.out, "latest")
    os.makedirs(latest_dir, exist_ok=True)
    try:
        shutil.copy2(docx_path, os.path.join(latest_dir, f"news_{date_label}.docx"))
        shutil.copy2(json_path, os.path.join(latest_dir, "story_data.json"))
        latest_images_dir = os.path.join(latest_dir, "images")
        if os.path.exists(latest_images_dir):
            shutil.rmtree(latest_images_dir)
        shutil.copytree(images_dir, latest_images_dir)
    except Exception as exc:
        print(f"সতর্কতা: latest ফোল্ডারে কপি করতে সমস্যা ({exc})")

    # ধাপ ৬: history.json এ এই রান সেভ করা
    run_record = {
        "run_id": run_id,
        "timestamp": datetime.now(DHAKA_TZ).isoformat(),
        "headline": chosen_story["headline"],
        "topic": chosen_story["core_event"],
        "keywords": chosen_story.get("search_keywords", []),
        "sources": [s["site"] for s in verified_sources],
        "output_doc": docx_path,
        "output_json": json_path,
    }
    record_story(date_label, run_record)

    elapsed = round(time.time() - started, 1)
    print("\n==================================================================")
    print("✅ সংবাদ সংগ্রহ ও মাল্টি-সোর্স বিশ্লেষণ সম্পন্ন!")
    print(f"  মূল শিরোনাম : {chosen_story['headline']}")
    print(f"  মোট সোর্স   : {len(verified_sources)}টি সংবাদমাধ্যম")
    print(f"  ডকুমেন্ট    : {docx_path}")
    print(f"  JSON ডেটা   : {json_path}")
    print(f"  ছবি ফোল্ডার : {images_dir}")
    print(f"  মোট সময়     : {elapsed} সেকেন্ড")
    print("==================================================================")


if __name__ == "__main__":
    main()
