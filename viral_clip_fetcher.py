import requests
import os

# =========================
# CONFIG
# =========================
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "rXkLTBGB7aSmfUjKO9p6zG1M89q4rLTztbrxs5ganSZLf03pu0t1YhJ7")

BASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "viral_clips")
TOP_PATH  = os.path.join(BASE_PATH, "top_clips")
RAW_PATH  = os.path.join(BASE_PATH, "raw_clips")

os.makedirs(TOP_PATH, exist_ok=True)
os.makedirs(RAW_PATH, exist_ok=True)

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

PER_QUERY = 8

# 14-day buffer: 4 clips/day avg x 14 days = 56
DAILY_UPLOAD_AVG = 4
BUFFER_DAYS = 14
TARGET_CLIPS = DAILY_UPLOAD_AVG * BUFFER_DAYS  # 56

# =========================
# INVENTORY
# =========================
def get_existing_ids():
    ids = set()
    for folder in [TOP_PATH, RAW_PATH]:
        for f in os.listdir(folder):
            if f.endswith(".mp4"):
                ids.add(f.split("_")[0])
    return ids

def get_current_count():
    total = sum(
        len([f for f in os.listdir(folder) if f.endswith(".mp4")])
        for folder in [TOP_PATH, RAW_PATH]
    )
    return total

def clips_needed():
    current = get_current_count()
    needed = TARGET_CLIPS - current
    print(f"[i] Inventory: {current} clips | Target: {TARGET_CLIPS} | Need: {max(needed, 0)}")
    return max(needed, 0)

# =========================
# SCORING SYSTEM
# =========================
def score_clip(video):
    score = 0

    duration = video.get("duration", 0)

    # SHORTER = BETTER
    if duration < 10:
        score += 3
    elif duration < 20:
        score += 2

    # RESOLUTION
    files = video.get("video_files", [])
    if files:
        width = max(f.get("width", 0) for f in files)
        if width >= 1920:
            score += 2

    # KEYWORDS
    url = video.get("url", "").lower()
    keywords = ["funny", "reaction", "weird", "fail", "interaction", "unexpected"]
    for k in keywords:
        if k in url:
            score += 1

    return score

# =========================
# DOWNLOAD FUNCTION (streamed)
# =========================
def download_video(video, score):
    files = video.get("video_files", [])
    if not files:
        return False

    best_file = max(files, key=lambda x: x.get("width", 0))
    video_url = best_file["link"]

    filename = f"{video['id']}_score{score}.mp4"
    path = os.path.join(TOP_PATH if score >= 5 else RAW_PATH, filename)

    try:
        with requests.get(video_url, stream=True, timeout=30) as r:
            r.raise_for_status()
            with open(path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        print(f"[OK] Saved (score {score}): {path}")
        return True
    except Exception as e:
        print(f"[X] Failed: {e}")
        return False

# =========================
# MAIN
# =========================
def main():
    print("\n=== Viral Clip Fetcher - 14-Day Buffer Mode ===\n")
    needed = clips_needed()

    if needed == 0:
        print(f"[✓] Buffer full ({TARGET_CLIPS} clips). Nothing to download today.")
        return

    print(f"[>>] Fetching {needed} clips...\n")
    existing_ids = get_existing_ids()
    total = 0

    for term in SEARCH_TERMS:
        if total >= needed:
            break

        print(f"Searching: {term}")
        url = f"https://api.pexels.com/videos/search?query={term}&per_page={PER_QUERY}"
        response = requests.get(url, headers=HEADERS)
        data = response.json()

        for video in data.get("videos", []):
            if total >= needed:
                break

            vid_id = str(video["id"])
            if vid_id in existing_ids:
                print(f"[=] Already have: {vid_id}")
                continue

            score = score_clip(video)
            if download_video(video, score):
                existing_ids.add(vid_id)
                total += 1

    print(f"\n=== DONE | +{total} new clips | Total: {get_current_count()} | D:/viral_clips ===")

if __name__ == "__main__":
    main()
