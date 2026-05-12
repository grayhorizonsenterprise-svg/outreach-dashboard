"""
generate_ep001.py — Shadow Clans EP001 Video Builder
Pipeline: AI art frames (Midjourney/SDXL PNGs) + real animal clips
Mobile portrait 1080x1920. Anime flicker only at supernatural scenes.
Drop Midjourney exports into: shadow_clans_output/frames/EP001/
  scene_01.png, scene_02.png ... scene_08.png
Missing frames fall back to a cinematic title card.
"""

import json
import subprocess
import sys
import shutil
import textwrap
from pathlib import Path

DIR        = Path(__file__).parent
SCRIPT     = DIR / "shadow_clans_output" / "frames" / "EP001" / "script.json"
FRAMES_DIR = DIR / "shadow_clans_output" / "frames" / "EP001"
ANIMAL_DIR = DIR / "viral_clips" / "raw_clips"
OUT_DIR    = DIR / "shadow_clans_output" / "episodes"
TEMP_DIR   = DIR / "shadow_clans_output" / "_temp_ep001"

FONT      = r"C\:/Windows/Fonts/arial.ttf"
FONT_BOLD = r"C\:/Windows/Fonts/arialbd.ttf"

W, H = 1080, 1920

OUT_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Scenes that get real animal clips mixed in (nature/live action feel)
ANIMAL_SCENES = {4, 5}   # wolf pack scouts + Raven Order atmosphere

# Scenes that get anime flicker (1-2 frame hue-rotate burst)
FLICKER_SCENES = {7, 8}  # Hollow Gate + child's silver eyes


def fp(path: Path) -> str:
    return str(path)


def esc(text: str) -> str:
    return (text
        .replace("'",  "")
        .replace(":",  " -")
        .replace("[",  "")
        .replace("]",  "")
        .replace("%",  "")
        .replace("\\", "")
    )


def wrap_lines(text: str, width: int = 30) -> str:
    return "\\n".join(textwrap.wrap(text, width))


def run(cmd: list, timeout: int = 120) -> bool:
    r = subprocess.run(cmd, capture_output=True, timeout=timeout)
    if r.returncode != 0:
        print(f"  [FFMPEG ERR] {r.stderr.decode(errors='replace')[-300:]}")
    return r.returncode == 0


def get_duration(path: Path) -> float:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        fp(path),
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return float(r.stdout.strip())
    except Exception:
        return 10.0


# ─── Title Card (pure FFmpeg, no source) ──────────────────────────────────────

def make_title_card(title: str, sub: str, duration: int, out: Path) -> bool:
    t = esc(title)
    s = esc(sub)
    vf = (
        f"drawtext=fontfile='{FONT_BOLD}':text='{t}'"
        f":fontcolor=white:fontsize=86:borderw=3:bordercolor=black"
        f":x=(w-text_w)/2:y=(h/2)-60,"
        f"drawtext=fontfile='{FONT}':text='{s}'"
        f":fontcolor=0xAAAAAA:fontsize=36:borderw=2:bordercolor=black"
        f":x=(w-text_w)/2:y=(h/2)+50"
    )
    return run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=0x060608:s={W}x{H}:r=24",
        "-t", str(duration),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-pix_fmt", "yuv420p", "-r", "24",
        fp(out),
    ], timeout=30)


# ─── Placeholder card when no Midjourney frame exists ─────────────────────────

def make_placeholder(scene_num: int, action: str, duration: int, out: Path) -> bool:
    tag  = esc(f"SCENE {scene_num}")
    desc = esc(wrap_lines(action, 28))
    vf = (
        f"drawtext=fontfile='{FONT}':text='{tag}'"
        f":fontcolor=0x666666:fontsize=32:borderw=1:bordercolor=black"
        f":x=50:y=60,"
        f"drawtext=fontfile='{FONT}':text='{desc}'"
        f":fontcolor=0x999999:fontsize=34:borderw=2:bordercolor=black"
        f":x=(w-text_w)/2:y=(h/2)-80:line_spacing=16,"
        f"drawtext=fontfile='{FONT}':text='[ drop scene_{scene_num:02d}.png here ]'"
        f":fontcolor=0x444444:fontsize=26:borderw=1:bordercolor=black"
        f":x=(w-text_w)/2:y=(h/2)+80"
    )
    return run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=0x080a0c:s={W}x{H}:r=24",
        "-t", str(duration),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-pix_fmt", "yuv420p", "-r", "24",
        fp(out),
    ], timeout=30)


