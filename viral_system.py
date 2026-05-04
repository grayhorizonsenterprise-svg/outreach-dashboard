"""
Gray Horizons Enterprise — Viral Video Engine
Single entry point: python viral_system.py
Fetch -> Motion Score -> MoviePy Render -> Metadata -> READY_TO_UPLOAD
"""

import os
import random
import shutil
import requests
import cv2
import numpy as np
from pathlib import Path
from moviepy.editor import (
    VideoFileClip, TextClip, CompositeVideoClip, vfx
)
from metadata_engine import generate_metadata, reset_batch

# =========================
# CONFIG (override via .env or env vars)
# =========================
BASE   = Path(os.getenv("VIRAL_BASE", "D:/viral_clips"))
RAW    = BASE / "raw_clips"
READY  = BASE / "READY_TO_UPLOAD"
POSTED = BASE / "POSTED"
AUDIO  = BASE / "audio"

for d in [RAW, READY, POSTED, AUDIO]:
    d.mkdir(parents=True, exist_ok=True)

PEXELS_API_KEY = os.getenv(
    "PEXELS_API_KEY",
    "rXkLTBGB7aSmfUjKO9p6zG1M89q4rLTztbrxs5ganSZLf03pu0t1YhJ7"
)
HEADERS = {"Authorization": PEXELS_API_KEY}

DAILY_UPLOADS  = 4
BUFFER_DAYS    = 14
TARGET_CLIPS   = DAILY_UPLOADS * BUFFER_DAYS  # 56
CLIP_LENGTH    = 8  # seconds per short

SEARCH_TERMS = [
    "animal funny reaction",
    "animal unexpected behavior",
    "monkey human behavior",
    "animal interaction",
    "baby animals cute",
    "cat fail",
    "dog zoomies",
    "chimp interaction",
    "wildlife strange behavior",
    "bird funny moment",
    "animal surprise reaction",
    "pet funny moment",
]

# =========================
# CAPTIONS (by mood)
# =========================
CAPTIONS = {
    "suspense": [
        "nobody taught it that",
        "the pause before it decided",
        "it knew before we did",
        "this behavior hasn't been documented",
        "the moment it understood what was happening",
        "something changed in its eyes right here",
        "i don't think it realized we were watching",
        "it made a decision and then looked at me",
    ],
    "funny": [
        "bro said absolutely not",
        "the audacity actually",
        "i was not prepared for this at all",
        "it knew exactly what it was doing",
        "i replayed this 6 times",
        "the confidence is sending me",
        "it had a full reaction and i felt that",
        "no because why did it do that",
    ],
    "cute": [
        "the way it waited for her",
        "nobody told it love looked like this",
        "i cried and i'm not embarrassed",
        "it does this every single day without fail",
        "the look it gives at the very end",
        "animals don't lie about how they feel",
        "i wasn't ready for how it ended",
    ],
    "ambient": [
        "something felt off the entire time",
        "i can't stop thinking about this one",
        "this is what they don't show you",
        "it happened so fast i almost missed it",
        "why did it do that and then just stop",
        "this one stayed with me longer than it should",
        "i watched this five times and still",
        "this isn't normal behavior",
    ],
}


def detect_mood(filename: str) -> str:
    n = filename.lower()
    if any(k in n for k in ["chimp", "monkey", "wildlife", "unexpected"]):
        return "suspense"
    if any(k in n for k in ["funny", "cat", "fail", "zoom", "zoomies", "reaction"]):
        return "funny"
    if any(k in n for k in ["baby", "cute", "puppy", "kitten"]):
        return "cute"
    return "ambient"


# =========================
# TRACKING
# =========================
def get_posted_ids() -> set:
    ids = set()
    if POSTED.exists():
        for f in POSTED.iterdir():
            for part in f.stem.split("_"):
                if part.isdigit():
                    ids.add(part)
    return ids


def get_existing_ids() -> set:
    ids = set()
    for folder in [RAW, READY, POSTED]:
        if folder.exists():
            for f in folder.iterdir():
                if f.suffix.lower() == ".mp4":
                    ids.add(f.stem.split("_")[0])
    return ids


def ready_count() -> int:
    if not READY.exists():
        return 0
    return len([f for f in READY.iterdir() if f.suffix.lower() == ".mp4"])


# =========================
# STEP 1: FETCH FROM PEXELS
# =========================
def score_clip(video: dict) -> int:
    duration = video.get("duration", 0)
    if not (4 <= duration <= 25):
        return -1
    score = 0
    if duration < 10:
        score += 3
    elif duration < 15:
        score += 1
    files = video.get("video_files", [])
    if files:
        width = max(f.get("width", 0) for f in files)
        if width >= 1920:
            score += 2
        elif width >= 1280:
            score += 1
    url = video.get("url", "").lower()
    for kw in ["funny", "reaction", "fail", "unexpected", "interaction"]:
        if kw in url:
            score += 1
    return score


def fetch_clips():
    current = ready_count()
    needed  = max(TARGET_CLIPS - current, 0)
    print(f"\n[FETCH] Buffer: {current}/{TARGET_CLIPS} clips | Need: {needed}")

    if needed == 0:
        print("[FETCH] Buffer full — nothing to download today.")
        return

    seen  = get_existing_ids()
    total = 0

    for term in SEARCH_TERMS:
        if total >= needed:
            break
        url  = f"https://api.pexels.com/videos/search?query={term}&per_page=12"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"  [API ERR] '{term}': HTTP {resp.status_code}")
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
            best     = max(files, key=lambda x: x.get("width", 0))
            out_path = RAW / f"{vid_id}_s{score}.mp4"
            try:
                with requests.get(best["link"], stream=True, timeout=30) as r:
                    r.raise_for_status()
                    with open(out_path, "wb") as fh:
                        for chunk in r.iter_content(8192):
                            fh.write(chunk)
                print(f"  [DL] {out_path.name}  (score {score})")
                seen.add(vid_id)
                total += 1
            except Exception as e:
                print(f"  [FAIL DL] {vid_id}: {e}")

    print(f"[FETCH] {total} new clips downloaded → {RAW}")


