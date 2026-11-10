"""
Youtube Page Manage Agent — YouTube Data API v3 Uploader
==========================================================
YouTube Shorts আপলোড, description, tags, thumbnail সেট করা।
OAuth2 Refresh Token অথবা API Key দিয়ে কাজ করে।
"""

import json
import os
import time
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

YT_API_BASE = "https://www.googleapis.com/youtube/v3"
YT_UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
YT_TOKEN_URL = "https://oauth2.googleapis.com/token"


# ──────────────────────────────────────────────────────────────────────────────
# Token Management
# ──────────────────────────────────────────────────────────────────────────────
def get_access_token() -> str:
    """Refresh token দিয়ে নতুন access token নেয়।"""
    client_id     = os.environ.get("YT_CLIENT_ID", "")
    client_secret = os.environ.get("YT_CLIENT_SECRET", "")
    refresh_token = os.environ.get("YT_REFRESH_TOKEN", "")

    if not all([client_id, client_secret, refresh_token]):
        raise RuntimeError(
            "YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN — সবগুলো .env-এ সেট করুন।"
        )

    res = requests.post(YT_TOKEN_URL, data={
        "client_id":     client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type":    "refresh_token",
    }, timeout=15)

    if res.status_code != 200:
        raise RuntimeError(f"Token refresh ব্যর্থ ({res.status_code}): {res.text[:300]}")

    token = res.json().get("access_token")
    if not token:
        raise RuntimeError("access_token পাওয়া যায়নি।")
    return token


