import re
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

from bs4 import BeautifulSoup

from fetcher import fetch
from sites import EXCLUDE_PATH_WORDS

MAX_CANDIDATES = 25
ENRICH_POOL = 6


BENGALI_DIGITS = "০১২৩৪৫৬৭৮৯"


def _split_glued(title):
    for marker in ("। ", ". "):
        pos = title.find(marker)
        if pos >= 25 and len(title) - pos > 25:
            return title[:pos].strip()
    return title


def _clean_title(title, site_name=""):
    title = re.sub(r"\s+", " ", title or "").strip()
    if site_name:
        title = re.sub(r"^\s*" + re.escape(site_name) + r"\s*[\|–—-]?\s*", "", title, flags=re.I)
        title = re.sub(r"\s*[\|–—-]\s*" + re.escape(site_name) + r"\s*$", "", title, flags=re.I)
    title = re.sub(r"\s*\|\|.*$", "", title)
    title = re.sub(r"^[\d" + BENGALI_DIGITS + r"]{1,3}[\.।\)]+\s+", "", title)
    title = title.strip(" |-\t\n")
    if len(title) > 120:
        title = _split_glued(title)
    if len(title) > 160:
        title = title[:157].rstrip() + "..."
    return title


def _blocked(path):
    low = path.lower()
    return any(word in low for word in EXCLUDE_PATH_WORDS)


def parse_rss(text, site_name):
    soup = BeautifulSoup(text, "lxml-xml")
    items = soup.find_all("item") or soup.find_all("entry")
    out = []
    for it in items:
        link = it.find("link")
        url = None
        if link is not None:
            url = link.get("href") or link.get_text(strip=True)
        if not url:
            continue
        title_tag = it.find("title")
        title = _clean_title(title_tag.get_text(" ", strip=True) if title_tag else "", site_name)
        if len(title) < 10:
            continue
        img = None
        for tag in ("media:content", "media:thumbnail", "enclosure"):
            node = it.find(tag)
            if node and node.get("url") and re.search(r"\.(jpg|jpeg|png|webp)(\?|$)", node.get("url", ""), re.I):
                img = node.get("url")
                break
        if not img:
            desc = it.find("description")
            if desc:
                m = re.search(r'<img[^>]+(?:src|data-src)=["\']([^"\']+)', str(desc))
                if m:
                    img = m.group(1)
        pub = None
        for tag in ("pubDate", "published", "updated", "dc:date"):
            node = it.find(tag)
            if node:
                pub = node.get_text(strip=True)
                break
        out.append({"title": title, "url": url, "img": img, "published": pub})
    return out


def _anchor_title(anchor, site_name):
    for tag in ("h1", "h2", "h3", "h4", "h5", "strong", "b", "p"):
        node = anchor.find(tag)
        if node:
            text = _clean_title(node.get_text(" ", strip=True), site_name)
            if len(text) >= 12:
                return text
    for node in anchor.find_all(["span", "div"]):
        text = _clean_title(node.get_text(" ", strip=True), site_name)
        if len(text) >= 12:
            return text
    chunks = list(anchor.stripped_strings)
    if chunks and re.fullmatch(r"[\d" + BENGALI_DIGITS + r"]{1,3}[\.।\)]?", chunks[0].strip()):
        chunks = chunks[1:]
    for chunk in chunks:
        text = _clean_title(chunk, site_name)
        if len(text) >= 12:
            return text
    text = _clean_title(anchor.get_text(" ", strip=True), site_name)
    if len(text) >= 12:
        return _split_glued(text) if len(text) > 120 else text
    return ""


