import io
import os
import re
import time
import urllib.parse

from PIL import Image, ImageDraw

from fetcher import fetch_bytes


def _save_jpeg(data, path, quality=88):
    image = Image.open(io.BytesIO(data))
    if image.mode in ("RGBA", "P", "LA"):
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.convert("RGBA").split()[-1])
        image = background
    else:
        image = image.convert("RGB")
    if max(image.size) > 1400:
        image.thumbnail((1400, 1400))
    image.save(path, "JPEG", quality=quality)
    return path


def _placeholder(path, label):
    image = Image.new("RGB", (800, 450), (238, 240, 243))
    draw = ImageDraw.Draw(image)
    draw.rectangle([8, 8, 791, 441], outline=(180, 186, 194), width=3)
    draw.text((40, 195), "Image not available", fill=(90, 96, 105))
    draw.text((40, 235), label[:60], fill=(130, 136, 145))
    image.save(path, "JPEG", quality=85)
    return path


def _normalize_img_url(url, base_url=""):
    if not url:
        return ""
    u = str(url).strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("/") and base_url:
        return urllib.parse.urljoin(base_url, u)
    return u


def _candidate_urls(item):
    base_url = item.get("url") or ""
    raw_list = [item.get("og_image"), item.get("img"), item.get("fallback_img")] + item.get("extra_images", [])
    raw_urls = filter(None, raw_list)
    urls = []
    for raw in raw_urls:
        norm = _normalize_img_url(raw, base_url)
        if norm and norm.startswith("http"):
            urls.append(norm)
        if "bing.com/th?id=" in norm:
            for width, height in ((640, 360), (234, 132)):
                variant = re.sub(r"\bw=\d+", f"w={width}", norm)
                variant = re.sub(r"\bh=\d+", f"h={height}", variant)
                if variant not in urls:
                    urls.append(variant)
    seen = []
    for url in urls:
        if url not in seen:
            seen.append(url)
    return seen


def _try_save(urls, path):
    for url in urls:
        data, _ = fetch_bytes(url)
        if not data:
            continue
        try:
            _save_jpeg(data, path)
            return url
        except Exception:
            continue
    return None


def download_images(news_list, images_dir):
    os.makedirs(images_dir, exist_ok=True)
    for item in news_list:
        number = item["number"]
        filename = f"news_{number:02d}.jpg"
        path = os.path.join(images_dir, filename)
        source = _try_save(_candidate_urls(item), path)

        if not source and item.get("url"):
            from scraper import enrich_one
            enrich_one(item)
            source = _try_save(_candidate_urls(item), path)

        if source:
            item["image_path"] = path
            item["image_source"] = source
        else:
            _placeholder(path, f"{item['site']} - news {number:02d}")
            item["image_path"] = path
            item["image_source"] = None
        print(f"    image {number:02d} -> {filename}"
              f"{' (placeholder)' if not item.get('image_source') else ''}")
    return news_list
