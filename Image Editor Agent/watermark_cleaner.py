import os
import numpy as np
from PIL import Image, ImageEnhance

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
YUNET_PATH = os.path.join(BASE_DIR, "assets", "yunet.onnx")


def clean_source_image(img_input, strip_bottom_banner=True):
    """
    সংবাদপত্রের ছবির ওয়াটারমার্ক, নিচের ব্যানার ও অপ্রয়োজনীয় ব্র্যান্ডিং ক্লিন করে।
    """
    if isinstance(img_input, str):
        img = Image.open(img_input).convert("RGB")
    else:
        img = img_input.convert("RGB")

    w, h = img.size

    # ১. প্রথম আলো ও অন্যান্য পত্রিকার নিচের ব্যানার ক্রপ করা
    # সাধারণত নিচের ১০% থেকে ১২% অংশে পত্রিকার ব্যানার/ওয়াটারমার্ক স্ট্রিপ থাকে
    if strip_bottom_banner:
        # ব্যানার ডিটেকশন: নিচের ১২% ক্রপ করা
        banner_height = int(h * 0.12)
        # যদি অ্যাসপেক্ট রেশিও যথেষ্ট চওড়া হয়
        if h > 300 and (w / h) >= 1.4:
            img = img.crop((0, 0, w, h - banner_height))
            w, h = img.size

    # ২. হালকা শার্পনেস ও কনট্রাস্ট অপ্টিমাইজেশন
    enhancer = ImageEnhance.Sharpness(img)
    img = enhancer.enhance(1.15)
    c_enhancer = ImageEnhance.Contrast(img)
    img = c_enhancer.enhance(1.05)

    return img


def smart_crop_to_face(pil_img, target_w, target_h):
    """
    YuNet ONNX মডেল দিয়ে ফেস ডিটেক্ট করে ফেস-সেন্টার্ড ক্রপ করে।
    যদি কোনো মুখ না পাওয়া যায় তাহলে সেন্টার ক্রপ ব্যবহার করে।

    Args:
        pil_img   : PIL Image (RGB)
        target_w  : আউটপুটের প্রস্থ (পিক্সেল)
        target_h  : আউটপুটের উচ্চতা (পিক্সেল)

    Returns:
        PIL Image (RGB) — সঠিক সাইজে ক্রপ করা
    """
    # স্কেল আপ — ক্রপ করার আগে নিশ্চিত করা হচ্ছে ছবি যথেষ্ট বড়
    orig_w, orig_h = pil_img.size
    scale = max(target_w / orig_w, target_h / orig_h)
    if scale > 1.0:
        new_w = int(orig_w * scale)
        new_h = int(orig_h * scale)
        pil_img = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        orig_w, orig_h = new_w, new_h

    # YuNet দিয়ে ফেস ডিটেকশন
    face_cx, face_cy = None, None

    try:
        import cv2

        img_np = np.array(pil_img.convert("RGB"))
        h_np, w_np = img_np.shape[:2]

        if os.path.exists(YUNET_PATH):
            detector = cv2.FaceDetectorYN.create(
                YUNET_PATH, "", (w_np, h_np),
                score_threshold=0.55,
                nms_threshold=0.3,
                top_k=5000,
            )
            _, faces = detector.detect(img_np)

            if faces is not None and len(faces) > 0:
                # সবচেয়ে বড় মুখটি (আয়তন অনুযায়ী) বেছে নেওয়া হচ্ছে
                best_face = max(faces, key=lambda f: float(f[2]) * float(f[3]))
                fx = int(best_face[0])
                fy = int(best_face[1])
                fw = int(best_face[2])
                fh = int(best_face[3])

                # মুখের কেন্দ্র (মাথাসহ সামান্য উপরে শিফট)
                face_cx = fx + fw // 2
                face_cy = fy + int(fh * 0.4)   # মাথার উপরের অংশ ফ্রেমে রাখতে
                print(f"      🎯 মুখ শনাক্ত: ({face_cx}, {face_cy}) — {len(faces)}টি মুখের মধ্যে সেরা")
            else:
                print("      ℹ️  কোনো মুখ পাওয়া যায়নি — সেন্টার ক্রপ ব্যবহার করা হচ্ছে")
        else:
            print(f"      ⚠️  YuNet মডেল নেই: {YUNET_PATH} — সেন্টার ক্রপ ব্যবহার করা হচ্ছে")

    except ImportError:
        print("      ⚠️  cv2 পাওয়া যায়নি — সেন্টার ক্রপ ব্যবহার করা হচ্ছে")
    except Exception as exc:
        print(f"      ⚠️  ফেস ডিটেকশন ত্রুটি: {exc} — সেন্টার ক্রপ ব্যবহার করা হচ্ছে")

    # ক্রপ কেন্দ্র নির্ধারণ
    if face_cx is None:
        face_cx = orig_w // 2
        face_cy = orig_h // 2

    # নিরাপদ ক্লিপিং: বাউন্ডারির বাইরে না যাওয়ার নিশ্চয়তা
    left = max(0, min(face_cx - target_w // 2, orig_w - target_w))
    top  = max(0, min(face_cy - target_h // 2, orig_h - target_h))
    right  = left + target_w
    bottom = top  + target_h

    return pil_img.crop((left, top, right, bottom))
