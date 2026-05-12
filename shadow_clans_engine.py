"""
shadow_clans_engine.py — Gray Horizons Enterprise
Autonomous cinematic content engine for SHADOW CLANS universe.
Nightly: generate episode script + scene prompts + narration via Claude
Morning: assemble frames → video → extract Shorts → queue YouTube upload
"""

import os
import sys
import json
import time
import random
import subprocess
import textwrap
from datetime import datetime
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ─── Config ──────────────────────────────────────────────────────────────────

ANTHROPIC_KEY    = os.getenv("ANTHROPIC_API_KEY", "")
STABILITY_KEY    = os.getenv("STABILITY_API_KEY", "")    # optional: auto-generate frames
YOUTUBE_ID       = os.getenv("YOUTUBE_CLIENT_ID", "")

DIR              = Path(__file__).parent
OUTPUT_DIR       = DIR / "shadow_clans_output"
EPISODES_DIR     = OUTPUT_DIR / "episodes"
FRAMES_DIR       = OUTPUT_DIR / "frames"
SHORTS_DIR       = OUTPUT_DIR / "shorts"
PROMPTS_DIR      = OUTPUT_DIR / "image_prompts"
UPLOAD_DIR       = OUTPUT_DIR / "ready_to_upload"
EPISODE_LOG      = OUTPUT_DIR / "episode_log.json"
FONT_PATH        = "C:/Windows/Fonts/arial.ttf"