def _img_src(image, base_url):
    if not image:
        return None
    raw = (image.get("src") or image.get("data-src") or
           image.get("data-original") or image.get("data-lazy-src"))
    if not raw or raw.startswith("data:"):
        srcset = image.get("srcset") or image.get("data-srcset")
        if srcset:
            raw = srcset.split(",")[0].strip().split(" ")[0]
    if not raw or raw.startswith("data:"):
        picture = image.find_parent("picture")
        if picture:
            source = picture.find("source")
            if source and source.get("srcset"):
                raw = source["srcset"].split(",")[0].strip().split(" ")[0]
    if not raw or raw.startswith("data:"):
        return None
    return urllib.parse.urljoin(base_url, raw)


def _img_url(node, base_url):
    return _img_src(node.find("img"), base_url)


def _container(anchor):
    node = anchor
    for _ in range(4):
        node = node.parent
        if node is None or node.name in ("body", "html"):
            return None
        if node.find(["h1", "h2", "h3", "h4", "h5", "h6"]) and len(node.get_text(" ", strip=True)) <= 1500:
            return node
    return None


def _heading_title(container, site_name):
    for tag in ("h1", "h2", "h3", "h4", "h5", "h6", "strong"):
        node = container.find(tag)
        if node:
            text = _clean_title(node.get_text(" ", strip=True), site_name)
            if len(text) >= 12:
                return text
    return ""


def _summary(container):
    paragraph = container.find("p")
    if paragraph:
        text = re.sub(r"\s+", " ", paragraph.get_text(" ", strip=True))
        if len(text) >= 40 and not re.search(r"\d{1,2}[:.]\d{2}", text[:20]):
            return text[:400]
    return None


def parse_home(text, page_url, site_name, pattern=None):
    soup = BeautifulSoup(text, "lxml")
    page = urllib.parse.urlparse(page_url)
    host = page.netloc.replace("www.", "")
    seen, out = set(), []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("javascript:", "mailto:", "#")):
            continue
        absu = urllib.parse.urljoin(page_url, href)
        parsed = urllib.parse.urlparse(absu)
        if host not in parsed.netloc.replace("www.", ""):
            continue
        path = parsed.path.rstrip("/")
        if not path or path == "/" or _blocked(path):
            continue
        if pattern and not re.search(pattern, path):
            continue
        if not pattern and (path.count("/") < 1 or not re.search(r"\d", path)):
            continue
        key = parsed._replace(query="", fragment="").geturl()
        if key in seen:
            continue
        title = _anchor_title(a, site_name)
        img = _img_url(a, page_url)
        description = None
        if not title or not img:
            container = _container(a)
            if container is not None:
                if not title:
                    title = _heading_title(container, site_name)
                if not img:
                    img = _img_url(container, page_url)
                if not description:
                    description = _summary(container)
        if not title and a.get("title"):
            title = _clean_title(a.get("title"), site_name)
        if not title and not img:
            continue
        seen.add(key)
        out.append({"title": title, "url": key, "img": img,
                    "published": None, "description": description})
    return out


def parse_bing(text, host):
    soup = BeautifulSoup(text, "lxml")
    out = []
    for card in soup.select("div.newsitem, .newsitem, div[class*=newscard]"):
        anchor = card.find("a", href=True)
        if not anchor:
            continue
        url = anchor["href"]
        netloc = urllib.parse.urlparse(url).netloc.replace("www.", "").lower()
        if netloc != host and not netloc.endswith("." + host):
            continue
        title_node = card.select_one("a.title") or anchor
        title = _clean_title(title_node.get_text(" ", strip=True))
        if len(title) < 10:
            continue
        img = _img_src(card.find("img"), "https://www.bing.com")
        if not img:
            img = _img_src(anchor.find("img"), "https://www.bing.com")
        if img:
            img = re.sub(r"\bw=\d+", "w=1200", img)
            img = re.sub(r"\bh=\d+", "h=675", img)
        out.append({"title": title, "url": url, "img": img, "published": None})
    return out


