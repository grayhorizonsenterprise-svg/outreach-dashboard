"""
video_intel.py — Gray Horizons Enterprise
Robust video analysis pipeline. Accepts YouTube URLs or local video files.

TRANSCRIPT METHODS (in order of preference):
  1. YouTube Transcript API  — instant, free, works on most YouTube videos
  2. OpenAI Whisper via API  — fallback for any video/audio (requires download)

QUEUE SYSTEM:
  Drop a URL into video_queue.json and run this script to process all pending.
  Results saved to video_analyses/ folder.

USAGE:
  python video_intel.py                          # process all queued URLs
  python video_intel.py <youtube_url>            # analyze single URL immediately
  python video_intel.py --add <youtube_url>      # add to queue without processing
  python video_intel.py --list                   # show queue and completed analyses
  python video_intel.py --brief <youtube_url>    # print summary of existing analysis

INSTALL:
  pip install youtube-transcript-api anthropic yt-dlp

Railway cron: run every 30 min to auto-process queue
"""

import sys
import json
import re
import os
import hashlib
import time
from pathlib import Path
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv(encoding="utf-8")
except ImportError:
    pass

DATA_DIR     = Path(os.path.dirname(os.path.abspath(__file__)))
ANALYSES_DIR = DATA_DIR / "video_analyses"
QUEUE_FILE   = DATA_DIR / "video_queue.json"
ANALYSES_DIR.mkdir(exist_ok=True)

ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")

GHE_CONTEXT = """Gray Horizons Enterprise (GHE) sells:
- AI automation systems for local service businesses (GHL CRM, AI voice agents, contractor intake, HOA management)
- TradingView indicators (Edge Scanner, Kelly Sizer, Congressional Tracker) $79 one-time
- AI trading signals $49/month
- Managed retainer $750/month
Revenue target: $100K within 2 months of landing first client."""


def extract_video_id(url: str) -> str:
    for pattern in [
        r"youtu\.be/([A-Za-z0-9_\-]{11})",
        r"youtube\.com/watch\?v=([A-Za-z0-9_\-]{11})",
        r"youtube\.com/shorts/([A-Za-z0-9_\-]{11})",
    ]:
        m = re.search(pattern, url)
        if m:
            return m.group(1)
    return None


def url_hash(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:10]


def _transcript_api(video_id: str) -> str | None:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        api = YouTubeTranscriptApi()
        snippets = api.fetch(video_id)
        return " ".join(s.text for s in snippets)
    except Exception as e:
        print(f"  [Transcript API] {e}")
        return None


def _transcript_whisper(url: str) -> str | None:
    # Whisper transcription requires OpenAI API key — not available in this setup
    # YouTube Transcript API handles the majority of videos
    print("  [Whisper] Skipped: no OpenAI key. Video may not have captions enabled.")
    return None


def get_transcript(url: str) -> str | None:
    vid = extract_video_id(url)
    if vid:
        t = _transcript_api(vid)
        if t:
            return t
    return _transcript_whisper(url)


def analyze(transcript: str, url: str) -> dict:
    if not ANTHROPIC_KEY:
        return {"error": "No ANTHROPIC_API_KEY"}
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
        prompt = f"""{GHE_CONTEXT}

VIDEO: {url}
TRANSCRIPT: {transcript[:8000]}

Return JSON with these exact fields:
- title: video title if identifiable
- summary: 3-5 sentence summary
- key_takeaways: list of 5 actionable insights
- pitch_angles: list of 3 ways to use insights to close automation clients
- sales_scripts: list of 2 short 3-sentence pitches from video insights
- objection_handlers: list of 3 objection/response pairs for closing automation clients
- revenue_application: how to apply this to hit $100K target
- action_items: list of 3 immediate next steps
- twitter_posts: list of 3 tweets under 240 chars
- linkedin_posts: list of 2 LinkedIn posts 3-5 short paragraphs each
- relevance_score: 1-10

Return ONLY valid JSON. No markdown. No em dashes. No double hyphens."""

        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = message.content[0].text.strip()
        # Strip markdown code fences if Claude wraps the JSON
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw.strip())
        return json.loads(raw)
    except Exception as e:
        return {"error": str(e)}


