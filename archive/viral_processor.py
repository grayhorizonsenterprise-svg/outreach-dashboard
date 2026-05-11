import os, subprocess, shutil, random
from metadata_engine import generate_metadata, reset_batch

BASE  = "D:/viral_clips"
RAW   = f"{BASE}/raw_clips"
READY = f"{BASE}/READY_TO_UPLOAD"
QUEUE = f"{BASE}/QUEUE"

FONT = "C\\:/Windows/Fonts/arial.ttf"

os.makedirs(READY, exist_ok=True)
os.makedirs(QUEUE, exist_ok=True)

# ---------- SCORE SYSTEM ----------
def score(name):
    n = name.lower()
    s = 1  # base score so clips pass

    # strong signals
    if "fail"     in n: s += 4
    if "zoom"     in n or "dog"    in n: s += 3
    if "reaction" in n: s += 3
    if "chimp"    in n or "monkey" in n: s += 2
    if "jump"     in n or "attack" in n: s += 3

    # mid signals
    if "cat" in n or "animal" in n or "baby" in n:
        s += 1

    # only kill truly bad clips
    if any(x in n for x in ["idle", "blank"]):
        s = -1

    return s

# ---------- CAPTIONS ----------
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
            "that energy spike was crazy… 😳",
            "the shift happened so fast… 😳",
        ])

    if "chimp" in n or "monkey" in n:
        return random.choice([
            "that pause wasn't random… 😳",
            "this felt way too human… 😳",
            "it reacted before anything happened… 😳",
            "nobody taught it that… 😳",
            "it knew before we did… 😳",
        ])

    if "reaction" in n:
        return random.choice([
            "this is where it changes… 😳",
            "you saw that shift right??",
            "that moment wasn't normal… 😳",
            "the pause before it decided… 😳",
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
        "something changed in its eyes right here… 😳",
        "it made a decision and then it looked at me… 😳",
        "animals don't lie about how they feel… 😭",
        "i've never seen an animal do this unprompted… 😳",
        "this one stayed with me longer than it should have… 😳",
    ])

# ---------- BUILD QUEUE ----------
def build_queue(processed):
    # clear old queue
    for f in os.listdir(QUEUE):
        os.remove(os.path.join(QUEUE, f))

    print("\nBUILDING QUEUE...\n")

    for i, (file, s) in enumerate(processed):
        src      = os.path.join(READY, file)
        dst_name = f"{str(i+1).zfill(2)}_score{s}_{file}"
        dst      = os.path.join(QUEUE, dst_name)

        shutil.copy(src, dst)
        print(f"QUEUED #{i+1}: {dst_name}")

    print(f"\nQUEUE READY — {len(processed)} clips\n")

# ---------- PROCESS ----------
def process():
    reset_batch()
    clips = []

    for f in os.listdir(RAW):
        if not f.endswith(".mp4"):
            continue
        s = score(f)
        if s < 0:
            print("REJECTED:", f)
            continue
        clips.append((f, s))

    # sort highest score first
    clips.sort(key=lambda x: x[1], reverse=True)

    # take top 10
    top = clips[:10]

    print(f"\nSELECTED {len(top)} CLIPS\n")

    processed = []

    for i, (file, s) in enumerate(top):
        inp = os.path.join(RAW, file)
        out = os.path.join(READY, f"edit_{file}")

        if os.path.exists(out):
            processed.append((f"edit_{file}", s))
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

        cmd = [
            "ffmpeg", "-y",
            "-i", inp,
            "-t", "8",
            "-vf", vf,
            "-af", "volume=0.3",
            "-c:a", "aac",
            "-b:a", "128k",
            out
        ]

        print(f"PROCESSING {i+1}/10:", file)

        try:
            subprocess.run(cmd, check=True)
            processed.append((f"edit_{file}", s))
            print("DONE:", file)
            title, desc, pin = generate_metadata(file)
            meta = out.replace(".mp4", ".txt")
            with open(meta, "w", encoding="utf-8") as mf:
                mf.write(f"TITLE:\n{title}\n\nDESCRIPTION:\n{desc}\n\nPINNED COMMENT:\n{pin}\n")
        except Exception as e:
            print("FAILED:", file)
            print(e)

    # build final queue from processed clips
    build_queue(processed)

# ---------- RUN ----------
if __name__ == "__main__":
    process()
