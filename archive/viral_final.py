import requests
import os
import random
import subprocess
import shutil
import cv2
from metadata_engine import generate_metadata, reset_batch

# =========================
# CONFIG
# =========================
PEXELS_API_KEY = "PASTE_YOUR_API_KEY_HERE"

BASE = "D:/viral_clips"
RAW = os.path.join(BASE, "raw")
READY = os.path.join(BASE, "READY_TO_UPLOAD")
AUDIO = os.path.join(BASE, "audio")

os.makedirs(RAW, exist_ok=True)
os.makedirs(READY, exist_ok=True)
os.makedirs(AUDIO, exist_ok=True)

HEADERS = {"Authorization": PEXELS_API_KEY}

POSTED_FOLDER = "D:/viral_clips/POSTED"
READY_BATCH   = "D:/viral_clips/READY_BATCH"

os.makedirs(POSTED_FOLDER, exist_ok=True)
os.makedirs(READY_BATCH, exist_ok=True)

def get_posted_ids():
    if not os.path.exists(POSTED_FOLDER):
        return set()
    ids = set()
    for f in os.listdir(POSTED_FOLDER):
        parts = f.split("_")
        for p in parts:
            if p.isdigit():
                ids.add(p)
    return ids

def extract_id(filename):
    parts = filename.split("_")
    for p in parts:
        if p.isdigit():
            return p
    return None

def should_skip(filename):
    posted_ids = get_posted_ids()
    for part in filename.split("_"):
        if part.isdigit() and part in posted_ids:
            return True
    return False

def move_posted():
    for f in os.listdir(READY_BATCH):
        if f.endswith(".mp4"):
            src = os.path.join(READY_BATCH, f)
            dst = os.path.join(POSTED_FOLDER, f)
            if not os.path.exists(dst):
                shutil.move(src, dst)
    print("[MOVED TO POSTED]")

SEARCH_TERMS = [
    "animal funny reaction",
    "animal unexpected behavior",
    "chimp interaction",
    "dog zoomies",
    "cat fail",
    "wildlife strange behavior"
]

PER_QUERY = 6

FONT    = "C\\\\:/Windows/Fonts/arial.ttf"
SFX_POP = os.path.join(AUDIO, "sfx_pop.mp3")

CAPTIONS = {
    "suspense": [
        "nobody taught it that",
        "the pause before it decided",
        "it knew before we did",
        "it looked back exactly once",
        "something changed in its eyes right here",
        "i don't think it realized we were watching",
        "this is the part that got me",
        "i've never seen an animal do this unprompted",
        "the way it looked at him after",
        "it made a decision and then it looked at me",
        "this behavior hasn't been documented the way you think",
        "the moment it understood what was happening",
    ],
    "funny": [
        "bro said absolutely not",
        "the audacity actually",
        "i was not prepared for this at all",
        "it looked at the camera like it knew",
        "no because why did it do that",
        "the way it just decided to do that",
        "i replayed this 6 times",
        "it had a full reaction and i felt that",
        "the confidence is sending me",
        "bro looked at me and chose violence",
        "it knew exactly what it was doing",
        "this is the funniest thing i have ever seen an animal do",
    ],
    "cute": [
        "the way it waited for her",
        "it chose to stay every single time",
        "i wasn't ready for how it ended",
        "nobody told it love looked like this",
        "it does this every single day without fail",
        "the look it gives at the very end",
        "animals don't lie about how they feel",
        "it recognized him after all that time",
        "i cried and i'm not even embarrassed",
        "this is why i don't trust people over animals",
    ],
    "ambient": [
        "something felt off the entire time",
        "i can't stop thinking about this one",
        "this is what they don't show you",
        "it happened so fast i almost missed it",
        "the moment right before everything changed",
        "i watched this five times and still",
        "there's something about this clip i can't shake",
        "why did it do that and then just stop",
        "this one stayed with me longer than it should have",
        "something about this doesn't sit right and i need answers",
    ],
}

MOOD_MAP = {
    "funny":    ["funny", "ambient"],
    "cute":     ["cute", "ambient"],
    "suspense": ["suspense", "ambient"],
    "ambient":  ["ambient", "neutral"],
    "neutral":  ["neutral", "ambient"],
}

def detect_mood(filename):
    n = filename.lower()
    if any(k in n for k in ["chimp", "monkey", "wildlife"]):
        return "suspense"
    if any(k in n for k in ["funny", "cat", "fail", "zoomies"]):
        return "funny"
    if any(k in n for k in ["baby", "cute"]):
        return "cute"
    return "ambient"

def pick_from_folder(folder):
    path = os.path.join(AUDIO, folder)
    if not os.path.exists(path):
        return None
    files = [f for f in os.listdir(path) if f.endswith(".mp3")]
    if not files:
        return None
    return os.path.join(path, random.choice(files))

def get_mix_audio(filename):
    mood = detect_mood(filename)
    folders = MOOD_MAP.get(mood, ["ambient"])
    random.shuffle(folders)
    for folder in folders:
        pick = pick_from_folder(folder)
        if pick:
            return pick
    return None

