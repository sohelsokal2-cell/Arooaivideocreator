import os
import sys
from PIL import Image
from watermark_cleaner import smart_crop_to_face
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
    QPixmap,
)
from PyQt6.QtWidgets import QApplication

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONTS_DIR = os.path.join(BASE_DIR, "fonts")
LOGO_PATH = os.path.join(BASE_DIR, "assets", "logo.jpg")

# PyQt6 Application নিশ্চিত করা
_APP = QApplication.instance() or QApplication(sys.argv)

# ফন্ট লোড করা
FONT_FAMILY = "Anek Bangla"
for f_name in ["AnekBangla-Bold.ttf", "NotoSansBengali-Bold.ttf", "HindSiliguri-Bold.ttf"]:
    f_path = os.path.join(FONTS_DIR, f_name)
    if os.path.exists(f_path):
        f_id = QFontDatabase.addApplicationFont(f_path)
        fams = QFontDatabase.applicationFontFamilies(f_id)
        if fams and "Anek" in fams[0]:
            FONT_FAMILY = fams[0]

# কালার প্যালেট (রেফারেন্স ইমেজ অনুযায়ী)
COLOR_CARD_BG = QColor(250, 245, 246)       # নরম হালকা ব্যাকগ্রাউন্ড
COLOR_CARD_BORDER = QColor(235, 218, 222)   # সূক্ষ্ম বর্ডার
COLOR_ACCENT = QColor(136, 19, 32)          # ডিপ মেরুন অ্যাকসেন্ট
COLOR_TEXT_MAIN = QColor(122, 18, 29)       # গাঢ় মেরুন হেডলাইন
COLOR_TEXT_MUTED = QColor(140, 80, 90)      # নরম হ্যান্ডেল টেক্সট


def pil_to_qimage(pil_img):
    """PIL Image কে QImage-এ রূপান্তর করে।"""
    img_rgb = pil_img.convert("RGBA")
    data = img_rgb.tobytes("raw", "RGBA")
    qimg = QImage(data, pil_img.width, pil_img.height, QImage.Format.Format_RGBA8888)
    return qimg.copy()


def qimage_to_pil(qimg):
    """QImage কে PIL Image-এ রূপান্তর করে।"""
    qimg = qimg.convertToFormat(QImage.Format.Format_RGBA8888)
    width = qimg.width()
    height = qimg.height()
    ptr = qimg.constBits()
    ptr.setsize(height * width * 4)
    arr = bytes(ptr)
    return Image.frombytes("RGBA", (width, height), arr)


def get_circular_logo(size=72):
    """লোগোটিকে গোলাকার করে বর্ডার সহ প্রস্তুত করে।"""
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

    # পাতলা ব্রোঞ্জ বর্ডার
    p.setPen(QPen(QColor(180, 120, 80, 220), 2))
    p.drawEllipse(QRectF(1, 1, size - 2, size - 2))
    p.end()

    return out