# ─── Still Image → Animated Video (Ken Burns slow zoom) ───────────────────────

def animate_frame(img: Path, duration: int, narration: str,
                  scene_num: int, flicker: bool, out: Path) -> bool:
    narr = esc(wrap_lines(narration, 32))
    tag  = esc(f"SCENE {scene_num}")

    # Ken Burns: slow zoom in from 1.0→1.06 over the clip duration
    zoom_speed = 0.0006
    zoom_vf = (
        f"scale=8000:-1,"
        f"zoompan=z='min(zoom+{zoom_speed},1.06)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        f":d={duration * 24}:s={W}x{H}:fps=24,"
    )

    # Cinematic grade: desaturate 72%, high contrast, slight darken
    grade = "eq=saturation=0.28:contrast=1.45:brightness=-0.08,vignette=PI/4,"

    # Anime flicker: 2-frame hue burst at midpoint (supernatural moments only)
    flicker_vf = ""
    if flicker:
        mid = duration // 2
        flicker_vf = (
            f"hue=h='if(between(t,{mid},{mid}+0.08),180,0)'"
            f":s='if(between(t,{mid},{mid}+0.08),2.0,1.0)',"
        )

    text_vf = (
        f"drawtext=fontfile='{FONT}':text='{tag}'"
        f":fontcolor=0x666666:fontsize=26:borderw=1:bordercolor=black"
        f":x=40:y=50,"
        f"drawtext=fontfile='{FONT_BOLD}':text='{narr}'"
        f":fontcolor=white:fontsize=44:borderw=4:bordercolor=black"
        f":x=(w-text_w)/2:y=h-260:line_spacing=14"
    )

    vf = zoom_vf + grade + flicker_vf + text_vf

    return run([
        "ffmpeg", "-y",
        "-loop", "1", "-i", fp(img),
        "-t", str(duration),
        "-vf", vf,
        "-an",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-pix_fmt", "yuv420p", "-r", "24",
        fp(out),
    ], timeout=120)


# ─── Animal Clip → Cinematic Scene (mix-in for live-action feel) ──────────────

def make_animal_scene(clip: Path, duration: int, narration: str,
                      scene_num: int, out: Path) -> bool:
    clip_dur = get_duration(clip)
    loop = clip_dur < duration

    inp = (["-stream_loop", "-1"] if loop else []) + ["-i", fp(clip)]
    narr = esc(wrap_lines(narration, 32))
    tag  = esc(f"SCENE {scene_num}")

    vf = (
        f"scale={W}:{H}:force_original_aspect_ratio=increase,"
        f"crop={W}:{H},"
        f"eq=saturation=0.28:contrast=1.45:brightness=-0.08,"
        f"vignette=PI/4,"
        f"drawtext=fontfile='{FONT}':text='{tag}'"
        f":fontcolor=0x666666:fontsize=26:borderw=1:bordercolor=black"
        f":x=40:y=50,"
        f"drawtext=fontfile='{FONT_BOLD}':text='{narr}'"
        f":fontcolor=white:fontsize=44:borderw=4:bordercolor=black"
        f":x=(w-text_w)/2:y=h-260:line_spacing=14"
    )

    return run(
        ["ffmpeg", "-y"] + inp + [
            "-t", str(duration),
            "-vf", vf,
            "-an",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-r", "24",
            fp(out),
        ],
        timeout=120,
    )


# ─── Outro ────────────────────────────────────────────────────────────────────

def make_outro(out: Path) -> bool:
    lines = [
        "RAIZEN walked into exile.",
        "KURO filed it away.",
        "VARN felt the gate pulse.",
        " ",
        "It begins again.",
    ]
    text = "\\n".join(esc(l) for l in lines)
    vf = (
        f"drawtext=fontfile='{FONT}':text='{text}'"
        f":fontcolor=0xCCCCCC:fontsize=44:borderw=2:bordercolor=black"
        f":x=(w-text_w)/2:y=(h/2)-160:line_spacing=22"
    )
    return run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=0x030305:s={W}x{H}:r=24",
        "-t", "6",
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-pix_fmt", "yuv420p", "-r", "24",
        fp(out),
    ], timeout=30)


