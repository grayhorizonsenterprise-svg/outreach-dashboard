"""
generate_sample.py — Gray Horizons Enterprise
Creates a sample Shadow Clans Episode 1 video using ffmpeg only.
No API keys required. Saves FULL + SHORT to Desktop for review.
Run: python generate_sample.py
"""

import subprocess
import sys
import os
import tempfile
import shutil
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DESKTOP = Path.home() / "Desktop" / "ShadowClans_Sample"
DESKTOP.mkdir(parents=True, exist_ok=True)

FONT = "C:/Windows/Fonts/arialbd.ttf"
FONT_LIGHT = "C:/Windows/Fonts/arial.ttf"

FULL_OUT  = str(DESKTOP / "SC_EP001_TheExileOfRaizen_FULL.mp4")
SHORT_OUT = str(DESKTOP / "SC_EP001_SHORT_01.mp4")

# Episode 1 script — each scene is (duration_secs, text_line, faction_color)
# Colors: Wolf Clan = #B8D4F0 (icy blue), Raven Order = #7BA7C4, Gorilla Titans = #C8A882, Narrator = #E8E8E0
SCENES = [
    # (seconds, text, hex_color, font_size)
    (4,  "SHADOW CLANS",                    "FFFFFF", 96),
    (3,  "Episode 1",                        "AAAAAA", 52),
    (4,  '"The Exile of RAIZEN"',            "B8D4F0", 62),
    (5,  "Three factions.\nOne shattered world.",     "E8E8E0", 54),
    (5,  "And one man who remembers\nhow it broke.",  "E8E8E0", 54),
    (5,  "Wolf Clan territory.\nNorthern Ridge. Night.", "888888", 42),
    (6,  "RAIZEN had not spoken\nto the elders in three days.", "B8D4F0", 54),
    (6,  "He already knew what\nthey were going to say.", "B8D4F0", 54),
    (5,  "\"You are no longer\none of us.\"",  "CCCCCC", 58),
    (5,  "He didn't argue.",                  "B8D4F0", 60),
    (5,  "There was nothing left\nto argue about.", "B8D4F0", 54),
    (6,  "The Hollow Gate had opened\ntwo weeks ago.", "888888", 42),
    (6,  "Everyone on this mountain\nheard it.",       "888888", 42),
    (6,  "No one talked about\nwhat came through.",    "B8D4F0", 54),
    (5,  "The Raven Order knew.",             "7BA7C4", 60),
    (6,  "KURO had known\nbefore it opened.",  "7BA7C4", 58),
    (6,  "That was the part\nthat kept RAIZEN awake.", "B8D4F0", 54),
    (5,  "He picked up his pack.",            "B8D4F0", 60),
    (5,  "He didn't look back.",              "B8D4F0", 60),
    (6,  "Honor isn't something\nyou carry with you.", "E8E8E0", 54),
    (5,  "It's something you become\nwhen no one is watching.", "E8E8E0", 52),
    (5,  "RAIZEN had always\nknown that.",     "B8D4F0", 58),
    (4,  "He just never thought\nit would cost him everything.", "B8D4F0", 52),
    (5,  "Next: The Raven Order moves.",      "7BA7C4", 54),
    (4,  "SHADOW CLANS",                      "FFFFFF", 80),
    (3,  "Episode 2 drops soon.",             "888888", 44),
]

def esc(text):
    """Escape text for ffmpeg drawtext."""
    return (text
            .replace("\\", "\\\\")
            .replace("'",  "’")   # curly apostrophe — no escaping needed
            .replace(":",  "\\:")
            .replace("[",  "\\[")
            .replace("]",  "\\]")
            .replace(",",  "\\,")
            )


def hex_to_rgb(h):
    h = h.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return r, g, b


def build_scene(duration, text, color_hex, font_size, tmp_dir, idx):
    """Build one scene clip and return its path."""
    out = os.path.join(tmp_dir, f"scene_{idx:03d}.mp4")
    r, g, b = hex_to_rgb(color_hex)

    lines = text.split("\n")
    # Build multi-line drawtext filters stacked vertically
    drawtext_filters = []
    line_h = font_size + 12
    total_h = line_h * len(lines)
    start_y = f"(h - {total_h}) / 2"

    for li, line in enumerate(lines):
        y_expr = f"({start_y}) + {li * line_h}"
        safe = esc(line)
        drawtext_filters.append(
            f"drawtext=fontfile='{FONT}':"
            f"text='{safe}':"
            f"fontcolor={r}\\/{g}\\/{b}:"
            f"fontsize={font_size}:"
            f"borderw=3:bordercolor=0x000000:"
            f"shadowcolor=0x000000:shadowx=2:shadowy=2:"
            f"x=(w-text_w)/2:y={y_expr}:"
            f"alpha='if(lt(t,0.4),t/0.4,if(gt(t,{duration - 0.4}),({duration}-t)/0.4,1))'"
        )

    vf = ",".join([
        "scale=1080:1920",
        *drawtext_filters,
    ])

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c=0x0a0a12:size=1080x1920:rate=30:duration={duration}",
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-an",
        out,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [WARN] Scene {idx} failed: {result.stderr[-200:]}")
        return None
    return out


def concat_clips(clip_paths, output_path):
    """Concatenate clips using ffmpeg concat demuxer."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        list_file = f.name
        for p in clip_paths:
            f.write(f"file '{p.replace(chr(92), '/')}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", list_file,
        "-c", "copy",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    os.unlink(list_file)
    if result.returncode != 0:
        print(f"  [ERROR] Concat failed: {result.stderr[-300:]}")
        return False
    return True


def extract_short(full_path, short_path, start=0, duration=58):
    """Extract a Short from the full video."""
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start),
        "-i", full_path,
        "-t", str(duration),
        "-c", "copy",
        short_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


def run():
    print("=" * 52)
    print("  SHADOW CLANS — Sample Generator")
    print("=" * 52)
    print(f"Output → {DESKTOP}\n")

    tmp = tempfile.mkdtemp(prefix="sc_sample_")
    try:
        clips = []
        total = len(SCENES)
        for i, (dur, text, color, fsize) in enumerate(SCENES):
            label = text.replace("\n", " ")[:40]
            print(f"  [{i+1}/{total}] Building: {label}...")
            path = build_scene(dur, text, color, fsize, tmp, i)
            if path:
                clips.append(path)

        if not clips:
            print("[ERROR] No scenes built — check ffmpeg installation")
            return

        print(f"\n  Assembling {len(clips)} scenes into FULL video...")
        ok = concat_clips(clips, FULL_OUT)
        if not ok:
            print("[ERROR] Assembly failed")
            return

        print(f"  Extracting SHORT (first 58s)...")
        extract_short(FULL_OUT, SHORT_OUT, start=0, duration=58)

        total_secs = sum(d for d, *_ in SCENES)
        mins, secs = divmod(int(total_secs), 60)

        print()
        print("=" * 52)
        print(f"  DONE — {mins}:{secs:02d} full episode generated")
        print()
        print(f"  FULL  → {FULL_OUT}")
        print(f"  SHORT → {SHORT_OUT}")
        print()
        print("  Review both on Desktop before approving.")
        print("  If style looks good → run shadow_clans_engine.py")
        print("  with ANTHROPIC_API_KEY for AI-generated scripts.")
        print("=" * 52)

    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    run()