for d in [OUTPUT_DIR, EPISODES_DIR, FRAMES_DIR, SHORTS_DIR, PROMPTS_DIR, UPLOAD_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ─── Universe ─────────────────────────────────────────────────────────────────

FACTIONS = {
    "Wolf Clan": {
        "leader": "RAIZEN",
        "eyes": "silver glowing, like frozen moonlight trapped in ice",
        "armor": "scarred dark iron plate, deep claw marks across the chest",
        "env": "snow-covered mountain peaks, frozen ruins, moonlit tundra",
        "theme": "honor, exile, survival at any cost",
        "palette": "desaturated blue-silver, breath mist, ice-cracked ground",
    },
    "Raven Order": {
        "leader": "KURO",
        "eyes": "cold glowing blue, unblinking",
        "armor": "black feather-plated cloak, obsidian half-mask",
        "env": "ruined stone towers, perpetual fog, dead city architecture",
        "theme": "secrets, manipulation, watching everything",
        "palette": "charcoal and deep shadow, dim blue-grey fog, black silhouettes",
    },
    "Gorilla Titans": {
        "leader": "VARN",
        "eyes": "amber runes that pulse, carved into skin",
        "armor": "ancient stone-plate, cracked glowing symbols etched in each slab",
        "env": "overgrown ruined temples, dense jungle fog, shattered statues",
        "theme": "ancient power, tragedy, a war they never wanted",
        "palette": "ochre and deep forest green, heavy mist, moss-covered stone",
    },
}

LORE_SEEDS = [
    "The night RAIZEN refused the kill order and was exiled from his own clan",
    "KURO's first move — the forged letter that started the three-faction war",
    "The moment VARN activated the Hollow Gate out of grief — and what came through",
    "A nameless scout discovers that all three leaders once trained together",
    "The Hollow Gate begins speaking — and only RAIZEN hears it",
    "A spy inside Wolf Clan feeding intelligence directly to the Raven Order",
    "VARN's son returns scarred, alive, and loyal to no faction",
    "The failed alliance — and the hand that sabotaged it from inside",
    "KURO reveals what the Hollow Gate really is — to RAIZEN alone",
    "The last survivor of a fourth clan arrives with a warning",
    "The night before the final battle — three leaders, three fires, one decision",
    "What the Hollow Gate promised VARN if he opened it one more time",
]

VISUAL_DIRECTIVE = """\
REALISM OVERRIDE — NON-NEGOTIABLE:
- 70% cinematic live-action realism: visible skin pores, fabric weight, dirt, sweat, battle scars
- 20% dark fantasy atmosphere: low unnatural fog, faint supernatural rune glow, ancient decay
- 10% retro anime flicker: ONLY 1-2 frames at the exact moment of supernatural power release — nowhere else
- REDUCE BY 45%: bloom glow effects, cartoon shading, game-engine rim lighting, color oversaturation, anime face proportions
- CAMERA: handheld documentary realism, rack focus, shallow depth of field, slight lens grain
- LIGHTING: practical sources only — torchlight, moonlight, distant fire, no lens flares or fantasy spotlights
- COLOR GRADE: desaturated, high contrast, filmic — NOT vibrant HDR, NOT painted look
- TARGET FEEL: a lost cinematic fantasy film from the early 2000s — NOT AI-generated fantasy spam
"""

SHORTS_HOOKS = [
    "No one knows why he chose exile...",
    "The war began with a single message...",
    "He opened the gate. And something came through.",
    "Three leaders. One secret. The gate was never meant to close.",
    "What KURO knew — and never told them.",
    "The Hollow Gate speaks. And it chose him.",
    "He was the last. He had nothing left to protect.",
    "They called him a traitor. He called it survival.",
    "Ancient power. Ancient cost. VARN paid it alone.",
    "The fourth clan. Nobody was supposed to know they existed.",
]

YOUTUBE_TAGS = "shadow clans,dark fantasy,cinematic,anime,wolf clan,raizen,kuro,varn,hollow gate,action,lore"


# ─── Script Generation ────────────────────────────────────────────────────────

def generate_episode(episode_number: int, lore_seed: str) -> dict:
    """Uses Claude to write a full episode script with scene breakdowns."""
    if not ANTHROPIC_KEY:
        print("[SHADOW CLANS] No ANTHROPIC_API_KEY set")
        return {}

    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

    factions_text = "\n".join(
        f"  {name}: Leader {f['leader']}, {f['eyes']} eyes, {f['armor']}, "
        f"Setting: {f['env']}, Theme: {f['theme']}"
        for name, f in FACTIONS.items()
    )

    prompt = f"""\
You are the head writer for SHADOW CLANS — an original dark cinematic fantasy universe.
The visual mandate is: {VISUAL_DIRECTIVE}

UNIVERSE:
- Three animal warrior factions in a collapsing world centered on THE HOLLOW GATE
- Factions:
{factions_text}

Write Episode {episode_number}: "{lore_seed}"

FORMAT — return valid JSON only, no markdown, no explanation:
{{
  "episode_number": {episode_number},
  "title": "Episode title (dramatic, 4-8 words)",
  "logline": "One sentence — what this episode is about",
  "narrator_intro": "30-second spoken narration that opens the episode (cinematic, no fluff)",
  "scenes": [
    {{
      "scene_number": 1,
      "duration_seconds": 12,
      "setting": "Exact physical location",
      "action": "What happens — written like a film script direction",
      "narration": "Spoken narration for this scene (10-20 words max)",
      "image_prompt": "Stable Diffusion / Midjourney prompt following the visual directive above. Start with the most important visual elements. End with: cinematic film grain, desaturated, shallow depth of field, 4k, realistic textures, NO glow, NO anime shading",
      "faction": "Wolf Clan | Raven Order | Gorilla Titans | neutral"
    }}
  ],
  "narrator_outro": "15-second closing narration teasing next episode",
  "shorts_hook": "One line — the most shocking moment in this episode (for Shorts thumbnail text)",
  "youtube_title": "Clickable but non-clickbait YouTube title",
  "youtube_description": "Full YouTube description with #hashtags at end"
}}

Write exactly 8 scenes. Each scene 10-15 seconds long. Total runtime: ~90 seconds.
"""

    try:
        message = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        episode = json.loads(raw)
        return episode
    except Exception as e:
        print(f"[SHADOW CLANS] Script generation error: {e}")
        return {}


# ─── Image Generation (Stability AI) ─────────────────────────────────────────

def generate_frame(prompt: str, output_path: Path) -> bool:
    """Generate a single frame via Stability AI. Returns True if saved."""
    if not STABILITY_KEY:
        return False
    try:
        import requests
        resp = requests.post(
            "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {STABILITY_KEY}",
            },
            json={
                "text_prompts": [
                    {"text": prompt, "weight": 1.0},
                    {"text": "anime style, cartoon, oversaturated, glowing, game engine, HDR, plastic, CGI, artificial", "weight": -0.9},
                ],
                "cfg_scale": 10,
                "height": 1344,
                "width": 768,
                "samples": 1,
                "steps": 30,
            },
            timeout=60,
        )
        if resp.status_code == 200:
            img_data = resp.json()["artifacts"][0]["base64"]
            import base64
            output_path.write_bytes(base64.b64decode(img_data))
            return True
        else:
            print(f"  [IMG] Stability error {resp.status_code}: {resp.text[:100]}")
            return False
    except Exception as e:
        print(f"  [IMG] Frame generation error: {e}")
        return False


