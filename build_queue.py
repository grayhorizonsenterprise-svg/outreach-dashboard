import os
import shutil

READY = "D:/viral_clips/READY_TO_UPLOAD"
QUEUE = "D:/viral_clips/QUEUE"
POSTED = "D:/viral_clips/POSTED"
BATCH_SIZE = 20

os.makedirs(QUEUE, exist_ok=True)
os.makedirs(POSTED, exist_ok=True)

def extract_id(filename):
    parts = filename.split("_")
    for p in parts:
        if p.isdigit():
            return p
    return None

def get_posted_ids():
    ids = set()
    for f in os.listdir(POSTED):
        vid = extract_id(f)
        if vid:
            ids.add(vid)
    return ids

def rank_video(name):
    n = name.lower()
    score = 0
    if "chimp" in n or "monkey" in n: score += 6
    if "funny" in n: score += 5
    if "reaction" in n: score += 4
    if "cat" in n: score += 5
    if "baby" in n: score += 4
    if "unexpected" in n: score += 3
    if "staring" in n: score -= 2
    return score

def build_queue():
    posted_ids = get_posted_ids()

    files = [f for f in os.listdir(READY) if f.endswith(".mp4")]

    # filter out already posted
    files = [f for f in files if extract_id(f) not in posted_ids]

    # rank best first
    ranked = sorted(files, key=lambda x: rank_video(x), reverse=True)

    selected = ranked[:BATCH_SIZE]

    # clear old queue
    for f in os.listdir(QUEUE):
        os.remove(os.path.join(QUEUE, f))

    # move + rename
    for i, f in enumerate(selected, start=1):
        new_name = f"{i:02d}_{f}"
        shutil.move(
            os.path.join(READY, f),
            os.path.join(QUEUE, new_name)
        )

    print(f"\n[QUEUE READY] {len(selected)} clips ready to post\n")

if __name__ == "__main__":
    build_queue()
