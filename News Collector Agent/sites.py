import os
import re
from urllib.parse import urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEBSITES_DOC = os.path.join(BASE_DIR, "bangladesh_newspaper_websites.doc")

STRATEGIES = {
    "prothomalo.com": {"kind": "rss", "feeds": ["https://www.prothomalo.com/feed"]},
    "bd-pratidin.com": {"kind": "home", "pattern": r"/20\d{2}/\d{2}/\d{2}/\d+$"},
    "jugantor.com": {"kind": "home", "pattern": r"^/[a-z\-]+/\d+$"},
    "kalerkantho.com": {"kind": "home", "pattern": r"/20\d{2}/\d{2}/\d{2}/\d+$"},
    "thedailystar.net": {"kind": "home", "pattern": r"/news-\d+$"},
    "bangla.thedailystar.net": {"kind": "home", "pattern": r"/news-\d+$"},
    "bdnews24.com": {"kind": "home", "pattern": r"^/[a-z\-]+/[a-z0-9]{8,}$"},
    "bangla.bdnews24.com": {"kind": "home", "pattern": r"^/[a-z\-]+/[a-z0-9]{8,}$"},
    "jagonews24.com": {"kind": "home", "pattern": r"/(news|\d{4,})/\d+$"},
    "banglatribune.com": {"kind": "home", "pattern": r"/\d{4,}/[^/]+$"},
    "ittefaq.com.bd": {"kind": "home", "pattern": r"^/\d{5,}/"},
    "samakal.com": {"kind": "rss", "feeds": ["https://samakal.com/rss"]},
}

DEFAULT_STRATEGY = {"kind": "home", "pattern": r"^/.+/.+"}

EXCLUDE_PATH_WORDS = [
    "topic", "category", "author", "tag", "page", "video", "photo", "gallery",
    "epaper", "about", "contact", "privacy", "policy", "login", "register",
    "search", "facebook", "twitter", "youtube", "instagram", "whatsapp",
    "rss", "sitemap", "poll", "advertisement", "advertisement-request", "node", "tube",
]


def parse_websites_doc(path=WEBSITES_DOC):
    if not os.path.exists(path):
        raise FileNotFoundError(f"websites list not found: {path}")
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        text = fh.read()
    sites = []
    for line in text.splitlines():
        m = re.search(r"^\s*\d+\.\s*([^:]+):\s*(https?://\S+)", line)
        if not m:
            continue
        name = m.group(1).strip()
        url = m.group(2).strip().rstrip("/")
        host = urlparse(url).netloc.replace("www.", "")

        # Auto-normalize to Bangla editions for Bengali news coverage
        if host == "thedailystar.net":
            url = "https://bangla.thedailystar.net"
            host = "bangla.thedailystar.net"
        elif host == "bdnews24.com":
            url = "https://bangla.bdnews24.com"
            host = "bangla.bdnews24.com"

        strategy = STRATEGIES.get(host)
        if strategy is None:
            for key, value in STRATEGIES.items():
                if host.endswith(key):
                    strategy = value
                    break
        strategy = dict(strategy or DEFAULT_STRATEGY)
        strategy.setdefault("feeds", [])
        if url + "/" not in strategy["feeds"] and strategy["kind"] == "home":
            strategy["home"] = url + "/"
        sites.append({"name": name, "url": url + "/", "host": host, "strategy": strategy})
    return sites


if __name__ == "__main__":
    for s in parse_websites_doc():
        print(f"{s['name']:22} {s['url']:40} {s['strategy']['kind']}")