def check_credentials() -> tuple[bool, str]:
    """YouTube credentials পরীক্ষা করে।"""
    client_id     = os.environ.get("YT_CLIENT_ID", "").strip()
    client_secret = os.environ.get("YT_CLIENT_SECRET", "").strip()
    refresh_token = os.environ.get("YT_REFRESH_TOKEN", "").strip()

    if not all([client_id, client_secret, refresh_token]):
        return False, "YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN সেট করা নেই।"

    try:
        token = get_access_token()
        # Channel info check
        r = requests.get(
            f"{YT_API_BASE}/channels",
            params={"part": "snippet", "mine": "true"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        if r.status_code == 200:
            items = r.json().get("items", [])
            if items:
                name = items[0]["snippet"]["title"]
                return True, f"সংযুক্ত চ্যানেল: {name}"
            return True, "YouTube চ্যানেল সংযুক্ত (নাম পাওয়া যায়নি)"
        return False, f"YouTube API ত্রুটি ({r.status_code}): {r.text[:200]}"
    except Exception as exc:
        return False, f"কানেকশন ত্রুটি: {exc}"


# ──────────────────────────────────────────────────────────────────────────────
# Upload Shorts Video (Resumable Upload)
# ──────────────────────────────────────────────────────────────────────────────
def upload_shorts(
    video_path: str,
    title: str,
    description: str,
    tags: list,
    category_id: int = 25,
    privacy: str = "public",
    thumbnail_path: str = None,
    publish_at: str = None,
) -> dict:
    """
    YouTube Shorts রিজ্যুমেবল আপলোড (DIRECT বা SCHEDULE)।
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"ভিডিও পাওয়া যায়নি: {video_path}")

    file_size = os.path.getsize(video_path)
    access_token = get_access_token()

    # Privacy status mapping
    privacy_upper = privacy.upper()
    if privacy_upper == "SCHEDULE" and publish_at:
        status = "private"
    else:
        privacy_map = {"PUBLIC": "public", "UNLISTED": "unlisted", "PRIVATE": "private"}
        status = privacy_map.get(privacy_upper, "public")

    # YouTube Shorts: title-এ #Shorts যোগ
    if "#Shorts" not in title and "#shorts" not in title:
        title = title[:90] + " #Shorts" if len(title) > 90 else title + " #Shorts"

    status_obj = {
        "privacyStatus": status,
        "selfDeclaredMadeForKids": False,
    }
    if privacy_upper == "SCHEDULE" and publish_at:
        status_obj["publishAt"] = publish_at
        print(f"         ⏰ ইউটিউব শর্টস শিডিউল করা হচ্ছে: {publish_at}")

    metadata = {
        "snippet": {
            "title":       title,
            "description": description,
            "tags":        tags,
            "categoryId":  str(category_id),
        },
        "status": status_obj,
    }

    # ধাপ ১: Session init
    print(f"      [1/3] YouTube Shorts আপলোড সেশন শুরু হচ্ছে...")
    init_headers = {
        "Authorization":           f"Bearer {access_token}",
        "Content-Type":            "application/json; charset=UTF-8",
        "X-Upload-Content-Type":   "video/*",
        "X-Upload-Content-Length": str(file_size),
    }
    r_init = requests.post(
        YT_UPLOAD_URL,
        params={"uploadType": "resumable", "part": "snippet,status"},
        headers=init_headers,
        json=metadata,
        timeout=30,
    )
    if r_init.status_code not in (200, 201):
        raise RuntimeError(f"Session init ব্যর্থ ({r_init.status_code}): {r_init.text[:300]}")

    upload_url = r_init.headers.get("Location")
    if not upload_url:
        raise RuntimeError("Upload URL পাওয়া যায়নি।")

    # ধাপ ২: ভিডিও আপলোড
    print(f"      [2/3] ভিডিও আপলোড হচ্ছে ({round(file_size / (1024*1024), 2)} MB)...")
    with open(video_path, "rb") as f:
        r_upload = requests.put(
            upload_url,
            headers={
                "Content-Type":   "video/*",
                "Content-Length": str(file_size),
            },
            data=f,
            timeout=300,
        )

    if r_upload.status_code not in (200, 201):
        raise RuntimeError(f"ভিডিও আপলোড ব্যর্থ ({r_upload.status_code}): {r_upload.text[:300]}")

    video_data = r_upload.json()
    video_id   = video_data.get("id")
    video_url  = f"https://www.youtube.com/shorts/{video_id}"

    # ধাপ ৩: Thumbnail সেট (optional)
    if thumbnail_path and os.path.exists(thumbnail_path) and video_id:
        print(f"      [3/3] থাম্বনেইল সেট হচ্ছে...")
        with open(thumbnail_path, "rb") as tf:
            r_thumb = requests.post(
                f"{YT_API_BASE}/thumbnails/set",
                params={"videoId": video_id},
                headers={"Authorization": f"Bearer {access_token}"},
                files={"thumbnail": tf},
                timeout=30,
            )
        if r_thumb.status_code in (200, 201):
            print("         ✅ থাম্বনেইল সেট সম্পন্ন")
        else:
            print(f"         ⚠️  থাম্বনেইল সেট ব্যর্থ ({r_thumb.status_code})")
    else:
        print(f"      [3/3] থাম্বনেইল: স্কিপ (ফাইল নেই বা video_id নেই)")

    return {
        "success":   True,
        "video_id":  video_id,
        "video_url": video_url,
        "shorts_url": f"https://www.youtube.com/shorts/{video_id}",
    }


# ──────────────────────────────────────────────────────────────────────────────
# Post Pinned Comment
# ──────────────────────────────────────────────────────────────────────────────
def post_pinned_comment(video_id: str, comment_text: str) -> str | None:
    """ভিডিওতে পিন করা কমেন্ট পোস্ট করে।"""
    try:
        access_token = get_access_token()
        # কমেন্ট পোস্ট
        r = requests.post(
            f"{YT_API_BASE}/commentThreads",
            params={"part": "snippet"},
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            json={
                "snippet": {
                    "videoId": video_id,
                    "topLevelComment": {
                        "snippet": {"textOriginal": comment_text}
                    }
                }
            },
            timeout=15,
        )
        if r.status_code in (200, 201):
            comment_id = r.json().get("id")
            return comment_id
    except Exception as exc:
        print(f"         ⚠️  Comment post ত্রুটি: {exc}")
    return None

