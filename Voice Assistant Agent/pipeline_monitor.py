"""
Voice Assistant Agent — Pipeline Runner & Live Monitor
======================================================
পাইপলাইন এক্সিকিউশন, লাইভ লগ পর্যবেক্ষণ ও ভয়েস রিপোর্টিং থ্রেড।
"""

import json
import os
import re
import subprocess
import sys
import threading
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
RUN_PIPELINE_SCRIPT = os.path.join(PROJECT_DIR, "run_pipeline.py")

import tts_output

class PipelineMonitor:
    def __init__(self):
        self.is_running = False
        self.current_step = 0
        self.total_steps = 8
        self.current_agent_name = ""
        self.logs = []
        self.last_status = "idle" # idle, running, success, error
        self.error_message = ""
        self.reports = []
        self._lock = threading.Lock()

    def get_state(self):
        with self._lock:
            return {
                "is_running": self.is_running,
                "current_step": self.current_step,
                "total_steps": self.total_steps,
                "current_agent_name": self.current_agent_name,
                "last_status": self.last_status,
                "error_message": self.error_message,
                "recent_logs": self.logs[-30:],
                "reports": self.reports[-10:],
            }

    def start_pipeline(self, mode="DIRECT", voice_notify=True):
        with self._lock:
            if self.is_running:
                return False, "পাইপলাইন ইতিমধ্যে চলছে।"
            self.is_running = True
            self.last_status = "running"
            self.current_step = 1
            self.current_agent_name = "১. সংবাদ সংগ্রহ ও বহু-উৎস বিশ্লেষণ"
            self.error_message = ""
            self.logs = []

        thread = threading.Thread(target=self._run_thread, args=(mode, voice_notify), daemon=True)
        thread.start()
        return True, "পাইপলাইন সফলভাবে শুরু হয়েছে।"

    def _add_report(self, text, voice_notify=True):
        with self._lock:
            self.reports.append({
                "time": time.strftime("%H:%M:%S"),
                "text": text
            })
        if voice_notify:
            threading.Thread(target=tts_output.speak_text, args=(text,), daemon=True).start()

    def _run_thread(self, mode, voice_notify):
        self._add_report("বাঙালি ফ্যাক্টস রিলস পাইপলাইন শুরু হয়েছে। সংবাদ সংগ্রহ চলছে।", voice_notify)
        cmd = [sys.executable, "-u", RUN_PIPELINE_SCRIPT, "--new"]
        
        # এনভায়রনমেন্ট আনবাফার্ড রাখা যাতে সঙ্গে সঙ্গে আউটপুট পাওয়া যায়
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"

        agent_names = {
            1: "১. সংবাদ সংগ্রহ ও বহু-উৎস বিশ্লেষণ",
            2: "২. ৪৫-৬০ সেকেন্ড রিল স্ক্রিপ্ট তৈরি",
            3: "৩. স্টুডিও বাংলা ভয়েস-ওভার",
            4: "৪. ব্র্যান্ডেড রিল স্লাইড তৈরি",
            5: "৫. ১০৮০x১৯২০ ভার্টিক্যাল ভিডিও রেন্ডারিং",
            6: "৬. ক্লিন থাম্বনেইল স্টুডিও",
            7: "৭. ফেসবুক রিলস অটো-পাবলিশিং",
            8: "৮. ইউটিউব শর্টস অটো-আপলোড"
        }

        agent_voice_alerts = {
            2: "সংবাদ সংগ্রহ সম্পন্ন। স্ক্রিপ্ট লেখা হচ্ছে।",
            3: "স্ক্রিপ্ট প্রস্তুত। স্টুডিও ভয়েস-ওভার তৈরি হচ্ছে।",
            5: "অডিও ও স্লাইড প্রস্তুত। ভিডিও রেন্ডারিং চলছে।",
            7: "ভিডিও প্রস্তুত। ফেসবুকে পাবলিশিং চলছে।",
            8: "ইউটিউব শর্টস আপলোড হচ্ছে।"
        }

        try:
            process = subprocess.Popen(
                cmd,
                cwd=PROJECT_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                bufsize=1
            )

            for line in process.stdout:
                line_str = line.strip()
                if line_str:
                    with self._lock:
                        self.logs.append(line_str)

                    # স্টেপ ডিটেকশন রেগেক্স: [1/8], [2/8], ইত্যাদি
                    match = re.search(r"\[([1-8])/8\]", line_str)
                    if match:
                        step_num = int(match.group(1))
                        with self._lock:
                            self.current_step = step_num
                            self.current_agent_name = agent_names.get(step_num, f"ধাপ {step_num}")
                        
                        if step_num in agent_voice_alerts:
                            self._add_report(agent_voice_alerts[step_num], voice_notify)
                    else:
                        # অল্টারনেটিভ ফলব্যাক ডিটেকশন
                        if "News Collector" in line_str and "শুরু" in line_str:
                            with self._lock:
                                self.current_step = 1
                                self.current_agent_name = agent_names[1]
                        elif "Writer Agent" in line_str and "শুরু" in line_str:
                            with self._lock:
                                self.current_step = 2
                                self.current_agent_name = agent_names[2]
                        elif "Voice Over Agent" in line_str and "শুরু" in line_str:
                            with self._lock:
                                self.current_step = 3
                                self.current_agent_name = agent_names[3]
                        elif "Image Editor Agent" in line_str and "শুরু" in line_str:
                            with self._lock:
                                self.current_step = 4
                                self.current_agent_name = agent_names[4]
                        elif "Video Creator Agent" in line_str and "শুরু" in line_str:
                            with self._lock:
                                self.current_step = 5
                                self.current_agent_name = agent_names[5]
                        elif "Thumbnail" in line_str and "শুরু" in line_str:
                            with self._lock:
                                self.current_step = 6
                                self.current_agent_name = agent_names[6]
                        elif "Facebook" in line_str and "শুরু" in line_str:
                            with self._lock:
                                self.current_step = 7
                                self.current_agent_name = agent_names[7]
                        elif "YouTube" in line_str and "শুরু" in line_str:
                            with self._lock:
                                self.current_step = 8
                                self.current_agent_name = agent_names[8]

            process.wait()
            with self._lock:
                self.is_running = False
                if process.returncode == 0:
                    self.last_status = "success"
                    self.current_step = 8
                    self._add_report("অভিনন্দন! নতুন রিল সফলভাবে তৈরি এবং সোশ্যাল মিডিয়ায় পাবলিশ সম্পন্ন হয়েছে।", voice_notify)
                else:
                    self.last_status = "error"
                    self.error_message = f"পাইপলাইনে ত্রুটি ঘটেছে (Code: {process.returncode})"
                    self._add_report("সতর্কতা: পাইপলাইনে একটি ত্রুটি ঘটেছে। দয়া করে লগ চেক করুন।", voice_notify)

        except Exception as exc:
            with self._lock:
                self.is_running = False
                self.last_status = "error"
                self.error_message = str(exc)
            self._add_report(f"সিস্টেম ত্রুটি: {exc}", voice_notify)

monitor = PipelineMonitor()