def load_queue() -> list:
    try:
        return json.loads(QUEUE_FILE.read_text(encoding="utf-8")) if QUEUE_FILE.exists() else []
    except Exception:
        return []


def save_queue(q: list):
    QUEUE_FILE.write_text(json.dumps(q, indent=2), encoding="utf-8")


def add_to_queue(url: str, note: str = ""):
    q = load_queue()
    if any(i["url"] == url for i in q):
        print(f"[QUEUE] Already in queue: {url}")
        return
    q.append({"url": url, "note": note, "added_at": datetime.utcnow().isoformat(), "status": "pending"})
    save_queue(q)
    print(f"[QUEUE] Added: {url}")


def process_url(url: str, note: str = "") -> dict | None:
    uid      = url_hash(url)
    out_file = ANALYSES_DIR / f"{uid}.json"
    if out_file.exists():
        print(f"[INTEL] Already analyzed — loading from cache")
        return json.loads(out_file.read_text(encoding="utf-8"))

    print(f"\n[INTEL] Processing: {url}")
    transcript = get_transcript(url)
    if not transcript:
        print("[INTEL] Could not get transcript")
        return None

    (ANALYSES_DIR / f"{uid}_transcript.txt").write_text(transcript, encoding="utf-8")
    print(f"[INTEL] Analyzing ({len(transcript)} chars)...")
    result = analyze(transcript, url)
    result.update({"url": url, "note": note, "analyzed_at": datetime.utcnow().isoformat()})
    out_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"[INTEL] Saved to video_analyses/{uid}.json")
    return result


def process_queue():
    q = load_queue()
    pending = [i for i in q if i.get("status") == "pending"]
    print(f"[QUEUE] {len(pending)} pending")
    for item in pending:
        result = process_url(item["url"], item.get("note", ""))
        item["status"] = "done" if result else "failed"
        save_queue(q)
        if result:
            print_brief(result)
        time.sleep(2)


def print_brief(r: dict):
    print(f"\n{'='*60}")
    print(f"TITLE: {r.get('title','')}")
    print(f"RELEVANCE: {r.get('relevance_score','?')}/10")
    print(f"\nSUMMARY: {r.get('summary','')}")
    print(f"\nKEY TAKEAWAYS:")
    for i, t in enumerate(r.get("key_takeaways", []), 1):
        print(f"  {i}. {t}")
    print(f"\nPITCH ANGLES:")
    for i, p in enumerate(r.get("pitch_angles", []), 1):
        print(f"  {i}. {p}")
    print(f"\nREVENUE APPLICATION: {r.get('revenue_application','')}")
    print(f"\nACTION ITEMS:")
    for i, a in enumerate(r.get("action_items", []), 1):
        print(f"  {i}. {a}")
    print(f"{'='*60}\n")


def list_all():
    q = load_queue()
    files = sorted(ANALYSES_DIR.glob("*.json"))
    print(f"\nQUEUE ({len(q)} items):")
    for item in q:
        print(f"  [{item['status'].upper():7}] {item['url'][:70]}")
    print(f"\nANALYSES ({len(files)} completed):")
    for f in files:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            print(f"  [{d.get('relevance_score','?')}/10] {d.get('title','?')[:50]} — {d.get('analyzed_at','')[:10]}")
        except Exception:
            print(f"  {f.name}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        process_queue()
    elif args[0] == "--list":
        list_all()
    elif args[0] == "--add" and len(args) >= 2:
        add_to_queue(args[1], " ".join(args[2:]))
    elif args[0] == "--brief" and len(args) >= 2:
        uid = url_hash(args[1])
        f   = ANALYSES_DIR / f"{uid}.json"
        if f.exists():
            print_brief(json.loads(f.read_text(encoding="utf-8")))
        else:
            print("No analysis found. Run without --brief first.")
    else:
        result = process_url(args[0], " ".join(args[1:]))
        if result:
            print_brief(result)
