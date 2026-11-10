import os
import subprocess
import sys
import time
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def wait_for_server(url, timeout=10):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False

def main():
    print("============================================================")
    print("  🚀 Bangalii Facts AI Studio Dashboard")
    print("  📱 Starting Server & Dedicated App Window (1280x860)...")
    print("============================================================")

    # Start Flask server
    server_process = subprocess.Popen([sys.executable, "app.py"], cwd=BASE_DIR)

    # Wait for server ready
    url = "http://localhost:5000"
    wait_for_server(url)

    # Locate Chrome or Edge
    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    profile_dir = os.path.join(os.environ.get("LOCALAPPDATA", BASE_DIR), "BangaliiFactsStudioProfile")

    browser_cmd = None
    if os.path.exists(chrome_path):
        browser_cmd = [chrome_path, f"--app={url}", "--window-size=1280,860", f"--user-data-dir={profile_dir}"]
    elif os.path.exists(edge_path):
        browser_cmd = [edge_path, f"--app={url}", "--window-size=1280,860", f"--user-data-dir={profile_dir}"]

    if browser_cmd:
        try:
            browser_process = subprocess.Popen(browser_cmd)
            browser_process.wait()
        except Exception as e:
            print(f"Browser launch note: {e}")
    else:
        import webbrowser
        webbrowser.open(url)

    print("\nDashboard closed. Stopping server...")
    try:
        server_process.terminate()
    except Exception:
        pass

if __name__ == "__main__":
    main()

