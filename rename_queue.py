import os

QUEUE_FOLDER = "D:/viral_clips/QUEUE"

os.makedirs(QUEUE_FOLDER, exist_ok=True)

def rank_video(filename):
    name = filename.lower()
    score = 0

    if "chimp" in name or "monkey" in name:
        score += 6
    if "funny" in name:
        score += 5
    if "reaction" in name:
        score += 4
    if "cat" in name:
        score += 5
    if "baby" in name:
        score += 4
    if "unexpected" in name:
        score += 3
    if "staring" in name:
        score -= 2

    return score


def rename_queue():
    files = [f for f in os.listdir(QUEUE_FOLDER) if f.endswith(".mp4")]

    # remove old numbering if rerun
    cleaned = []
    for f in files:
        if f[0:2].isdigit() and "_" in f:
            cleaned_name = f.split("_", 1)[1]
            os.rename(
                os.path.join(QUEUE_FOLDER, f),
                os.path.join(QUEUE_FOLDER, cleaned_name)
            )
            cleaned.append(cleaned_name)
        else:
            cleaned.append(f)

    # rank
    ranked = sorted(cleaned, key=lambda x: rank_video(x), reverse=True)

    # rename with numbers
    for i, f in enumerate(ranked, start=1):
        new_name = f"{i:02d}_{f}"
        src = os.path.join(QUEUE_FOLDER, f)
        dst = os.path.join(QUEUE_FOLDER, new_name)
        os.rename(src, dst)

    print(f"\n[QUEUE SORTED + RENAMED] {len(ranked)} files ready\n")


if __name__ == "__main__":
    rename_queue()
