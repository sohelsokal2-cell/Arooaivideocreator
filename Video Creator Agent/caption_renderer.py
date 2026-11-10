import os
import re
import sys
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
)
from PyQt6.QtWidgets import QApplication

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
FONT_PATH = os.path.join(PROJECT_DIR, "Image Editor Agent", "fonts", "AnekBangla-Bold.ttf")

_APP = QApplication.instance() or QApplication(sys.argv)
FONT_FAMILY = "Anek Bangla"
if os.path.exists(FONT_PATH):
    f_id = QFontDatabase.addApplicationFont(FONT_PATH)
    fams = QFontDatabase.applicationFontFamilies(f_id)
    if fams:
        FONT_FAMILY = fams[0]


def chunk_text_for_captions(text, target_words_per_chunk=3):
    """
    বাংলা বাক্যকে ২-৩ শব্দের স্পষ্ট ও দ্রুত পঠনযোগ্য চাঙ্কে ভাগ করে।
    """
    clean_text = re.sub(r"\s+", " ", text or "").strip()
    words = clean_text.split()
    if not words:
        return []

    chunks = []
    curr = []
    for w in words:
        curr.append(w)
        # যতিচিহ্ন পেলে বা ৩টি শব্দ হলে নতুন চাঙ্ক
        if len(curr) >= target_words_per_chunk or any(w.endswith(p) for p in ["।", "?", "!", ","]):
            chunks.append(" ".join(curr))
            curr = []

    if curr:
        chunks.append(" ".join(curr))

    return chunks


def render_caption_pill(phrase_text, out_path):
    """
    ১০৮০ x ১৯২০ ক্যানভাসে আধুনিক ডায়নামিক ক্যাপশন পিল রেন্ডার করে।
    """
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    canvas = QImage(1080, 1920, QImage.Format.Format_ARGB32)
    canvas.fill(QColor(0, 0, 0, 0))

    p = QPainter(canvas)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

    pill_w = 880
    pill_h = 100
    pill_x = (1080 - pill_w) // 2
    pill_y = 1380

    # সফট ড্রপ শ্যাডো
    s_path = QPainterPath()
    s_path.addRoundedRect(QRectF(pill_x - 4, pill_y - 2, pill_w + 8, pill_h + 8), 24, 24)
    p.fillPath(s_path, QColor(0, 0, 0, 180))

    # ডার্ক গ্লাস পিল ব্যাকগ্রাউন্ড
    p_path = QPainterPath()
    p_path.addRoundedRect(QRectF(pill_x, pill_y, pill_w, pill_h), 22, 22)
    p.fillPath(p_path, QColor(10, 5, 8, 240))
    # গোল্ডেন বর্ডার
    p.setPen(QPen(QColor(245, 185, 60, 220), 2))
    p.drawPath(p_path)

    # বোল্ড ইয়োলো বাংলা টেক্সট (Anek Bangla Bold) - বড় ও স্পষ্ট লেটার স্পেসিং
    font = QFont(FONT_FAMILY, 36, QFont.Weight.Bold)
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.5)
    p.setFont(font)
    p.setPen(QColor(255, 230, 40))
    p.drawText(
        QRectF(pill_x + 20, pill_y, pill_w - 40, pill_h),
        Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
        phrase_text,
    )

    p.end()
    canvas.save(out_path)
    return out_path


def generate_scene_caption_overlays(scene_text, duration_sec, temp_dir, scene_num):
    """
    একটি দৃশ্যের জন্য সময়ানুযায়ী ক্যাপশন ওভারলে ফাইল ও টাইমস্ট্যাম্প তৈরি করে।
    """
    chunks = chunk_text_for_captions(scene_text)
    if not chunks:
        return []

    total_words = sum(len(c.split()) for c in chunks)
    overlays = []
    curr_t = 0.0

    for idx, chunk in enumerate(chunks, start=1):
        w_count = len(chunk.split())
        # শব্দের সংখ্যা অনুপাতে সময় নির্ধারণ
        chunk_dur = (w_count / total_words) * duration_sec
        end_t = min(curr_t + chunk_dur, duration_sec)

        pill_filename = f"cap_scene_{scene_num:02d}_chunk_{idx:02d}.png"
        pill_path = os.path.join(temp_dir, pill_filename)
        render_caption_pill(chunk, pill_path)

        overlays.append({
            "image_path": pill_path,
            "start": round(curr_t, 2),
            "end": round(end_t, 2),
            "text": chunk,
        })
        curr_t = end_t

    # শেষ চাঙ্ক যাতে দৃশ্যের শেষ পর্যন্ত থাকে
    if overlays:
        overlays[-1]["end"] = round(duration_sec, 2)

    return overlays
