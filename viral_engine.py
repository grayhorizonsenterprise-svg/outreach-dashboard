import os, random, subprocess, shutil

BASE  = "D:/viral_clips"
RAW   = f"{BASE}/raw_clips"
READY = f"{BASE}/READY_TO_UPLOAD"
QUEUE = f"{BASE}/QUEUE"
POSTED = f"{BASE}/POSTED"
AUDIO = f"{BASE}/audio"

FONT = "C\\:/Windows/Fonts/arial.ttf"

os.makedirs(READY,  exist_ok=True)
os.makedirs(QUEUE,  exist_ok=True)
os.makedirs(POSTED, exist_ok=True)

# ---------- CLIP FILTER ----------
def valid(name):
    n = name.lower()

    # STRONG SIGNAL (always allow)
    if any(x in n for x in ["fail","zoom","reaction","chimp","monkey","jump","attack"]):
        return True

    # MID SIGNAL (allow)
    if any(x in n for x in ["dog","cat","animal","baby","unexpected","funny"]):
        return True

    # ONLY reject obvious dead clips
    if any(x in n for x in ["idle","static","blank"]):
        return False

    # DEFAULT: ALLOW
    return True

# ---------- CAPTION GENERATOR ----------
def caption(name):
    n = name.lower()

    if "fail" in n:
        return random.choice([
            "this is where it goes wrong… 😭",
            "it really thought it had it… 😭",
            "the confidence before this… 😭",
        ])

    if "zoom" in n or "dog" in n:
        return random.choice([
            "it switched up instantly… 😳",
            "why did it move like that… 😳",
            "that energy spike was crazy… 😳",
        ])

    if "chimp" in n or "monkey" in n:
        return random.choice([
            "it reacted before anything happened… 😳",
            "that pause wasn't random… 😳",
            "this felt way too human… 😳",
        ])

    return random.choice([
        "nobody taught it that… 😳",
        "something about this feels off… 😳",
        "this isn't normal behavior… 😳",
        "it knew before we did… 😳",
        "i wasn't ready for how it ended… 😭",
        "the pause before it decided… 😳",
        "i replayed this 6 times… 😳",
        "bro said absolutely not… 😭",
        "i can't stop thinking about this one… 😳",
        "the moment right before everything changed… 😳",
    ])

# ---------- PROCESS ----------
def process():
    for file in os.listdir(RAW):
        if not file.endswith(".mp4"):
            continue
        if not valid(file):
            print("REJECTED:", file)
            continue

        inp  = f"{RAW}/{file}"
        out  = f"{READY}/edit_{file}"

        if os.path.exists(out):
            continue

        text = caption(file).replace(":", "\\:").replace("'", "\\'")

        vf = (
            f"scale=1080:1920,"
            f"drawtext=fontfile='{FONT}':"
            f"text='{text}':"
            f"fontcolor=white:fontsize=60:"
            f"borderw=4:bordercolor=black:"
            f"shadowcolor=black:shadowx=2:shadowy=2:"
            f"x=(w-text_w)/2:y=h-250"
        )

        cmd = f'ffmpeg -y -i "{inp}" -t 8 -vf "{vf}" -af "volume=0.3" -c:a aac -b:a 128k "{out}"'

        try:
            subprocess.run(cmd, shell=True, check=True)
            print("DONE:", file)
        except:
            print("FAILED:", file)

# ---------- BUILD QUEUE ----------
def build_queue():
    posted = set()
    if os.path.exists(POSTED):
        for f in os.listdir(POSTED):
            stem = f.replace(".mp4", "").split("_")[-1]
            posted.add(stem)

    files = [
        f for f in os.listdir(READY)
        if f.endswith(".mp4") and f.replace(".mp4","").split("_")[-1] not in posted
    ]
    files.sort()

    for i, f in enumerate(files[:20]):
        src = f"{READY}/{f}"
        dst = f"{QUEUE}/{str(i+1).zfill(2)}_{f}"
        shutil.copy(src, dst)

    print(f"QUEUE READY — {min(len(files), 20)} clips")

# ---------- RUN ----------
if __name__ == "__main__":
    process()
    build_queue()