# =========================
# KEYWORD FILTER
# =========================
def is_valid_clip(filename):
    name = filename.lower()

    # numeric Pexels IDs have no keywords — pass through to motion analysis
    stem = name.replace(".mp4", "")
    if stem.isdigit():
        return True

    # PRIORITY CLIPS (ALLOW)
    if any(x in name for x in [
        "fail", "zoom", "reaction", "unexpected",
        "chimp", "monkey", "jump", "attack", "slip"
    ]):
        return True

    # AUTO REJECT
    if any(x in name for x in [
        "staring", "standing", "walking", "idle", "calm", "slow"
    ]):
        return False

    return False

# =========================
# MOTION FILTER
# =========================
def has_motion_spike(video_path):
    cap = cv2.VideoCapture(video_path)
    prev = None
    motion_score = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        if prev is not None:
            diff = cv2.absdiff(prev, gray)
            score = diff.mean()

            if score > 8:
                motion_score += 1

        prev = gray

    cap.release()
    return motion_score > 5

# =========================
# BEST SEGMENT FINDER
# =========================
def find_best_segment(video_path):
    cap = cv2.VideoCapture(video_path)

    scores = []
    prev = None
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        if prev is not None:
            diff = cv2.absdiff(prev, gray)
            score = diff.mean()
            scores.append((frame_idx, score))

        prev = gray
        frame_idx += 1

    cap.release()

    if not scores:
        return 0

    best_frame = max(scores, key=lambda x: x[1])[0]
    fps = 30
    start_time = max(0, best_frame / fps - 2)

    return start_time

# =========================
# FETCH CLIPS
# =========================
def fetch_clips():
    print("\n=== FETCHING ===")
    for term in SEARCH_TERMS:
        url = f"https://api.pexels.com/videos/search?query={term}&per_page={PER_QUERY}"
        res = requests.get(url, headers=HEADERS).json()

        for vid in res.get("videos", []):
            files = vid.get("video_files", [])
            if not files:
                continue

            best = max(files, key=lambda x: x.get("width", 0))
            link = best["link"]

            filename = f"{vid['id']}.mp4"
            path = os.path.join(RAW, filename)

            if os.path.exists(path):
                continue

            try:
                r = requests.get(link, stream=True)
                with open(path, "wb") as f:
                    for chunk in r.iter_content(8192):
                        f.write(chunk)
                print(f"[OK] {filename}")
            except:
                print("[FAIL DOWNLOAD]")

# =========================
# EDIT CLIPS
# =========================
def edit_clips():
    print("\n=== EDITING ===")

    for file in os.listdir(RAW):
        if not file.endswith(".mp4"):
            continue

        input_path = os.path.join(RAW, file)
        output_path = os.path.join(READY, f"edit_{file}")

        if os.path.exists(output_path):
            continue

        if should_skip(file):
            print(f"[SKIP POSTED] {file}")
            continue

        if not is_valid_clip(file):
            print(f"[SKIP KEYWORD] {file}")
            continue

        if not has_motion_spike(input_path):
            print(f"[SKIP LOW MOTION] {file}")
            continue

        mood       = detect_mood(file)
        caption    = random.choice(CAPTIONS.get(mood, CAPTIONS["ambient"])).replace(":", "\\:").replace("'", "\\'")
        audio_file = get_mix_audio(file)
        start_time = find_best_segment(input_path)

        if audio_file:
            fc = (
                f"[0:v]scale=1080:1920,drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':"
                f"text={caption}:fontcolor=white:fontsize=60:borderw=3:bordercolor=black:"
                "x=(w-text_w)/2:y=h-250[v];"
                "[0:a]volume=0.6[a0];"
                "[1:a]volume=0.3[a1];"
                "[a0][a1]amix=inputs=2:duration=shortest[a]"
            )
            cmd = (
                f'ffmpeg -y -i "{input_path}" -i "{audio_file}"'
                f' -ss {start_time} -t 8'
                f' -filter_complex "{fc}"'
                f' -map "[v]" -map "[a]" -c:a aac -b:a 128k -shortest "{output_path}"'
            )
        else:
            fc_v = (
                f"[0:v]scale=1080:1920,drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':"
                f"text={caption}:fontcolor=white:fontsize=60:borderw=3:bordercolor=black:"
                "x=(w-text_w)/2:y=h-250[v]"
            )
            cmd = (
                f'ffmpeg -y -i "{input_path}"'
                f' -f lavfi -i anullsrc=channel_layout=stereo:sample_rate=44100'
                f' -ss {start_time} -t 8'
                f' -filter_complex "{fc_v}"'
                f' -map "[v]" -map 1:a -c:a aac -b:a 128k -shortest "{output_path}"'
            )

        try:
            subprocess.run(cmd, shell=True, check=True)
            print(f"[EDITED] {file}")
            title, desc, pin = generate_metadata(file)
            meta_path = output_path.replace(".mp4", ".txt")
            with open(meta_path, "w", encoding="utf-8") as mf:
                mf.write(f"TITLE:\n{title}\n\nDESCRIPTION:\n{desc}\n\nPINNED COMMENT:\n{pin}\n")
            print(f"[META] saved → {os.path.basename(meta_path)}")
        except:
            print(f"[FAIL EDIT] {file}")

# =========================
# MAIN
# =========================
def main():
    print("\n=== VIRAL ENGINE START ===\n")

    reset_batch()
    fetch_clips()
    edit_clips()

    print("\n=== DONE ===")
    print(f"READY FOLDER: {READY}")

if __name__ == "__main__":
    main()
    move_posted()
