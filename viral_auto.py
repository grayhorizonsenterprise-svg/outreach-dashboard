import requests
import os
import subprocess
import shutil
import cv2
import numpy as np
from pathlib import Path
from datetime import datetime

# =========================
# !! PASTE YOUR API KEY BELOW !!
# =========================
PEXELS_API_KEY = "rXkLTBGB7aSmfUjKO9p6zG1M89q4rLTztbrxs5ganSZLf03pu0t1YhJ7"
# =========================

# =========================
# FOLDER CONFIG
# =========================
BASE_DIR     = Path("D:/viral_clips")
INCOMING     = BASE_DIR / "incoming"
APPROVED     = BASE_DIR / "approved"
REJECTED     = BASE_DIR / "rejected"
READY        = BASE_DIR / "READY_TO_UPLOAD"
LOG_FILE     = BASE_DIR / "pipeline_log.txt"

for folder in [INCOMING, APPROVED, REJECTED, READY]:
    folder.mkdir(parents=True, exist_ok=True)

# =========================
# BUFFER CONFIG
# =========================
DAILY_UPLOAD_AVG = 4
BUFFER_DAYS      = 14
TARGET_CLIPS     = DAILY_UPLOAD_AVG * BUFFER_DAYS  # 56

# =========================
# FETCH CONFIG
# =========================
HEADERS = {"Authorization": PEXELS_API_KEY}

SEARCH_TERMS = [
    "animal funny reaction",
    "animal unexpected behavior",
    "monkey human behavior",
    "animal interaction",
    "baby animals cute",
    "cat fail",
    "dog zoomies",
    "chimp interaction"
]

PER_QUERY    = 8
MIN_DURATION = 5
MAX_DURATION = 20

# =========================
# FILTER CONFIG
# =========================
MOTION_THRESHOLD = 500000  # tune up to reject more, down to accept more

# =========================
# TRIM + EDIT CONFIG
# =========================
TRIM_START  = 0.2
TRIM_LENGTH = 6

CAPTIONS = [
    "why did it do THAT at the end",
    "wait for the reaction...",
    "this got weird fast",
    "i was NOT expecting that",
    "watch the eyes...",
    "this changed instantly",
    "something feels off here",
]

# =========================
# LOGGING
# =========================
def log(msg):
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] {msg}"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line)

# =========================
# FFMPEG CHECK
# =========================
def check_ffmpeg():
    if shutil.which("ffmpeg") is None:
        log("ERROR: ffmpeg not found. Run: winget install ffmpeg  -- then restart.")
        return False
    return True

# =========================
# BUFFER CHECK
# =========================
def ready_count():
    return len([f for f in READY.iterdir() if f.suffix.lower() == ".mp4"])

def existing_ids():
    ids = set()
    for folder in [INCOMING, APPROVED, READY]:
        for f in folder.iterdir():
            if f.suffix.lower() == ".mp4":
                ids.add(f.stem.split("_")[0])
    return ids

# =========================
# SCORING
# =========================
def score_clip(video):
    score = 0
    duration = video.get("duration", 0)
    if not (MIN_DURATION <= duration <= MAX_DURATION):
        return -1
    if duration < 10:
        score += 3
    elif duration < 20:
        score += 2
    files = video.get("video_files", [])
    if files:
        width = max(f.get("width", 0) for f in files)
        if width >= 1920:
            score += 2
    return score

