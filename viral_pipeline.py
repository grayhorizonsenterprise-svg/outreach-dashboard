import os
import subprocess
from pathlib import Path

# =========================
# CONFIG
# =========================
BASE_DIR = Path("D:/viral_clips")

INCOMING = BASE_DIR / "incoming"
APPROVED = BASE_DIR / "approved"
REJECTED = BASE_DIR / "rejected"
READY = BASE_DIR / "READY_TO_UPLOAD"
LOG_FILE = BASE_DIR / "process_log.txt"

VIDEO_EXTENSIONS = [".mp4", ".mov", ".mkv"]

# =========================
# ENSURE FOLDERS EXIST
# =========================
for folder in [INCOMING, APPROVED, REJECTED, READY]:
    folder.mkdir(parents=True, exist_ok=True)

# =========================
# LOGGING
# =========================
def log(message):
    with open(LOG_FILE, "a") as f:
        f.write(message + "\n")
    print(message)

# =========================
# BASIC FILTER (FAST)
# =========================
def is_valid_clip(file_path):
    name = file_path.name.lower()

    reject_keywords = ["ai", "render", "generated", "fake"]
    if any(k in name for k in reject_keywords):
        return False, "Rejected: AI-like filename"

    allow_keywords = ["fail", "zoom", "chimp", "dog", "cat"]
    if any(k in name for k in allow_keywords):
        return True, "Approved: keyword match"

    return True, "Approved: default"

# =========================
# TRIM CLIP (FFMPEG)
# =========================
def trim_clip(input_path, output_path):
    cmd = [
        "ffmpeg",
        "-y",
        "-ss", "0.2",
        "-i", str(input_path),
        "-t", "3.5",
        "-c", "copy",
        str(output_path)
    ]

    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        log(f"ERROR trimming {input_path.name}: {e}")
        return False

# =========================
# MAIN PROCESS
# =========================
def process_clips():
    files = [f for f in INCOMING.iterdir() if f.suffix.lower() in VIDEO_EXTENSIONS]

    if not files:
        log("No clips found in incoming folder.")
        return

    for file in files:
        valid, reason = is_valid_clip(file)

        if not valid:
            target = REJECTED / file.name
            file.rename(target)
            log(f"{file.name} -> REJECTED ({reason})")
            continue

        approved_path = APPROVED / file.name
        file.rename(approved_path)
        log(f"{file.name} -> APPROVED")

        output_name = f"ready_{file.stem}.mp4"
        output_path = READY / output_name

        success = trim_clip(approved_path, output_path)

        if success:
            log(f"{output_name} -> READY (trimmed)")
        else:
            log(f"{file.name} -> FAILED TRIM")

# =========================
# RUN
# =========================
if __name__ == "__main__":
    log("---- RUNNING VIRAL PIPELINE ----")
    process_clips()
    log("---- DONE ----")
