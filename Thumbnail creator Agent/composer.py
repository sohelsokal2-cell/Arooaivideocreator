import os
import sys
from PIL import Image, ImageFilter
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import (
    QBrush,
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
IMAGE_EDITOR_DIR = os.path.join(os.path.dirname(BASE_DIR), "Image Editor Agent")
FONTS_DIR = os.path.join(IMAGE_EDITOR_DIR, "fonts")
LOGO_PATH = os.path.join(IMAGE_EDITOR_DIR, "assets", "logo.jpg")

_APP = QApplication.instance() or QApplication(sys.argv)

FONT_FAMILY = "Anek Bangla"
for f_name in ["AnekBangla-Bold.ttf", "NotoSansBengali-Bold.ttf", "HindSiliguri-Bold.ttf"]:
    f_path = os.path.join(FONTS_DIR, f_name)
    if os.path.exists(f_path):
        f_id = QFontDatabase.addApplicationFont(f_path)
        fams = QFontDatabase.applicationFontFamilies(f_id)
        if fams and "Anek" in fams[0]:
            FONT_FAMILY = fams[0]

# রেফারেন্স ইমেজের হুবহু এক্সাক্ট কালার প্যালেট
COLOR_CARD_BG = QColor(250, 245, 246)       # সফ্ট ক্রিম/হোয়াইট ব্যাকগ্রাউন্ড
COLOR_CARD_BORDER = QColor(235, 218, 222)   # সূক্ষ্ম বর্ডার
COLOR_ACCENT = QColor(136, 19, 32)          # ডিপ মেরুন অ্যাকসেন্ট (কোণা ও ব্যাজ)
COLOR_TEXT_MAIN = QColor(122, 18, 29)       # গাঢ় মেরুন হেডলাইন
COLOR_TEXT_MUTED = QColor(140, 80, 90)      # নরম হ্যান্ডেল টেক্সট


def pil_to_qimage(pil_img):
    img_rgb = pil_img.convert("RGBA")
    data = img_rgb.tobytes("raw", "RGBA")
    qimg = QImage(data, pil_img.width, pil_img.height, QImage.Format.Format_RGBA8888)
    return qimg.copy()


def qimage_to_pil(qimg):
    qimg = qimg.convertToFormat(QImage.Format.Format_RGBA8888)
    width = qimg.width()
    height = qimg.height()
    ptr = qimg.constBits()
    ptr.setsize(height * width * 4)
    arr = bytes(ptr)
    return Image.frombytes("RGBA", (width, height), arr)


def get_circular_logo(size=72):
    if not os.path.exists(LOGO_PATH):
        return None
    pil_logo = Image.open(LOGO_PATH).convert("RGBA")
    q_logo = pil_to_qimage(pil_logo)

    out = QImage(size, size, QImage.Format.Format_ARGB32)
    out.fill(QColor(0, 0, 0, 0))

    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    path = QPainterPath()
    path.addEllipse(QRectF(1, 1, size - 2, size - 2))
    p.setClipPath(path)
    p.drawImage(QRectF(0, 0, size, size), q_logo)
    p.setClipping(False)

    p.setPen(QPen(QColor(180, 120, 80, 220), 2))
    p.drawEllipse(QRectF(1, 1, size - 2, size - 2))
    p.end()

    return out


def build_premium_clean_card(news_img, headline, date_str="০৯ নভেম্বর ২০২৬", card_w=980, photo_h=510):
    """
    রেফারেন্স ইমেজের হুবহু ক্লিন প্রিমিয়াম নিউজ কার্ড তৈরি করে।
    """
    target_photo_w = 890
    target_photo_h = photo_h

    # ছবি স্মার্ট ফেস ক্রপ করা (YuNet Face Detector)
    if isinstance(news_img, Image.Image):
        try:
            sys.path.insert(0, IMAGE_EDITOR_DIR)
            from watermark_cleaner import smart_crop_to_face
            cropped_photo = smart_crop_to_face(news_img, target_photo_w, target_photo_h)
        except Exception:
            pw, ph = news_img.size
            scale = max(target_photo_w / pw, target_photo_h / ph)
            new_pw, new_ph = int(pw * scale), int(ph * scale)
            scaled = news_img.resize((new_pw, new_ph), Image.Resampling.LANCZOS)
            l = (new_pw - target_photo_w) // 2
            t = (new_ph - target_photo_h) // 2
            cropped_photo = scaled.crop((l, t, l + target_photo_w, t + target_photo_h))
        q_photo = pil_to_qimage(cropped_photo)
    else:
        q_photo = news_img

    # হেডলাইনের উচ্চতা নির্ধারণ
    temp_img = QImage(card_w, 400, QImage.Format.Format_ARGB32)
    temp_p = QPainter(temp_img)
    font_headline = QFont(FONT_FAMILY, 34, QFont.Weight.Bold)
    temp_p.setFont(font_headline)
    text_rect = temp_p.boundingRect(
        QRectF(0, 0, card_w - 90, 400),
        Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
        headline,
    )
    temp_p.end()

    text_h = max(int(text_rect.height()) + 24, 80)
    card_h = 100 + target_photo_h + 30 + text_h + 30

    card = QImage(card_w, card_h, QImage.Format.Format_ARGB32)
    card.fill(QColor(0, 0, 0, 0))

    p = QPainter(card)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    # কার্ড ব্যাকগ্রাউন্ড
    card_path = QPainterPath()
    card_path.addRoundedRect(QRectF(1, 1, card_w - 2, card_h - 2), 30, 30)
    p.fillPath(card_path, COLOR_CARD_BG)
    p.setPen(QPen(COLOR_CARD_BORDER, 2))
    p.drawPath(card_path)

    # কোণার লাল মেরুন অ্যাকসেন্ট
    accent_sz = 65
    accent_l = QPainterPath()
    accent_l.moveTo(0, 0)
    accent_l.lineTo(accent_sz, 0)
    accent_l.lineTo(0, accent_sz)
    accent_l.closeSubpath()
    p.fillPath(accent_l, COLOR_ACCENT)

    accent_r = QPainterPath()
    accent_r.moveTo(card_w, 0)
    accent_r.lineTo(card_w - accent_sz, 0)
    accent_r.lineTo(card_w, accent_sz)
    accent_r.closeSubpath()
    p.fillPath(accent_r, COLOR_ACCENT)

    # লোগো ও চ্যানেল নাম
    logo = get_circular_logo(size=68)
    logo_x = 42
    logo_y = 18
    if logo:
        p.drawImage(QRectF(logo_x, logo_y, 68, 68), logo)
        text_x = logo_x + 78
    else:
        text_x = logo_x

    font_title = QFont(FONT_FAMILY, 24, QFont.Weight.Bold)
    p.setFont(font_title)
    p.setPen(COLOR_TEXT_MAIN)
    p.drawText(int(text_x), int(logo_y + 30), "বাঙালি ফ্যাক্টস")

    font_handle = QFont(FONT_FAMILY, 15, QFont.Weight.Medium)
    p.setFont(font_handle)
    p.setPen(COLOR_TEXT_MUTED)
    p.drawText(int(text_x), int(logo_y + 55), "@bangaliifacts")

    # বাংলা তারিখ
    font_date = QFont(FONT_FAMILY, 22, QFont.Weight.Bold)
    p.setFont(font_date)
    p.setPen(COLOR_TEXT_MAIN)
    date_rect = p.boundingRect(QRectF(0, 0, 300, 50), Qt.AlignmentFlag.AlignRight, date_str)
    date_x = card_w - 55 - date_rect.width()
    p.drawText(int(date_x), int(logo_y + 40), date_str)

    # ছবি (২২px রাউন্ডেড কর্নার + ৪px হোয়াইট বর্ডার)
    photo_x = (card_w - target_photo_w) // 2
    photo_y = 100
    photo_path = QPainterPath()
    photo_path.addRoundedRect(QRectF(photo_x, photo_y, target_photo_w, target_photo_h), 22, 22)
    p.save()
    p.setClipPath(photo_path)
    p.drawImage(QRectF(photo_x, photo_y, target_photo_w, target_photo_h), q_photo)
    p.restore()

    p.setPen(QPen(QColor(255, 255, 255), 4))
    p.drawPath(photo_path)

    # হেডলাইন
    headline_y = photo_y + target_photo_h + 20
    p.setFont(font_headline)
    p.setPen(COLOR_TEXT_MAIN)
    p.drawText(
        QRectF(45, headline_y, card_w - 90, text_h),
        Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
        headline,
    )

    p.end()
    return qimage_to_pil(card)


def compose_reels_9x16_thumbnail(card_img, bg_image=None):
    """
    রেফারেন্স ইমেজের হুবহু ১০৮০ x ১৯২০ রিল ও শর্টস থাম্বনেইল
    """
    canvas_w, canvas_h = 1080, 1920

    if bg_image:
        bg = bg_image.copy().resize((canvas_w, canvas_h), Image.Resampling.LANCZOS)
        bg = bg.filter(ImageFilter.GaussianBlur(38))
        overlay = Image.new("RGBA", (canvas_w, canvas_h), (12, 6, 9, 218))
        bg = bg.convert("RGBA")
        bg = Image.alpha_composite(bg, overlay)
        q_bg = pil_to_qimage(bg)
    else:
        q_bg = QImage(canvas_w, canvas_h, QImage.Format.Format_ARGB32)
        q_bg.fill(QColor(16, 8, 12))

    canvas = QImage(canvas_w, canvas_h, QImage.Format.Format_ARGB32)
    p = QPainter(canvas)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    p.drawImage(QRectF(0, 0, canvas_w, canvas_h), q_bg)

    q_card = pil_to_qimage(card_img)
    cw = q_card.width()
    ch = q_card.height()
    cx = (canvas_w - cw) // 2
    cy = int((canvas_h - ch) * 0.46)

    # ড্রপ শ্যাডো
    shadow_path = QPainterPath()
    shadow_path.addRoundedRect(QRectF(cx - 8, cy - 4, cw + 16, ch + 16), 34, 34)
    p.fillPath(shadow_path, QColor(0, 0, 0, 130))

    p.drawImage(QRectF(cx, cy, cw, ch), q_card)

    # টপ ব্যাজ ("বাঙালি ফ্যাক্টস | ব্রেকিং নিউজ")
    font_badge = QFont(FONT_FAMILY, 21, QFont.Weight.Bold)
    p.setFont(font_badge)
    badge_text = "বাঙালি ফ্যাক্টস  |  ব্রেকিং নিউজ"
    bbox = p.boundingRect(QRectF(0, 0, 500, 50), Qt.AlignmentFlag.AlignCenter, badge_text)
    bw = int(bbox.width()) + 50
    bh = 46
    bx = (canvas_w - bw) // 2
    by = cy - 72

    badge_path = QPainterPath()
    badge_path.addRoundedRect(QRectF(bx, by, bw, bh), 23, 23)
    p.fillPath(badge_path, COLOR_ACCENT)
    p.setPen(QPen(QColor(220, 160, 170, 180), 1))
    p.drawPath(badge_path)

    p.setPen(QColor(255, 255, 255))
    p.drawText(QRectF(bx, by, bw, bh), Qt.AlignmentFlag.AlignCenter, badge_text)

    p.end()
    return qimage_to_pil(canvas).convert("RGB")


def compose_youtube_16x9_thumbnail(card_img, bg_image=None):
    """
    ১২৮০ x ৭২০ সাইজে ইউটিউব ও ফেসবুক ল্যান্ডস্কেপ ভিডিওর জন্য নিখুঁত ক্লিন থাম্বনেইল
    """
    canvas_w, canvas_h = 1280, 720

    if bg_image:
        bg = bg_image.copy().resize((canvas_w, canvas_h), Image.Resampling.LANCZOS)
        bg = bg.filter(ImageFilter.GaussianBlur(38))
        overlay = Image.new("RGBA", (canvas_w, canvas_h), (12, 6, 9, 218))
        bg = bg.convert("RGBA")
        bg = Image.alpha_composite(bg, overlay)
        q_bg = pil_to_qimage(bg)
    else:
        q_bg = QImage(canvas_w, canvas_h, QImage.Format.Format_ARGB32)
        q_bg.fill(QColor(16, 8, 12))

    canvas = QImage(canvas_w, canvas_h, QImage.Format.Format_ARGB32)
    p = QPainter(canvas)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    p.drawImage(QRectF(0, 0, canvas_w, canvas_h), q_bg)

    q_card = pil_to_qimage(card_img)
    target_ch = int(canvas_h * 0.88)
    scale = target_ch / q_card.height()
    new_cw = int(q_card.width() * scale)
    new_ch = target_ch

    scaled_card = q_card.scaled(new_cw, new_ch, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    cx = (canvas_w - scaled_card.width()) // 2
    cy = (canvas_h - scaled_card.height()) // 2

    shadow_path = QPainterPath()
    shadow_path.addRoundedRect(QRectF(cx - 8, cy - 4, scaled_card.width() + 16, scaled_card.height() + 16), 30, 30)
    p.fillPath(shadow_path, QColor(0, 0, 0, 130))

    p.drawImage(QRectF(cx, cy, scaled_card.width(), scaled_card.height()), scaled_card)
    p.end()

    return qimage_to_pil(canvas).convert("RGB")