def collect_candidates(site):
    strategy = site["strategy"]
    kind = strategy.get("kind", "home")
    name = site["name"]
    candidates = []
    try:
        if kind == "rss":
            for feed in strategy.get("feeds", []):
                result = fetch(feed)
                if result.status == 200:
                    candidates = parse_rss(result.text, name)
                    if candidates:
                        break
        elif kind == "bing":
            query = urllib.parse.quote(f"site:{site['host']}")
            url = f"https://www.bing.com/news/search?q={query}&FORM=HDRSC6"
            result = fetch(url)
            if result.status == 200:
                candidates = parse_bing(result.text, site["host"])
        else:
            result = fetch(strategy.get("home", site["url"]))
            if result.status == 200:
                candidates = parse_home(result.text, strategy.get("home", site["url"]),
                                        name, strategy.get("pattern"))
    except Exception as exc:
        print(f"    collect error [{name}]: {type(exc).__name__}: {exc}")

    if not candidates and kind == "rss":
        try:
            result = fetch(site["url"])
            if result.status == 200:
                candidates = parse_home(result.text, site["url"], name, None)
        except Exception:
            pass

    deduped, seen_urls, seen_titles = [], set(), set()
    for cand in candidates:
        if cand["url"] in seen_urls:
            continue
        title_key = (cand.get("title") or "").strip().lower()
        if title_key and title_key in seen_titles:
            continue
        seen_urls.add(cand["url"])
        if title_key:
            seen_titles.add(title_key)
        deduped.append(cand)
        if len(deduped) >= MAX_CANDIDATES:
            break
    return deduped


def search_bing_news_general(query, max_items=15):
    encoded = urllib.parse.quote(query)
    url = f"https://www.bing.com/news/search?q={encoded}&FORM=HDRSC6"
    result = fetch(url)
    if result.status != 200:
        return []
    soup = BeautifulSoup(result.text, "lxml")
    cards = soup.select("div.newsitem, .newsitem, div[class*=newscard], div.news-card")
    out = []
    seen = set()
    for card in cards:
        anchor = card.find("a", href=True)
        if not anchor:
            continue
        href = anchor["href"]
        if not href.startswith("http") or "bing.com" in href or href in seen:
            continue
        seen.add(href)

        source_tag = card.select_one("div.source, .source, a.source, [class*=source]")
        source_name = source_tag.get_text(strip=True) if source_tag else ""
        # '7h', '2d' বা সময়ের অংশ বাদ দেওয়া
        source_name = re.sub(r"\d+[hmsd]$|\d+\s*(ঘণ্টা|মিনিট|দিন|ঘন্টা).*$", "", source_name).strip()
        if not source_name:
            source_name = urllib.parse.urlparse(href).netloc.replace("www.", "").split(".")[0].title()

        title_node = card.select_one("a.title, .title") or anchor
        title = _clean_title(title_node.get_text(" ", strip=True))
        if len(title) < 10:
            continue

        snippet_node = card.select_one("div.snippet, .snippet")
        snippet = snippet_node.get_text(" ", strip=True) if snippet_node else ""

        img = _img_src(card.find("img"), "https://www.bing.com")
        if img:
            img = re.sub(r"\bw=\d+", "w=1200", img)
            img = re.sub(r"\bh=\d+", "h=675", img)

        out.append({
            "title": title,
            "url": href,
            "site": source_name,
            "description": snippet,
            "img": img,
            "published": None
        })
        if len(out) >= max_items:
            break
    return out