def build_news_card(news_img, headline, date_str="০৯ নভেম্বর ২০২৬", channel_name="বাঙালি ফ্যাক্টস", handle="@bangaliifacts"):
    """
    HarfBuzz টেক্সট শেপিং দিয়ে নিখুঁত বাংলা ফন্টে ব্র্যান্ডেড নিউজ কার্ড তৈরি করে।
    """
    card_w = 980
    target_photo_w = 890
    target_photo_h = 490

    # মূল ছবি ফেস ডিটেকশন দিয়ে স্মার্ট ক্রপ করা
    if isinstance(news_img, Image.Image):
        cropped_photo = smart_crop_to_face(news_img, target_photo_w, target_photo_h)
        q_photo = pil_to_qimage(cropped_photo)
    else:
        q_photo = news_img

    # হেডলাইনের দৈর্ঘ্য অনুযায়ী ডায়নামিক ফন্ট সাইজ (যাতে কোনো লেখা না কাটে)
    font_size = 32
    if len(headline) > 85:
        font_size = 25
    elif len(headline) > 60:
        font_size = 28

    temp_img = QImage(card_w, 400, QImage.Format.Format_ARGB32)
    temp_p = QPainter(temp_img)
    font_headline = QFont(FONT_FAMILY, font_size, QFont.Weight.Bold)
    temp_p.setFont(font_headline)
    text_rect = temp_p.boundingRect(
        QRectF(0, 0, card_w - 90, 500),
        Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
        headline,
    )
    temp_p.end()

    text_h = max(int(text_rect.height()) + 30, 85)
    card_h = 100 + target_photo_h + 30 + text_h + 35

    card = QImage(card_w, card_h, QImage.Format.Format_ARGB32)
    card.fill(QColor(0, 0, 0, 0))

    p = QPainter(card)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    # কার্ড ব্যাকগ্রাউন্ড ও বর্ডার
    card_path = QPainterPath()
    card_path.addRoundedRect(QRectF(1, 1, card_w - 2, card_h - 2), 30, 30)
    p.fillPath(card_path, COLOR_CARD_BG)
    p.setPen(QPen(COLOR_CARD_BORDER, 2))
    p.drawPath(card_path)

    # টপ-লেফট এবং টপ-রাইট লাল কোণা অ্যাকসেন্ট (রেফারেন্সের মতো)
    accent_sz = 65
    accent_left = QPainterPath()
    accent_left.moveTo(0, 0)
    accent_left.lineTo(accent_sz, 0)
    accent_left.lineTo(0, accent_sz)
    accent_left.closeSubpath()
    p.fillPath(accent_left, COLOR_ACCENT)

    accent_right = QPainterPath()
    accent_right.moveTo(card_w, 0)
    accent_right.lineTo(card_w - accent_sz, 0)
    accent_right.lineTo(card_w, accent_sz)
    accent_right.closeSubpath()
    p.fillPath(accent_right, COLOR_ACCENT)

    # হেডার বাম পাশ: লোগো ও নাম
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
    p.drawText(int(text_x), int(logo_y + 30), channel_name)

    font_handle = QFont(FONT_FAMILY, 15, QFont.Weight.Medium)
    p.setFont(font_handle)
    p.setPen(COLOR_TEXT_MUTED)
    p.drawText(int(text_x), int(logo_y + 55), handle)

    # হেডার ডান পাশ: বাংলা তারিখ
    font_date = QFont(FONT_FAMILY, 22, QFont.Weight.Bold)
    p.setFont(font_date)
    p.setPen(COLOR_TEXT_MAIN)
    date_rect = p.boundingRect(QRectF(0, 0, 300, 50), Qt.AlignmentFlag.AlignRight, date_str)
    date_x = card_w - 55 - date_rect.width()
    p.drawText(int(date_x), int(logo_y + 40), date_str)

    # মাঝখানে ছবি পেস্ট করা (রাউন্ডেড কর্নার ও ৪px হোয়াইট বর্ডার)
    photo_x = (card_w - target_photo_w) // 2
    photo_y = 100

    photo_path = QPainterPath()
    photo_path.addRoundedRect(QRectF(photo_x, photo_y, target_photo_w, target_photo_h), 22, 22)
    p.save()
    p.setClipPath(photo_path)
    p.drawImage(QRectF(photo_x, photo_y, target_photo_w, target_photo_h), q_photo)
    p.restore()

    # হোয়াইট বর্ডার
    p.setPen(QPen(QColor(255, 255, 255), 4))
    p.drawPath(photo_path)

    # নিচে হেডলাইন টেক্সট (Anek Bangla বোল্ড ফন্ট, হার্ফবাজ শেপিং)
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


def compose_reel_slide(card_img, bg_image=None):
    """
    ১০৮০ x ১৯২০ (৯:১৬ রিল ফরম্যাট) ক্যানভাসে ব্র্যান্ডেড কার্ডটিকে সেন্টার করে তৈরি করে।
    """
    canvas_w, canvas_h = 1080, 1920

    # ব্যাকগ্রাউন্ড
    if bg_image:
        from PIL import ImageFilter
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
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    p.drawImage(QRectF(0, 0, canvas_w, canvas_h), q_bg)

    q_card = pil_to_qimage(card_img)
    cw = q_card.width()
    ch = q_card.height()
    cx = (canvas_w - cw) // 2
    cy = int((canvas_h - ch) * 0.46)

    # কার্ডের ড্রপ শ্যাডো
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
    p.fillPath(badge_path, QColor(136, 19, 32, 240))
    p.setPen(QPen(QColor(220, 160, 170, 180), 1))
    p.drawPath(badge_path)

    p.setPen(QColor(255, 255, 255))
    p.drawText(QRectF(bx, by, bw, bh), Qt.AlignmentFlag.AlignCenter, badge_text)

    p.end()
    return qimage_to_pil(canvas).convert("RGB")
