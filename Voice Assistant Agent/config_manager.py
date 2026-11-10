"""
Voice Assistant Agent — Central Config Manager
===============================================
প্রোজেক্টের সব এজেন্টের .env ফাইল রিড ও রাইট করার সেন্ট্রাল ম্যানেজার।
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)

ENV_PATHS = {
    "news": os.path.join(PROJECT_DIR, "News Collector Agent", ".env"),
    "writer": os.path.join(PROJECT_DIR, "Writer Agent", ".env"),
    "voice": os.path.join(PROJECT_DIR, "Voice Over Agent", ".env"),
    "facebook": os.path.join(PROJECT_DIR, "Facebook Page Manage Agent", ".env"),
    "youtube": os.path.join(PROJECT_DIR, "Youtube Page Manage Agent", ".env"),
    "assistant": os.path.join(BASE_DIR, ".env"),
}

def parse_env_file(file_path: str) -> dict:
    config = {}
    if not os.path.exists(file_path):
        return config
    with open(file_path, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            config[k.strip()] = v.strip().strip('"').strip("'")
    return config

def write_env_file(file_path: str, updates: dict):
    # ইউজার যদি ফিল্ড ডিলিট করে, তবে সেই কী-গুলোও ফাইল থেকে বাদ যাবে
    # আর বিদ্যমান লাইনের কমেন্ট ইত্যাদি অক্ষত থাকবে
    lines = []
    seen = set()
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8-sig") as f:
            for line in f:
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    k, _, _ = stripped.partition("=")
                    k = k.strip()
                    if k in updates:
                        lines.append(f"{k}={updates[k]}\n")
                        seen.add(k)
                        continue
                    else:
                        # যদি ইউজার ডিলিট করে দিয়ে থাকে, তবে ফাইলে এটি আর রাইট হবে না
                        continue
                lines.append(line if line.endswith("\n") else line + "\n")

    for k, v in updates.items():
        if k not in seen:
            lines.append(f"{k}={v}\n")

    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

def get_all_configs() -> dict:
    return {agent: parse_env_file(path) for agent, path in ENV_PATHS.items()}

def update_agent_config(agent: str, updates: dict) -> bool:
    if agent in ENV_PATHS:
        write_env_file(ENV_PATHS[agent], updates)
        return True
    return False