# ─── Concatenate ──────────────────────────────────────────────────────────────

def concatenate(clips: list[Path], out: Path) -> bool:
    lst = TEMP_DIR / "concat.txt"
    with open(lst, "w") as f:
        for p in clips:
            f.write(f"file '{fp(p)}'\n")
    return run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", fp(lst),
        "-c", "copy",
        fp(out),
    ], timeout=120)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 55)
    print("  SHADOW CLANS — EP001 VIDEO BUILDER")
    print("  Style: AI Art + Animal Mix | Mobile Portrait")
    print("=" * 55)

    episode = json.loads(SCRIPT.read_text(encoding="utf-8"))
    scenes  = episode["scenes"]

    # Animal clips sorted by score
    animal_clips = sorted(
        ANIMAL_DIR.glob("*.mp4"),
        key=lambda p: int(p.stem.split("score")[-1]) if "score" in p.stem else 0,
        reverse=True,
    )
    animal_idx = 0

    assembled = []

    # Title
    title_out = TEMP_DIR / "00_title.mp4"
    print("\n[TITLE]")
    if make_title_card("SHADOW  CLANS", "Episode 1 - The Night He Refused", 4, title_out):
        assembled.append(title_out)
        print("  OK")

    # Scenes
    for scene in scenes:
        sn     = scene["scene_number"]
        dur    = scene.get("duration_seconds", 12)
        narr   = scene.get("narration", "")
        action = scene.get("action", "")
        out    = TEMP_DIR / f"{sn:02d}_scene.mp4"
        flick  = sn in FLICKER_SCENES

        print(f"\n[SCENE {sn}] {dur}s | flicker={'YES' if flick else 'no'}")

        # Check for Midjourney frame
        frame = None
        for ext in ("png", "jpg", "jpeg", "PNG", "JPG"):
            candidate = FRAMES_DIR / f"scene_{sn:02d}.{ext}"
            if candidate.exists():
                frame = candidate
                break

        if frame:
            print(f"  AI frame: {frame.name}")
            ok = animate_frame(frame, dur, narr, sn, flick, out)

        elif sn in ANIMAL_SCENES and animal_clips:
            clip = animal_clips[animal_idx % len(animal_clips)]
            animal_idx += 1
            print(f"  Animal clip: {clip.name}")
            ok = make_animal_scene(clip, dur, narr, sn, out)

        else:
            print(f"  Placeholder (drop scene_{sn:02d}.png to replace)")
            ok = make_placeholder(sn, action, dur, out)

        if ok:
            assembled.append(out)
            print("  OK")
        else:
            print("  FAILED — skipping")

    # Outro
    outro = TEMP_DIR / "99_outro.mp4"
    print("\n[OUTRO]")
    if make_outro(outro):
        assembled.append(outro)
        print("  OK")

    if not assembled:
        print("\n[ERROR] Nothing assembled.")
        sys.exit(1)

    # Final
    final = OUT_DIR / "SC_EP001_The_Night_He_Refused_TEST.mp4"
    print(f"\n[ASSEMBLE] {len(assembled)} clips...")
    if concatenate(assembled, final):
        mb = final.stat().st_size / 1_000_000
        print(f"\n{'='*55}")
        print(f"  DONE  {final.name}")
        print(f"  Size: {mb:.1f} MB")
        print(f"  Path: {final}")
        print(f"\n  To upgrade: drop Midjourney PNGs into:")
        print(f"  shadow_clans_output/frames/EP001/")
        print(f"  scene_01.png ... scene_08.png")
        print(f"  Then re-run — AI frames auto-replace placeholders.")
        print(f"{'='*55}")
    else:
        print("\n[ERROR] Assembly failed.")
        sys.exit(1)

    shutil.rmtree(TEMP_DIR, ignore_errors=True)


if __name__ == "__main__":
    main()
