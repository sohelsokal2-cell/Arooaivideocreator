"""
Voice Assistant Agent — Flask Web UI Backend
=============================================
সেন্ট্রাল ওয়েব ড্যাশবোর্ড সার্ভার (API Management + Live Monitoring + AI Chat)।
"""

import json
import os
import sys
from flask import Flask, jsonify, render_template, request, send_from_directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
sys.path.insert(0, BASE_DIR)

import config_manager
import groq_brain
import intent_handler
from pipeline_monitor import monitor
import tts_output

app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"), static_folder=os.path.join(BASE_DIR, "static"))

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/configs", methods=["GET"])
def get_configs():
    return jsonify(config_manager.get_all_configs())

@app.route("/api/configs/<agent>", methods=["POST"])
def update_config(agent):
    data = request.json or {}
    success = config_manager.update_agent_config(agent, data)
    return jsonify({"success": success})

@app.route("/api/pipeline/status", methods=["GET"])
def pipeline_status():
    state = monitor.get_state()
    # সর্বশেষ খবরের তথ্য যোগ করা
    state["context"] = intent_handler.get_pipeline_context()
    
    # সর্বশেষ লিংকসমূহ
    links_res = intent_handler.execute_intent("get_links")
    state["published_links"] = links_res.get("msg", "")
    return jsonify(state)

@app.route("/api/pipeline/run", methods=["POST"])
def run_pipeline():
    data = request.json or {}
    mode = data.get("mode", "DIRECT")
    voice_notify = data.get("voice_notify", True)
    started, msg = monitor.start_pipeline(mode=mode, voice_notify=voice_notify)
    return jsonify({"success": started, "message": msg})

@app.route("/api/assistant/chat", methods=["POST"])
def assistant_chat():
    data = request.json or {}
    user_msg = data.get("message", "").strip()
    if not user_msg:
        return jsonify({"success": False, "error": "মেসেজ ফাঁকা হতে পারে না"})

    context = intent_handler.get_pipeline_context()
    analysis = groq_brain.analyze_user_query(user_msg, context)
    intent = analysis.get("intent", "chat")
    spoken = analysis.get("spoken_response", "")

    # অডিও স্পিকিং
    if data.get("speak", True) and spoken:
        tts_output.speak_text(spoken, auto_play=True)

    action_result = {}
    if intent in ["run_pipeline", "get_news", "get_links", "check_status"]:
        action_result = intent_handler.execute_intent(intent)

    return jsonify({
        "success": True,
        "intent": intent,
        "spoken": spoken,
        "action_result": action_result.get("msg", "")
    })

@app.route("/api/preview/video")
def preview_video():
    video_dir = os.path.join(PROJECT_DIR, "Video Creator Agent", "output", "latest")
    video_file = os.path.join(video_dir, "reel_latest.mp4")
    if os.path.exists(video_file):
        resp = send_from_directory(video_dir, "reel_latest.mp4")
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp
    return "Video not found", 404

@app.route("/api/preview/thumbnail")
def preview_thumbnail():
    thumb_dir = os.path.join(PROJECT_DIR, "Thumbnail creator Agent", "output", "latest")
    thumb_file = os.path.join(thumb_dir, "thumbnail_reels_9x16.jpg")
    if os.path.exists(thumb_file):
        resp = send_from_directory(thumb_dir, "thumbnail_reels_9x16.jpg")
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp
    return "Thumbnail not found", 404

if __name__ == "__main__":
    print("=" * 65)
    print("  🚀 বাঙালি ফ্যাক্টস সেন্ট্রাল ড্যাশবোর্ড চালু হচ্ছে...")
    print("  🌐 ব্রাউজারে খুলুন: http://localhost:5000")
    print("=" * 65)
    app.run(host="0.0.0.0", port=5000, debug=False)

