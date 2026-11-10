import os
import sys
from PIL import Image, ImageFilter
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontDatabase,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QLinearGradient,
    QRadialGradient,
)
from PyQt6.QtWidgets import QApplication

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
LOGO_PATH = os.path.join(ASSETS_DIR, "logo.jpg")
FONTS_DIR = os.path.join(os.path.dirname(BASE_DIR), "Image Editor Agent", "fonts")

_APP = QApplication.instance() or QApplication(sys.argv)

FONT_FAMILY = "Anek Bangla"
for f_name in ["AnekBangla-Bold.ttf", "NotoSansBengali-Bold.ttf", "HindSiliguri-Bold.ttf"]:
    f_path = os.path.join(FONTS_DIR, f_name)
    if os.path.exists(f_path):
        f_id = QFontDatabase.addApplicationFont(f_path)
        fams = QFontDatabase.applicationFontFamilies(f_id)
        if fams and "Anek" in fams[0]:
            FONT_FAMILY = fams[0]

COLOR_ACCENT = QColor(136, 19, 32)          # ডিপ মেরুন
COLOR_GOLD = QColor(255, 215, 0)            # গোল্ডেন ইয়েলো


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


def get_large_circular_logo(size=320):
    """আউটরোর জন্য বড় ও আকর্ষণীয় গোল্ডেন বর্ডারযুক্ত সার্কুলার লোগো"""
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
    path.addEllipse(QRectF(4, 4, size - 8, size - 8))
    p.setClipPath(path)
    p.drawImage(QRectF(4, 4, size - 8, size - 8), q_logo)
    p.setClipping(False)

    # প্রিমিয়াম ৩ডি গোল্ডেন রিং
    p.setPen(QPen(COLOR_GOLD, 8))
    p.drawEllipse(QRectF(4, 4, size - 8, size - 8))
    p.end()

    return out


def render_outro_slide(output_path, width=1080, height=1920):
    """
    ১০৮০ x ১৯২০ সাইজে হাই-কনভার্টিং ব্রডকাস্ট ব্র্যান্ডেড আউটরো স্লাইড তৈরি করে।
    """
    canvas = QImage(width, height, QImage.Format.Format_ARGB32)
    p = QPainter(canvas)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    # ১. সিনেমাটিক ডার্ক ব্যাকগ্রাউন্ড ও স্পটলাইট
    grad = QLinearGradient(0, 0, 0, height)
    grad.setColorAt(0.0, QColor(14, 6, 8))
    grad.setColorAt(0.5, QColor(32, 10, 16))
    grad.setColorAt(1.0, QColor(10, 4, 6))
    p.fillRect(0, 0, width, height, grad)

    # সেন্টার গোল্ডেন রেডিয়াল স্পটলাইট
    spotlight = QRadialGradient(width // 2, int(height * 0.42), 650)
    spotlight.setColorAt(0.0, QColor(255, 215, 0, 55))
    spotlight.setColorAt(0.6, QColor(136, 19, 32, 40))
    spotlight.setColorAt(1.0, QColor(0, 0, 0, 0))
    p.fillRect(0, 0, width, height, spotlight)

    # ২. মাঝখানে বড় অফিশিয়াল চ্যানেল লোগো
    logo_size = 340
    logo = get_large_circular_logo(size=logo_size)
    logo_x = (width - logo_size) // 2
    logo_y = int(height * 0.28)

    # লোগোর নিচে ড্রপ শ্যাডো
    shadow_path = QPainterPath()
    shadow_path.addEllipse(QRectF(logo_x - 10, logo_y - 6, logo_size + 20, logo_size + 20))
    p.fillPath(shadow_path, QColor(0, 0, 0, 180))

    if logo:
        p.drawImage(QRectF(logo_x, logo_y, logo_size, logo_size), logo)

    # ৩. চ্যানেল নাম: বাঙালি ফ্যাক্টস
    font_title = QFont(FONT_FAMILY, 56, QFont.Weight.Bold)
    p.setFont(font_title)
    p.setPen(COLOR_GOLD)
    title_rect = QRectF(0, logo_y + logo_size + 40, width, 80)
    p.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, "বাঙালি ফ্যাক্টস")

    # হ্যান্ডেল: @bangaliifacts
    font_handle = QFont(FONT_FAMILY, 30, QFont.Weight.Medium)
    p.setFont(font_handle)
    p.setPen(QColor(220, 220, 220))
    handle_rect = QRectF(0, logo_y + logo_size + 125, width, 50)
    p.drawText(handle_rect, Qt.AlignmentFlag.AlignCenter, "@bangaliifacts")

    # ৪. ফলো পিল বাটন (Follow / Subscribe CTA)
    btn_w = 760
    btn_h = 100
    btn_x = (width - btn_w) // 2
    btn_y = logo_y + logo_size + 210

    # বাটনের ড্রপ শ্যাডো
    btn_shadow = QPainterPath()
    btn_shadow.addRoundedRect(QRectF(btn_x - 4, btn_y + 4, btn_w + 8, btn_h + 8), 50, 50)
    p.fillPath(btn_shadow, QColor(0, 0, 0, 160))

    # মূল মেরুন বাটন পিল
    btn_path = QPainterPath()
    btn_path.addRoundedRect(QRectF(btn_x, btn_y, btn_w, btn_h), 50, 50)
    p.fillPath(btn_path, COLOR_ACCENT)
    p.setPen(QPen(QColor(255, 255, 255, 220), 3))
    p.drawPath(btn_path)

    # বাটন টেক্সট: সুন্দর মার্জিন সহ পারফেক্ট সাইজ (যাতে কোনো অংশ না কাটে)
    font_btn = QFont(FONT_FAMILY, 26, QFont.Weight.Bold)
    p.setFont(font_btn)
    p.setPen(QColor(255, 255, 255))
    p.drawText(QRectF(btn_x + 15, btn_y, btn_w - 30, btn_h), Qt.AlignmentFlag.AlignCenter, "🔔 নিয়মিত আপডেটের জন্য ফলো করুন")

    # ৫. নিচে ট্যাগলাইন
    font_tagline = QFont(FONT_FAMILY, 26, QFont.Weight.Normal)
    p.setFont(font_tagline)
    p.setPen(QColor(200, 180, 185, 210))
    tag_rect = QRectF(0, btn_y + btn_h + 35, width, 50)
    p.drawText(tag_rect, Qt.AlignmentFlag.AlignCenter, "লাইক ও শেয়ার করে সত্য প্রকাশে পাশে থাকুন")

    # চারপাশের পাতলা গোল্ডেন বর্ডার
    border_pen = QPen(QColor(255, 215, 0, 160), 4)
    p.setPen(border_pen)
    p.drawRect(2, 2, width - 4, height - 4)

    p.end()

    pil_out = qimage_to_pil(canvas).convert("RGB")
    pil_out.save(output_path, "JPEG", quality=95)
    return output_path


if __name__ == "__main__":
    test_out = os.path.join(BASE_DIR, "assets", "test_outro.jpg")
    render_outro_slide(test_out)
    print("Outro slide created at:", test_out)

