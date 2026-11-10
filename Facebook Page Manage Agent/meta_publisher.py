import os
import time
import requests

GRAPH_API_VERSION = "v19.0"
GRAPH_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


def check_api_credentials(page_id, access_token):
    """ফেসবুক পেজ ক্রেডেনশিয়াল কার্যকর কি না তা পরীক্ষা করে।"""
    if not page_id or not access_token:
        return False, "FB_PAGE_ID বা FB_PAGE_ACCESS_TOKEN সেট করা নেই।"
    try:
        url = f"{GRAPH_URL}/{page_id}?access_token={access_token}&fields=id,name"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            name = r.json().get("name", "Unknown Page")
            return True, f"সংযুক্ত পেজ: {name} (ID: {page_id})"
        else:
            return False, f"মেটা এপিআই ত্রুটি ({r.status_code}): {r.text[:200]}"
    except Exception as exc:
        return False, f"কানেকশন ত্রুটি: {exc}"


def publish_reel(page_id, access_token, video_path, caption="", cover_img_path=None, publish_mode="DIRECT", scheduled_time=None):
    """
    মেটা গ্রাফ এপিআই (Meta Reels Publishing API) দিয়ে রিল ভিডিও আপলোড করে।
    ধাপ ১: ইনিশিয়ালাইজেশন
    ধাপ ২: বাইনারি ভিডিও আপলোড
    ধাপ ৩: পাবলিশ রিকোয়েস্ট (DIRECT বা SCHEDULE)
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"ভিডিও পাওয়া যায়নি: {video_path}")

    file_size = os.path.getsize(video_path)
    print(f"      [1/3] মেটা রিল সেশন ইনিশিয়ালাইজ করা হচ্ছে...")
    init_url = f"{GRAPH_URL}/{page_id}/video_reels"
    init_payload = {
        "upload_phase": "start",
        "access_token": access_token,
    }
    r_init = requests.post(init_url, data=init_payload, timeout=20)
    if r_init.status_code != 200:
        raise RuntimeError(f"রিল সেশন শুরু ব্যর্থ ({r_init.status_code}): {r_init.text}")

    init_data = r_init.json()
    video_id = init_data.get("video_id")
    upload_url = init_data.get("upload_url")

    # ধাপ ২: ভিডিও আপলোড
    print(f"      [2/3] রিল ভিডিও বাইনারি ডাটা আপলোড হচ্ছে ({round(file_size / (1024*1024), 2)} MB)...")
    headers = {
        "Authorization": f"OAuth {access_token}",
        "offset": "0",
        "file_size": str(file_size),
    }
    with open(video_path, "rb") as f:
        r_upload = requests.post(upload_url, headers=headers, data=f, timeout=180)
    if r_upload.status_code not in (200, 201):
        raise RuntimeError(f"ভিডিও আপলোড ব্যর্থ ({r_upload.status_code}): {r_upload.text}")

    # ধাপ ৩: পাবলিশ
    print(f"      [3/3] রিল ভিডিও প্রসেসিং ও ফাইনাল পাবলিশ হচ্ছে...")
    finish_url = f"{GRAPH_URL}/{page_id}/video_reels"
    finish_payload = {
        "upload_phase": "finish",
        "access_token": access_token,
        "video_id": video_id,
        "description": caption,
    }
    
    if publish_mode.upper() == "SCHEDULE" and scheduled_time:
        finish_payload["video_state"] = "SCHEDULED"
        finish_payload["scheduled_publish_time"] = int(scheduled_time)
        print(f"         ⏰ ফেসবুক রিল শিডিউল করা হচ্ছে: {scheduled_time}")
    else:
        finish_payload["video_state"] = "PUBLISHED"

    r_finish = requests.post(finish_url, data=finish_payload, timeout=30)
    if r_finish.status_code not in (200, 201):
        raise RuntimeError(f"রিল পাবলিশ ব্যর্থ ({r_finish.status_code}): {r_finish.text}")

    return {
        "success": True,
        "video_id": video_id,
        "reel_url": f"https://www.facebook.com/reel/{video_id}",
    }


def post_first_comment(video_id, access_token, comment_text):
    """রিল ভিডিওর নিচে স্বয়ংক্রিয় পিন কমেন্ট বা ফার্স্ট কমেন্ট ড্রপ করে।"""
    try:
        url = f"{GRAPH_URL}/{video_id}/comments"
        payload = {
            "message": comment_text,
            "access_token": access_token,
        }
        res = requests.post(url, data=payload, timeout=15)
        if res.status_code in (200, 201):
            return res.json().get("id")
    except Exception:
        pass
    return None