def enrich_one(candidate):
    try:
        result = fetch(candidate["url"], timeout=25)
        if result.status != 200:
            print(f"[enrich] {candidate['url']}: HTTP {result.status}"
                  f"{' — ' + result.error if result.error else ''}", file=sys.stderr)
            return candidate
        soup = BeautifulSoup(result.text, "lxml")

        def meta(*names, prop=None):
            node = soup.find("meta", attrs={"property": prop}) if prop else None
            for n in names:
                if node:
                    break
                node = soup.find("meta", attrs={"name": n}) or soup.find("meta", attrs={"itemprop": n})
            if node and node.get("content"):
                return node["content"].strip()
            return None

        image = meta(prop="og:image") or meta("og:image", "twitter:image", "image")
        if image:
            image = urllib.parse.urljoin(candidate["url"], image)
        description = meta(prop="og:description") or meta("description", "og:description", "twitter:description")
        og_title = meta(prop="og:title") or meta("og:title")
        published = meta(prop="article:published_time") or meta("article:published_time", "date")
        if image and not candidate.get("img"):
            candidate["img"] = image
        candidate["og_image"] = image
        parsed_summary = candidate.get("description")
        candidate["description"] = parsed_summary or re.sub(r"\s+", " ", description or "")[:400] or None
        candidate["og_title"] = _clean_title(og_title or "", "") or None
        candidate["published"] = candidate.get("published") or published
        if len((candidate.get("title") or "").strip()) < 12 and candidate["og_title"]:
            brand = urllib.parse.urlparse(candidate["url"]).netloc.replace("www.", "").split(".")[0].lower()
            cleaned = candidate["og_title"]
            if len(cleaned) >= 12 and brand not in cleaned.lower():
                candidate["title"] = cleaned

        # মূল খবরের প্যারাগ্রাফ (Body content) এক্সট্র্যাক্ট করা
        article_container = (
            soup.find("article")
            or soup.find(class_=re.compile(r"story-element|content|details|story-detail|jw_detail_content|article-content|news-details|news_content", re.I))
            or soup
        )
        body_paras = []
        for p in article_container.find_all("p"):
            p_text = re.sub(r"\s+", " ", p.get_text(strip=True))
            if len(p_text) > 30 and not any(bad in p_text.lower() for bad in ["advertisement", "বিজ্ঞাপন", "কপিরাইট", "সব অধিকার"]):
                # সাধারণ তারিখ বা ক্রেডিট লাইন বাদ দেওয়া
                if not re.match(r"^(প্রিন্ট|প্রকাশ|আপডেট|ছবি|প্রতিবেদক|বিশেষ সংবাদদাতা|অনলাইন ডেস্ক)[:\s]", p_text):
                    body_paras.append(p_text)
            if len(body_paras) >= 8:
                break
        candidate["body"] = "\n\n".join(body_paras[:6]) if body_paras else candidate.get("description", "")
        candidate["paragraphs"] = body_paras[:6]

        # অতিরিক্ত ইন-আর্টিকেল ছবি খোঁজা
        extra_imgs = []
        for img_tag in article_container.find_all("img"):
            src = img_tag.get("src") or img_tag.get("data-src") or img_tag.get("data-original")
            if src and not src.startswith("data:"):
                full_img = urllib.parse.urljoin(candidate["url"], src)
                if any(ext in full_img.lower() for ext in [".jpg", ".jpeg", ".png", ".webp"]) and not any(bad in full_img.lower() for bad in ["logo", "icon", "avatar", "ad-", "banner", "1x1"]):
                    if full_img != candidate.get("img") and full_img not in extra_imgs:
                        extra_imgs.append(full_img)
            if len(extra_imgs) >= 3:
                break
        candidate["extra_images"] = extra_imgs

    except Exception as exc:
        print(f"[enrich] {candidate.get('url', '?')}: {type(exc).__name__}: {exc}", file=sys.stderr)
    return candidate


def enrich_candidates(candidates, pool=ENRICH_POOL):
    with ThreadPoolExecutor(max_workers=4) as pool_exec:
        list(pool_exec.map(enrich_one, candidates[:pool]))
    retried = 0
    for cand in candidates:
        if len((cand.get("title") or "").strip()) >= 12 or retried >= 5:
            continue
        enrich_one(cand)
        retried += 1
    kept = [c for c in candidates if len((c.get("title") or "").strip()) >= 12]
    dropped = len(candidates) - len(kept)
    if dropped:
        print(f"      শিরোনাম না পাওয়ায় {dropped}টি লিংক বাদ পড়েছে")
    return kept