# ─── Video Assembly ───────────────────────────────────────────────────────────

def check_ffmpeg() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True, timeout=10)
        return True
    except Exception:
        return False


def frame_to_video(frame_path: Path, duration: int, narration: str, output_path: Path) -> bool:
    """Convert a still image into a video clip with narration text overlay."""
    safe_text = narration.replace("'", "\\'").replace(":", "\\:").replace("[", "\\[").replace("]", "\\]")
    words = textwrap.wrap(safe_text, 35)
    text_line = "\\n".join(words)

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(frame_path),
        "-vf", (
            f"scale=1080:1920:force_original_aspect_ratio=decrease,"
            f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,"
            f"drawtext=fontfile='{FONT_PATH}':text='{text_line}':"
            f"fontcolor=white:fontsize=44:borderw=3:bordercolor=black:"
            f"x=(w-text_w)/2:y=h-200:line_spacing=12"
        ),
        "-t", str(duration),
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-pix_fmt", "yuv420p",
        "-r", "24",
        str(output_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        return result.returncode == 0
    except Exception as e:
        print(f"  [FFMPEG] Error: {e}")
        return False


def assemble_episode(episode: dict, episode_dir: Path) -> Path | None:
    """Concatenate scene clips into final episode video."""
    clip_list_path = episode_dir / "clips.txt"
    clips = sorted(episode_dir.glob("scene_*.mp4"))

    if not clips:
        print("[ASSEMBLE] No scene clips found")
        return None

    with open(clip_list_path, "w") as f:
        for clip in clips:
            f.write(f"file '{clip}'\n")

    ep_num    = episode.get("episode_number", 1)
    title_raw = episode.get("title", f"Episode {ep_num}").replace(" ", "_")[:40]
    out_path  = EPISODES_DIR / f"SC_EP{ep_num:03d}_{title_raw}.mp4"

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(clip_list_path),
        "-c", "copy",
        str(out_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=300)
        if result.returncode == 0:
            print(f"  [ASSEMBLE] Episode saved: {out_path.name}")
            return out_path
        else:
            print(f"  [ASSEMBLE] FFmpeg error: {result.stderr.decode()[:200]}")
            return None
    except Exception as e:
        print(f"  [ASSEMBLE] Error: {e}")
        return None


def extract_shorts(episode_path: Path, episode: dict) -> list[Path]:
    """Extract 5-15 second Shorts from key scene moments."""
    shorts = []
    hook   = episode.get("shorts_hook", SHORTS_HOOKS[0])
    safe_hook = hook.replace("'", "\\'").replace(":", "\\:").replace("[", "\\[").replace("]", "\\]")

    offsets = [5, 20, 40, 60, 80]

    for i, offset in enumerate(offsets, 1):
        out = SHORTS_DIR / f"SC_SHORT_{episode['episode_number']:03d}_{i:02d}.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(offset),
            "-i", str(episode_path),
            "-t", "15",
            "-vf", (
                f"scale=1080:1920:force_original_aspect_ratio=decrease,"
                f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,"
                f"drawtext=fontfile='{FONT_PATH}':text='{safe_hook}':"
                f"fontcolor=white:fontsize=52:borderw=3:bordercolor=black:"
                f"x=(w-text_w)/2:y=120:line_spacing=10"
            ),
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-pix_fmt", "yuv420p",
            str(out),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=60)
            if result.returncode == 0:
                shorts.append(out)
        except Exception:
            pass

    print(f"  [SHORTS] Extracted {len(shorts)} Shorts clips")
    return shorts


