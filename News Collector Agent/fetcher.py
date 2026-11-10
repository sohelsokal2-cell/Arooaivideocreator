import sys
import time

import requests
from curl_cffi import requests as curl_requests

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,bn;q=0.8",
}

IMPERSONATIONS = ["chrome", "chrome131", "chrome124", "safari17_0", "firefox133"]

BAD_STATUSES = {403, 429, 500, 502, 503, 504, 520, 521, 522, 523, 524}


class FetchResult:
    def __init__(self, status, content, final_url, content_type="", encoding=None, error=None):
        self.status = status
        self.content = content
        self.url = final_url
        self.content_type = content_type
        self.encoding = encoding
        self.error = error

    @property
    def text(self):
        if isinstance(self.content, bytes):
            # ঘোষিত charset কে সম্মান করা হয়; না থাকলে UTF-8।
            # errors="ignore" বাদ — ভুল মোজাইক সাইলেন্টলি গিলে নেয়।
            enc = self.encoding or "utf-8"
            try:
                return self.content.decode(enc)
            except (UnicodeDecodeError, LookupError):
                return self.content.decode("utf-8", errors="replace")
        return self.content


def _plain(url, timeout, stream=False):
    r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True, stream=stream)
    if stream:
        return r
    enc = r.encoding
    if not enc or enc.lower() == "iso-8859-1":
        # requests-এর কাছে সরাসরি charset না থাকলে apparent থেকে আনা (chardet)
        enc = r.apparent_encoding or enc
    return FetchResult(r.status_code, r.content, r.url, r.headers.get("content-type", ""), enc)


def fetch(url, timeout=25, retries=True):
    last = None
    for attempt in range(2 if retries else 1):
        try:
            result = _plain(url, timeout)
            if result.status == 200:
                return result
            last = result
        except Exception as exc:
            last = exc
        for imp in IMPERSONATIONS:
            try:
                r = curl_requests.get(url, impersonate=imp, timeout=timeout, headers=HEADERS)
                if r.status_code == 200:
                    return FetchResult(r.status_code, r.content, r.url,
                                       r.headers.get("content-type", ""), r.encoding)
                last = FetchResult(r.status_code, r.content, r.url,
                                   r.headers.get("content-type", ""), r.encoding)
            except Exception as exc:
                last = exc
        # শেষ attempt-এর পর অপেক্ষা করা হয় না
        if attempt == (2 if retries else 1) - 1:
            break
        time.sleep(1.5 * (attempt + 1))
    if isinstance(last, FetchResult):
        if last.status != 200:
            last.error = f"HTTP {last.status}"
        return last
    msg = f"{type(last).__name__}: {last}" if last else "সব ফেচ প্রচেষ্টা ব্যর্থ"
    # আগে এই ত্রুটি content_type-এ ঢুকিয়ে কোথাও ব্যবহার করা হতো না — আউটেজ চাপা পড়তো।
    print(f"[fetch] ব্যর্থ: {url} — {msg}", file=sys.stderr)
    return FetchResult(0, b"", url, error=msg)


def fetch_bytes(url, timeout=30):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True, stream=True)
        if r.status_code == 200:
            data = r.content
            if data:
                return data, r.headers.get("content-type", "")
    except Exception:
        pass
    for imp in IMPERSONATIONS[:3]:
        try:
            r = curl_requests.get(url, impersonate=imp, timeout=timeout, headers=HEADERS)
            if r.status_code == 200 and r.content:
                return r.content, r.headers.get("content-type", "")
        except Exception:
            continue
    return b"", ""