# =========================
# STEP 2: FIND BEST SEGMENT (motion analysis)
# =========================
def find_best_start(video_path: Path, clip_len: int = CLIP_LENGTH) -> float:
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    scores = []
    prev = None
    frame_i = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if prev is not None:
            diff = cv2.absdiff(prev, gray)
            scores.append((frame_i, float(diff.mean())))
        prev = gray
        frame_i += 1

    cap.release()

    if not scores:
        return 0.0

    best_frame  = max(scores, key=lambda x: x[1])[0]
    total_secs  = frame_i / fps
    start_sec   = max(0.0, best_frame / fps - 2.0)
    max_start   = max(0.0, total_secs - clip_len)
    return min(start_sec, max_start)


# =========================
# STEP 3: MOVIEPY RENDER
# zoom + caption text → 1080×1920 portrait
# =========================
def render_clip(input_path: Path, output_path: Path, mood: str = "ambient") -> bool:
    caption_text = random.choice(CAPTIONS.get(mood, CAPTIONS["ambient"]))

    try:
        start = find_best_start(input_path)

        raw_clip = VideoFileClip(str(input_path)).subclip(start, start + CLIP_LENGTH)

        # Scale to fill 9:16 portrait (crop width if needed)
        clip = raw_clip.resize(height=1920)
        w, h = clip.size
        if w > 1080:
            x_center = w // 2
            clip = clip.crop(x1=x_center - 540, x2=x_center + 540)
        clip = clip.resize((1080, 1920))

        # Subtle zoom-in effect (grows 2% over the clip duration)
        clip = clip.fx(vfx.resize, lambda t: 1 + 0.02 * t)
        # Re-crop after zoom to keep 1080×1920
        clip = clip.crop(x_center=540, y_center=960, width=1080, height=1920)

        # Caption text — bottom third
        txt = (
            TextClip(
                caption_text,
                fontsize=62,
                color="white",
                stroke_color="black",
                stroke_width=3,
                font="Arial-Bold",
                method="caption",
                size=(960, None),
            )
            .set_position(("center", 1580))
            .set_duration(clip.duration)
        )

        final = CompositeVideoClip([clip, txt], size=(1080, 1920))
        final.write_videofile(
            str(output_path),
            fps=30,
            codec="libx264",
            audio_codec="aac",
            preset="fast",
            threads=4,
            logger=None,
        )
        final.close()
        raw_clip.close()
        return True

    except Exception as e:
        print(f"  [RENDER FAIL] {input_path.name}: {e}")
        try:
            output_path.unlink(missing_ok=True)
        except Exception:
            pass
        return False


# =========================
# STEP 4: EDIT ALL RAW CLIPS
# =========================
def edit_clips():
    posted_ids = get_posted_ids()
    raw_files  = sorted([f for f in RAW.iterdir() if f.suffix.lower() == ".mp4"])
    done       = 0

    print(f"\n[EDIT] Processing {len(raw_files)} raw clips...")

    for f in raw_files:
        vid_id = f.stem.split("_")[0]

        if vid_id in posted_ids:
            print(f"  [SKIP] Already posted: {f.name}")
            continue

        out_name = f"ready_{f.stem}.mp4"
        out_path = READY / out_name

        if out_path.exists():
            continue

        mood = detect_mood(f.name)
        print(f"  [RENDER] {f.name}  mood={mood}")

        success = render_clip(f, out_path, mood)

        if success:
            # Save title / description / pinned comment alongside the video
            title, desc, pin = generate_metadata(f.name)
            meta_path = out_path.with_suffix(".txt")
            with open(meta_path, "w", encoding="utf-8") as mf:
                mf.write(
                    f"TITLE:\n{title}\n\n"
                    f"DESCRIPTION:\n{desc}\n\n"
                    f"PINNED COMMENT:\n{pin}\n"
                )
            print(f"    → READY: {out_name}")
            print(f"    → META:  {meta_path.name}")
            done += 1

    print(f"\n[EDIT] {done} clips ready → {READY}")


# =========================
# STEP 5: MARK AS POSTED
# Call this AFTER you upload a batch to TikTok / YouTube Shorts
# =========================
def mark_posted(filename: str):
    src = READY / filename
    dst = POSTED / filename
    if src.exists():
        shutil.move(str(src), str(dst))
        meta = src.with_suffix(".txt")
        if meta.exists():
            shutil.move(str(meta), str(POSTED / meta.name))
        print(f"[POSTED] {filename}")


# =========================
# MAIN
# =========================
def main():
    print("\n" + "=" * 55)
    print("  VIRAL VIDEO ENGINE — GRAY HORIZONS ENTERPRISE")
    print("=" * 55)

    reset_batch()
    fetch_clips()
    edit_clips()

    final_count = ready_count()
    print(f"\n[DONE] {final_count} clips in READY_TO_UPLOAD")
    print(f"       {READY}")
    print("=" * 55)


if __name__ == "__main__":
    main()