# ─── Prompt Export ────────────────────────────────────────────────────────────

def save_prompts(episode: dict, ep_num: int):
    """Save all image prompts to a text file for manual Midjourney generation."""
    out = PROMPTS_DIR / f"EP{ep_num:03d}_image_prompts.txt"
    lines = [
        f"SHADOW CLANS — Episode {ep_num}: {episode.get('title', '')}",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "=" * 60,
        "",
        "PASTE EACH PROMPT INTO MIDJOURNEY OR STABLE DIFFUSION:",
        "",
    ]
    for scene in episode.get("scenes", []):
        lines += [
            f"SCENE {scene['scene_number']} ({scene.get('duration_seconds', 12)}s)",
            f"Action: {scene.get('action', '')}",
            f"Narration: {scene.get('narration', '')}",
            "",
            f"IMAGE PROMPT:",
            scene.get("image_prompt", ""),
            "",
            "-" * 40,
            "",
        ]
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"  [PROMPTS] Saved to {out.name}")



# ─── Episode Log ──────────────────────────────────────────────────────────────

def load_log() -> dict:
    if EPISODE_LOG.exists():
        try:
            return json.loads(EPISODE_LOG.read_text())
        except Exception:
            pass
    return {"last_episode": 0, "used_seeds": [], "episodes": []}


def save_log(log: dict):
    EPISODE_LOG.write_text(json.dumps(log, indent=2))


# ─── Main Run ─────────────────────────────────────────────────────────────────