# =========================
# STEP 1: FETCH FROM PEXELS
# =========================
def fetch_clips(needed):
    log(f"FETCH: Need {needed} clips from Pexels")
    seen = existing_ids()
    total = 0

    for term in SEARCH_TERMS:
        if total >= needed:
            break

        url = f"https://api.pexels.com/videos/search?query={term}&per_page={PER_QUERY}"
        resp = requests.get(url, headers=HEADERS)
        if resp.status_code != 200:
            log(f"  API error on '{term}': {resp.status_code}")
            continue

        for video in resp.json().get("videos", []):
            if total >= needed:
                break

            vid_id = str(video["id"])
            if vid_id in seen:
                continue

            score = score_clip(video)
            if score < 0:
                continue

            files = video.get("video_files", [])
            if not files:
                continue

            best = max(files, key=lambda x: x.get("width", 0))
            out_path = INCOMING / f"{vid_id}_score{score}.mp4"

            try:
                with requests.get(best["link"], stream=True, timeout=30) as r:
                    r.raise_for_status()
                    with open(out_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                log(f"  Downloaded: {out_path.name}")
                seen.add(vid_id)
                total += 1
            except Exception as e:
                log(f"  Failed download {vid_id}: {e}")

    log(f"FETCH: Done - {total} clips downloaded to incoming")
    return total

# =========================
# STEP 2: FILTER (motion analysis)
# =========================
def motion_score(video_path):
    cap = cv2.VideoCapture(str(video_path))
    frames = []
    count = 0

    while count < 15:
        ret, frame = cap.read()
        if not ret:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frames.append(gray)
        count += 1

    cap.release()

    if len(frames) < 2:
        return 0

    diffs = [np.sum(cv2.absdiff(frames[i], frames[i - 1])) for i in range(1, len(frames))]
    return np.mean(diffs)

def get_pexels_score(file_path):
    # score is embedded in filename: 36383997_score3.mp4
    try:
        return int(file_path.stem.split("score")[-1])
    except (ValueError, IndexError):
        return 0

def is_high_quality(video_path):
    m_score = motion_score(video_path)
    p_score = get_pexels_score(video_path)

    if m_score > MOTION_THRESHOLD and p_score > 1:
        return True, m_score, p_score
    return False, m_score, p_score

def filter_clips():
    files = [f for f in INCOMING.iterdir() if f.suffix.lower() == ".mp4"]
    approved = []

    for f in files:
        valid, m_score, p_score = is_high_quality(f)
        if not valid:
            f.rename(REJECTED / f.name)
            log(f"  Rejected (motion={int(m_score)}, pexels={p_score}): {f.name}")
            continue
        approved_path = APPROVED / f.name
        f.rename(approved_path)
        log(f"  Approved (motion={int(m_score)}, pexels={p_score}): {f.name}")
        approved.append(approved_path)

    log(f"FILTER: {len(approved)} clips approved")
    return approved

# =========================
# STEP 3: TRIM + SCALE + CAPTION -> READY_TO_UPLOAD
# =========================
def edit_video(input_path, output_path):
    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-t", "6",
        "-vf", "scale=1080:1920",
        "-c:a", "copy",
        str(output_path)
    ]

    try:
        subprocess.run(cmd, check=True)
        log(f"  [OK] Edited: {os.path.basename(str(input_path))}")
        return True
    except subprocess.CalledProcessError:
        log(f"  [FAIL] Edit failed: {os.path.basename(str(input_path))}")
        return False

def edit_clips(approved_files):
    ready = 0
    for clip in approved_files:
        out_name = f"ready_{clip.stem}.mp4"
        out_path = READY / out_name

        if out_path.exists():
            log(f"  Already exists: {out_name}")
            continue

        if edit_video(clip, out_path):
            ready += 1

    log(f"EDIT: {ready} clips moved to READY_TO_UPLOAD")
    return ready

# =========================
# MAIN
# =========================
def main():
    log("=" * 50)
    log("VIRAL AUTO PIPELINE - STARTING")
    log("=" * 50)

    if not check_ffmpeg():
        return

    current = ready_count()
    needed  = max(TARGET_CLIPS - current, 0)
    log(f"BUFFER: {current} ready | Target: {TARGET_CLIPS} | Need: {needed}")

    if needed == 0:
        log("Buffer full. Nothing to do today.")
        log("=" * 50)
        return

    fetch_clips(needed)
    approved = filter_clips()
    edit_clips(approved)

    final = ready_count()
    log(f"PIPELINE COMPLETE: {final} clips in READY_TO_UPLOAD")
    log("=" * 50)

if __name__ == "__main__":
    main()
