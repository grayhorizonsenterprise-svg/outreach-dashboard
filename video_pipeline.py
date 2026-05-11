"""
video_pipeline.py — Gray Horizons Enterprise
Master video pipeline. Run daily via Task Scheduler.
  1. Downloads fresh clips from Pexels
  2. Processes with captions via ffmpeg
  3. Places finished videos in READY_TO_UPLOAD folder
  4. Uploads to YouTube automatically (if API key set)

Revenue: YouTube ad revenue + affiliate links in descriptions
"""

import os
import sys
import subprocess
import glob
import time
import random
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DIR       = os.path.dirname(os.path.abspath(__file__))
BASE      = os.path.join(DIR, "viral_clips")
READY     = os.path.join(BASE, "READY_TO_UPLOAD")
POSTED    = os.path.join(BASE, "POSTED")
QUEUE     = os.path.join(BASE, "QUEUE")
LOG_FILE  = os.path.join(BASE, "upload_log.txt")

YOUTUBE_KEY         = os.getenv("YOUTUBE_API_KEY", "")
YOUTUBE_CLIENT_ID   = os.getenv("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET", "")

for d in [BASE, READY, POSTED, QUEUE]:
    os.makedirs(d, exist_ok=True)


# ─── STEP 1: FETCH CLIPS ─────────────────────────────────────────────────────
def fetch_clips():
    print("\n[STEP 1] Fetching new clips from Pexels...")
    script = os.path.join(DIR, "viral_clip_fetcher.py")
    if os.path.exists(script):
        subprocess.run([sys.executable, "-u", script], timeout=300)
    else:
        print("  viral_clip_fetcher.py not found — skipping")


# ─── STEP 2: PROCESS CLIPS ───────────────────────────────────────────────────
def process_clips():
    print("\n[STEP 2] Processing clips with captions...")
    script = os.path.join(DIR, "viral_engine.py")
    if os.path.exists(script):
        subprocess.run([sys.executable, "-u", script], timeout=600)
    else:
        print("  viral_engine.py not found — skipping")


# ─── STEP 3: REPORT READY ────────────────────────────────────────────────────
def report_ready():
    ready_files = glob.glob(os.path.join(READY, "*.mp4"))
    queue_files = glob.glob(os.path.join(QUEUE, "*.mp4"))
    print(f"\n[STEP 3] Ready to upload: {len(ready_files)} clips")
    print(f"         Queued: {len(queue_files)} clips")
    if ready_files:
        print(f"         Folder: {READY}")
    return ready_files + queue_files


# ─── STEP 4: YOUTUBE UPLOAD (requires setup) ─────────────────────────────────
def upload_to_youtube(video_path: str) -> bool:
    """
    Uploads video to YouTube using youtube-upload CLI tool.
    Setup: pip install youtube-upload
    Then run: youtube-upload --client-secrets=client_secrets.json to auth once.
    """
    try:
        from youtube_upload import main as yt_upload
    except ImportError:
        return False

    title    = f"You won't believe this... {datetime.now().strftime('%b %d')}"
    desc     = (
        "Watch till the end!\n\n"
        "Daily market signals + trading tools:\n"
        "https://horizons56.gumroad.com\n\n"
        "Edge Engine signals (stocks, crypto, sports):\n"
        "https://buy.stripe.com/cNidR99V6cOfcGv1G86Zy01\n\n"
        "#viral #funny #unexpected #animals #trending"
    )
    tags     = "viral,funny,animals,trending,unexpected,reaction"
    category = "22"  # People & Blogs

    cmd = [
        sys.executable, "-m", "youtube_upload",
        "--title", title,
        "--description", desc,
        "--tags", tags,
        "--category", category,
        "--privacy", "public",
        video_path,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            video_id = result.stdout.strip().split()[-1]
            print(f"  [YT] Uploaded: https://youtube.com/watch?v={video_id}")
            # Move to posted
            posted_path = os.path.join(POSTED, os.path.basename(video_path))
            os.rename(video_path, posted_path)
            with open(LOG_FILE, "a") as f:
                f.write(f"{datetime.now()} | {os.path.basename(video_path)} | {video_id}\n")
            return True
        else:
            print(f"  [YT] Upload failed: {result.stderr[:200]}")
            return False
    except Exception as e:
        print(f"  [YT] Error: {e}")
        return False


def run():
    print("=" * 50)
    print("  GHE VIDEO PIPELINE")
    print("=" * 50)

    fetch_clips()
    process_clips()
    files = report_ready()

    if not files:
        print("\n[DONE] No videos ready yet. Run again after ffmpeg processes clips.")
        return

    # Upload up to 4 videos per day
    uploaded = 0
    for video_path in files[:4]:
        print(f"\n[UPLOAD] {os.path.basename(video_path)}")
        if YOUTUBE_CLIENT_ID:
            success = upload_to_youtube(video_path)
            if success:
                uploaded += 1
                time.sleep(5)
        else:
            print("  [MANUAL] No YouTube credentials — video is ready in READY_TO_UPLOAD folder")

    print(f"\n{'='*50}")
    print(f"  DONE — {len(files)} clips ready, {uploaded} uploaded")
    print(f"  Folder: {READY}")
    print(f"{'='*50}")


if __name__ == "__main__":
    run()