def run():
    print("=" * 55)
    print("  SHADOW CLANS — CONTENT ENGINE")
    print("=" * 55)

    if not ANTHROPIC_KEY:
        print("[ERROR] ANTHROPIC_API_KEY not set — cannot generate scripts")
        return

    ffmpeg_ok = check_ffmpeg()
    if not ffmpeg_ok:
        print("[WARNING] ffmpeg not found — will generate prompts only, no video assembly")

    log       = load_log()
    ep_num    = log["last_episode"] + 1
    used      = set(log["used_seeds"])
    remaining = [s for s in LORE_SEEDS if s not in used]
    if not remaining:
        used = set()
        remaining = LORE_SEEDS[:]
    seed = random.choice(remaining)

    print(f"\n[EP {ep_num:03d}] Seed: {seed}")
    print("[SCRIPT] Generating episode via Claude...")

    episode = generate_episode(ep_num, seed)
    if not episode:
        print("[ERROR] Script generation failed")
        return

    print(f"  Title: {episode.get('title', '?')}")
    print(f"  Scenes: {len(episode.get('scenes', []))}")

    # Save script JSON
    ep_dir = FRAMES_DIR / f"EP{ep_num:03d}"
    ep_dir.mkdir(parents=True, exist_ok=True)
    script_path = ep_dir / "script.json"
    script_path.write_text(json.dumps(episode, indent=2), encoding="utf-8")
    print(f"  Script saved: {script_path.name}")

    # Save image prompts
    save_prompts(episode, ep_num)

    # Generate frames via Stability AI if key is set
    if STABILITY_KEY:
        print(f"\n[FRAMES] Generating {len(episode.get('scenes', []))} frames via Stability AI...")
        for scene in episode.get("scenes", []):
            frame_path = ep_dir / f"scene_{scene['scene_number']:02d}.png"
            if frame_path.exists():
                print(f"  Scene {scene['scene_number']}: cached")
                continue
            success = generate_frame(scene.get("image_prompt", ""), frame_path)
            status  = "OK" if success else "SKIP"
            print(f"  Scene {scene['scene_number']}: {status}")
            time.sleep(1)
    else:
        print("\n[FRAMES] No STABILITY_API_KEY — prompts saved for manual Midjourney generation")
        print(f"         Prompts: {PROMPTS_DIR}/EP{ep_num:03d}_image_prompts.txt")

    # Assemble video clips if ffmpeg + frames exist
    episode_path = None
    if ffmpeg_ok and STABILITY_KEY:
        print("\n[VIDEO] Assembling scene clips...")
        for scene in episode.get("scenes", []):
            frame_path = ep_dir / f"scene_{scene['scene_number']:02d}.png"
            clip_path  = ep_dir / f"scene_{scene['scene_number']:02d}.mp4"
            if not frame_path.exists():
                print(f"  Scene {scene['scene_number']}: no frame — skipping")
                continue
            ok = frame_to_video(
                frame_path,
                scene.get("duration_seconds", 12),
                scene.get("narration", ""),
                clip_path,
            )
            print(f"  Scene {scene['scene_number']}: {'OK' if ok else 'FAIL'}")

        print("\n[ASSEMBLE] Merging clips into full episode...")
        episode_path = assemble_episode(episode, ep_dir)

        if episode_path and episode_path.exists():
            print("\n[SHORTS] Extracting Shorts...")
            shorts = extract_shorts(episode_path, episode)

            # Copy episode + shorts to upload-ready folder with clear names
            import shutil
            ep_num_str  = f"EP{episode.get('episode_number', 1):03d}"
            title_clean = episode.get("title", "").replace(" ", "_")[:35]

            upload_copy = UPLOAD_DIR / f"SC_{ep_num_str}_{title_clean}_FULL.mp4"
            shutil.copy2(episode_path, upload_copy)

            for i, short in enumerate(shorts, 1):
                short_dest = UPLOAD_DIR / f"SC_{ep_num_str}_SHORT_{i:02d}.mp4"
                shutil.copy2(short, short_dest)

            print(f"\n[READY] Episode + {len(shorts)} Shorts ready for manual upload")
            print(f"         Folder: {UPLOAD_DIR}")
            print(f"         Full episode: SC_{ep_num_str}_{title_clean}_FULL.mp4")
            print(f"         Shorts:       SC_{ep_num_str}_SHORT_01 through {len(shorts):02d}")
            print(f"         YouTube title: {episode.get('youtube_title', '')}")
            print(f"         Review clips before uploading — upload at your own pace")

    # Update log
    log["last_episode"] = ep_num
    log["used_seeds"]   = list(used | {seed})
    log["episodes"].append({
        "number":    ep_num,
        "title":     episode.get("title", ""),
        "seed":      seed,
        "generated": datetime.now().isoformat(),
        "has_video": episode_path is not None,
    })
    save_log(log)

    print(f"\n{'='*55}")
    print(f"  DONE — Episode {ep_num:03d}: {episode.get('title', '')}")
    if STABILITY_KEY:
        print(f"  Frames:  {ep_dir}")
        if episode_path:
            print(f"  Episode: {episode_path.name}")
            print(f"  Shorts:  {SHORTS_DIR}")
    else:
        print(f"  Prompts: {PROMPTS_DIR}/EP{ep_num:03d}_image_prompts.txt")
        print("  Next: generate frames in Midjourney, drop into frames folder, re-run")
    print(f"{'='*55}")


if __name__ == "__main__":
    run()
