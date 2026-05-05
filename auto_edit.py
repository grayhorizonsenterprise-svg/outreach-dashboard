import subprocess
import os
import random

# =========================
# CONFIG
# =========================
INPUT_PATH  = r"D:/viral_clips"
OUTPUT_PATH = r"D:/viral_clips/READY_TO_UPLOAD"

os.makedirs(OUTPUT_PATH, exist_ok=True)

# =========================
# CAPTIONS
# =========================
hooks = [
    "nobody taught it that",
    "the pause before it decided",
    "it knew before we did",
    "it looked back exactly once",
    "something changed in its eyes right here",
    "i don't think it realized we were watching",
    "this is the part that got me",
    "bro said absolutely not",
    "the audacity actually",
    "i was not prepared for this at all",
    "it looked at the camera like it knew",
    "no because why did it do that",
    "i replayed this 6 times",
    "the way it waited for her",
    "it chose to stay every single time",
    "i wasn't ready for how it ended",
    "animals don't lie about how they feel",
    "something felt off the entire time",
    "i can't stop thinking about this one",
    "it happened so fast i almost missed it",
    "the moment right before everything changed",
    "something about this doesn't sit right and i need answers",
    "this one stayed with me longer than it should have",
    "it made a decision and then it looked at me",
    "the confidence is sending me",
]

# =========================
# EDIT FUNCTION
# =========================
AUDIO_DIR = "D:/viral_clips/audio"

def edit_video(input_path, output_path):
    hook = random.choice(hooks).replace(":", "\\:").replace("'", "\\'")

    audio_files = [f for f in os.listdir(AUDIO_DIR) if f.endswith(".mp3")]
    audio_file  = os.path.join(AUDIO_DIR, random.choice(audio_files)) if audio_files else None

    if audio_file:
        fc = (
            f"[0:v]scale=1080:1920,drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':"
            f"text={hook}:fontcolor=white:fontsize=60:borderw=3:bordercolor=black:"
            "x=(w-text_w)/2:y=h-250[v];"
            "[0:a]volume=0.6[a0];"
            "[1:a]volume=0.3[a1];"
            "[a0][a1]amix=inputs=2:duration=shortest[a]"
        )
        cmd = (
            f'ffmpeg -y -i "{input_path}" -i "{audio_file}"'
            f' -t 8'
            f' -filter_complex "{fc}"'
            f' -map "[v]" -map "[a]" -c:a aac -b:a 128k -shortest "{output_path}"'
        )
    else:
        fc_v = (
            f"[0:v]scale=1080:1920,drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':"
            f"text={hook}:fontcolor=white:fontsize=60:borderw=3:bordercolor=black:"
            "x=(w-text_w)/2:y=h-250[v]"
        )
        cmd = (
            f'ffmpeg -y -i "{input_path}"'
            f' -f lavfi -i anullsrc=channel_layout=stereo:sample_rate=44100'
            f' -t 8'
            f' -filter_complex "{fc_v}"'
            f' -map "[v]" -map 1:a -c:a aac -b:a 128k -shortest "{output_path}"'
        )

    try:
        subprocess.run(cmd, shell=True, check=True)
        print(f"[OK] Edited: {os.path.basename(input_path)}")
        return True
    except subprocess.CalledProcessError:
        print(f"[FAIL] Edit failed: {os.path.basename(input_path)}")
        return False

# =========================
# PROCESS ALL
# =========================
def process_all():
    for file in os.listdir(INPUT_PATH):
        if file.endswith(".mp4"):
            input_file  = os.path.join(INPUT_PATH, file)
            output_file = os.path.join(OUTPUT_PATH, "edit_" + file)

            if os.path.exists(output_file):
                continue

            print(f"[>>] Editing: {file}")
            edit_video(input_file, output_file)

# =========================
# MAIN
# =========================
def main():
    print("=== AUTO EDIT START ===")
    process_all()
    print("=== DONE ===")

if __name__ == "__main__":
    main()
