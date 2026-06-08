"""
yt_analyzer.py — Gray Horizons Enterprise
Pulls transcript from any YouTube video, summarizes it, and generates
repurposing content: Twitter posts, LinkedIn posts, pitch angles, email hooks.

Usage:
  pip install youtube-transcript-api openai
  python yt_analyzer.py https://youtu.be/VIDEO_ID

Output: yt_analysis_VIDEO_ID.json + printed summary
"""

import sys
import json
import re
import os
from pathlib import Path

DATA_DIR = Path(os.path.dirname(os.path.abspath(__file__)))


def extract_video_id(url: str) -> str:
    for pattern in [
        r"youtu\.be/([A-Za-z0-9_\-]{11})",
        r"youtube\.com/watch\?v=([A-Za-z0-9_\-]{11})",
        r"youtube\.com/shorts/([A-Za-z0-9_\-]{11})",
    ]:
        m = re.search(pattern, url)
        if m:
            return m.group(1)
    return url.strip()


def get_transcript(video_id: str) -> str:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        api = YouTubeTranscriptApi()
        snippets = api.fetch(video_id)
        return " ".join(s.text for s in snippets)
    except ImportError:
        print("Run: pip install youtube-transcript-api")
        sys.exit(1)
    except Exception as e:
        print(f"[YT] Transcript error: {e}")
        print("     Video may have captions disabled or be private.")
        sys.exit(1)


def analyze(transcript: str, video_url: str) -> dict:
    try:
        import openai
    except ImportError:
        print("Run: pip install openai")
        return {}

    key = os.getenv("OPENAI_API_KEY", "")
    if not key:
        print("[YT] Set OPENAI_API_KEY to enable analysis")
        return {}

    client = openai.OpenAI(api_key=key)
    excerpt = transcript[:8000]

    prompt = f"""Analyze this YouTube video transcript for Gray Horizons Enterprise.
GHE sells AI automation systems for local service businesses (GHL CRM, voice agents, contractor systems, HOA management).
Also sells TradingView indicators and trading signals.

URL: {video_url}
TRANSCRIPT: {excerpt}

Return JSON with:
- summary: 3-5 sentence summary
- key_takeaways: 5 actionable insights
- twitter_posts: 3 tweet-ready posts under 240 chars
- linkedin_posts: 2 LinkedIn posts (3-5 short paragraphs each)
- pitch_angles: 3 ways to apply these insights to close AI automation clients
- email_subject_lines: 3 cold outreach subject lines based on video insights
- relevance_score: 1-10 rating for GHE business relevance

Return ONLY valid JSON."""

    try:
        r = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            response_format={"type": "json_object"}
        )
        return json.loads(r.choices[0].message.content)
    except Exception as e:
        print(f"[YT] OpenAI error: {e}")
        return {}


def run(url: str):
    video_id   = extract_video_id(url)
    print(f"[YT] Fetching transcript: {video_id}")
    transcript = get_transcript(video_id)
    print(f"[YT] {len(transcript)} chars pulled")

    raw = DATA_DIR / f"yt_transcript_{video_id}.txt"
    raw.write_text(transcript, encoding="utf-8")

    print("[YT] Analyzing with GPT-4o...")
    result = analyze(transcript, url)

    if result:
        out = DATA_DIR / f"yt_analysis_{video_id}.json"
        out.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"\n{'='*60}")
        print("SUMMARY:", result.get("summary", ""))
        print("\nKEY TAKEAWAYS:")
        for i, t in enumerate(result.get("key_takeaways", []), 1):
            print(f"  {i}. {t}")
        print("\nPITCH ANGLES:")
        for i, p in enumerate(result.get("pitch_angles", []), 1):
            print(f"  {i}. {p}")
        print(f"\nAnalysis saved: {out}")
        print(f"{'='*60}")
    else:
        print("\nRaw transcript saved to:", raw)
        print("First 500 chars:", transcript[:500])


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python yt_analyzer.py <youtube_url>")
        sys.exit(1)
    run(sys.argv[1])
