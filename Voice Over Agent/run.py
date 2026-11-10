import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
        sys.stdin.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

import main


def show_menu():
    while True:
        print("\n" + "=" * 65)
        print("     বাংলা এআই ভয়েস-ওভার এজেন্ট (Gemini Natural Human Voices)")
        print("=" * 65)
        print("\nকোন কণ্ঠে ভয়েস-ওভার অডিও তৈরি করতে চান?")
        print("  [1] Kore   - মিষ্টি, সাবলীল ও বাস্তব নারী কণ্ঠ (ডেমো অডিওর মতো)")
        print("  [2] Aoede  - স্পষ্ট ও পেশাদার টিভি সংবাদ উপস্থাপিকার নারী কণ্ঠ")
        print("  [3] Charon - গম্ভীর ও ব্যক্তিত্বসম্পন্ন পুরুষ সংবাদ উপস্থাপকের কণ্ঠ")
        print("  [4] ALL    - সব ৩টি কণ্ঠেই আলাদা আলাদা ফুল অডিও তৈরি")
        print("  [5] বের হন")
        print("=" * 65)

        try:
            choice = input("\nআপনার পছন্দ লিখুন (১-৫) [ডিফল্ট: ১]: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nপ্রোগ্রাম সমাপ্ত।")
            sys.exit(0)

        if not choice:
            choice = "1"

        if choice == "1":
            sys.argv = ["main.py", "--voice", "kore"]
            main.main()
            break

        elif choice == "2":
            sys.argv = ["main.py", "--voice", "aoede"]
            main.main()
            break

        elif choice == "3":
            sys.argv = ["main.py", "--voice", "charon"]
            main.main()
            break

        elif choice == "4":
            sys.argv = ["main.py", "--voice", "all"]
            main.main()
            break

        elif choice == "5":
            print("বিদায়!")
            sys.exit(0)

        else:
            print("ভুল ইনপুট! অনুগ্রহ করে ১ থেকে ৫ এর মধ্যে বেছে নিন।")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        main.main()
    else:
        show_menu()
