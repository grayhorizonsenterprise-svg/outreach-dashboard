"""
kdp_ebook_generator.py — Gray Horizons Enterprise
Generates niche ebooks using Claude AI and exports them
as formatted HTML ready for KDP (Kindle Direct Publishing).

Each ebook = passive income on Amazon indefinitely.
Target: 10 books live in month 1 = $2,000-$8,000/month by month 3.

Usage:
  python kdp_ebook_generator.py
"""

import anthropic
import os
import sys
import json
import re
import time
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
DATA_DIR      = os.path.dirname(os.path.abspath(__file__))
EBOOK_DIR     = os.path.join(DATA_DIR, "ebooks")
os.makedirs(EBOOK_DIR, exist_ok=True)

EBOOKS = [
    {
        "title":    "The Sports Bettor's Edge: Using Math and AI Signals to Beat the House",
        "subtitle": "Kelly Criterion, Line Shopping, and Daily Signal Strategies",
        "niche":    "sports_betting",
        "keywords": ["sports betting strategy", "Kelly criterion betting", "sports betting math", "beat the sportsbook", "AI betting signals"],
        "price":    9.99,
        "chapters": [
            "Why Most Bettors Lose (And How to Be Different)",
            "Understanding Expected Value and Edge",
            "The Kelly Criterion: How to Size Every Bet",
            "Reading Lines and Finding Value",
            "Line Shopping: The Free Edge Nobody Uses",
            "Using AI Signals in Your Betting Strategy",
            "Bankroll Management That Protects Your Money",
            "Tracking Your Bets: What to Measure",
            "Sports-Specific Edges: NFL, NBA, MLB, NHL",
            "Building a Sustainable Betting System",
        ]
    },
    {
        "title":    "HOA Management Made Simple: Automate Your Community Operations",
        "subtitle": "A Step-by-Step Guide for Property Managers and Board Members",
        "niche":    "hoa_management",
        "keywords": ["HOA management", "homeowners association", "property management automation", "HOA board guide", "community management"],
        "price":    14.99,
        "chapters": [
            "The Modern HOA: Challenges and Opportunities",
            "Violation Tracking Systems That Actually Work",
            "Automating Owner Communications",
            "Financial Management and Reserve Funds",
            "Board Meeting Efficiency and Documentation",
            "Vendor Management and Maintenance Scheduling",
            "Handling Disputes Without the Headache",
            "Technology Tools for HOA Managers",
            "Legal Compliance and Risk Management",
            "Scaling From One Community to Many",
        ]
    },
    {
        "title":    "The Contractor's Playbook: Get More Jobs with Less Effort",
        "subtitle": "Lead Generation, Follow-Up Systems, and Closing Strategies for Contractors",
        "niche":    "contractor",
        "keywords": ["contractor lead generation", "construction business", "contractor marketing", "grow contracting business", "construction leads"],
        "price":    12.99,
        "chapters": [
            "Why Good Contractors Stay Broke (The Marketing Problem)",
            "Your Online Presence: What Actually Brings in Jobs",
            "Lead Generation Systems That Run Themselves",
            "The Follow-Up Process That Closes 30% More Jobs",
            "Pricing Strategy: Stop Leaving Money on the Table",
            "Referral Systems That Generate Consistent Work",
            "Seasonal Planning and Cash Flow Management",
            "Hiring and Subcontracting Without the Risk",
            "Customer Reviews: Your Most Powerful Marketing Tool",
            "Scaling to $1M+ Without Working More Hours",
        ]
    },
    {
        "title":    "Stock Trading for the Working Professional",
        "subtitle": "Build Passive Income Using AI Signals, Momentum Strategies, and Disciplined Risk Management",
        "niche":    "stock_trading",
        "keywords": ["stock trading beginners", "passive income stocks", "stock market signals", "swing trading", "momentum investing"],
        "price":    9.99,
        "chapters": [
            "Why 90% of Traders Lose (And How to Be in the 10%)",
            "Market Structure: What Actually Moves Prices",
            "Momentum Trading: The Edge That Works",
            "Using AI Signals Without Being a Tech Expert",
            "Risk Management: The Only Rule That Matters",
            "Position Sizing with the Kelly Criterion",
            "Reading Earnings and News Catalysts",
            "Congressional Trading Alerts: Follow the Smart Money",
            "Building Your Trading Routine (30 Minutes a Day)",
            "Scaling Up: From $10K to $100K Accounts",
        ]
    },
    {
        "title":    "AI for Small Business: Automate Everything and Work Less",
        "subtitle": "Practical AI Tools That Save 20+ Hours Per Week Without Technical Skills",
        "niche":    "ai_business",
        "keywords": ["AI small business", "business automation", "AI tools for business", "automate small business", "ChatGPT business"],
        "price":    12.99,
        "chapters": [
            "The AI Revolution Is Already Here (Are You Using It?)",
            "Email and Customer Communication on Autopilot",
            "Lead Generation While You Sleep",
            "AI Content Creation for Marketing",
            "Customer Service Automation That Feels Human",
            "Financial Tracking and Reporting",
            "Scheduling and Calendar Automation",
            "Social Media on Autopilot",
            "AI Tools That Are Actually Free (or Nearly Free)",
            "Building Your Full AI Business Stack",
        ]
    },
]


def generate_chapter(client, book_title: str, chapter_title: str, niche: str) -> str:
    prompt = f"""Write a detailed, practical chapter for a book titled "{book_title}".

Chapter: {chapter_title}

Requirements:
- 1,200-1,500 words
- Practical and actionable — real advice, not fluff
- Include specific examples, numbers, and tactics
- Write for a non-technical audience
- Use short paragraphs and bullet points where appropriate
- Do not include the chapter title in your response — just the content
- No filler phrases like "In this chapter we will explore..."

Write the chapter now:"""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text


def generate_intro(client, book: dict) -> str:
    prompt = f"""Write an introduction for a book titled "{book['title']}".

Subtitle: {book['subtitle']}
Chapters covered: {', '.join(book['chapters'])}

Requirements:
- 400-600 words
- Hook the reader immediately
- Explain what they'll learn and why it matters
- Personal and direct tone
- Do not use filler phrases

Write the introduction now:"""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text


def format_html(book: dict, intro: str, chapters: list) -> str:
    chapters_html = ""
    for i, (chapter_title, content) in enumerate(zip(book["chapters"], chapters), 1):
        paragraphs = content.strip().split("\n\n")
        content_html = ""
        for p in paragraphs:
            p = p.strip()
            if not p:
                continue
            if p.startswith("- ") or p.startswith("• "):
                items = [line.lstrip("- •").strip() for line in p.split("\n") if line.strip()]
                content_html += "<ul>" + "".join(f"<li>{item}</li>" for item in items) + "</ul>"
            elif re.match(r"^\d+\.", p):
                items = [re.sub(r"^\d+\.\s*", "", line).strip() for line in p.split("\n") if line.strip()]
                content_html += "<ol>" + "".join(f"<li>{item}</li>" for item in items) + "</ol>"
            elif p.isupper() or (len(p) < 80 and not p.endswith(".")):
                content_html += f"<h3>{p}</h3>"
            else:
                content_html += f"<p>{p}</p>"

        chapters_html += f"""
<div class="chapter">
  <h2>Chapter {i}: {chapter_title}</h2>
  {content_html}
</div>
"""

    intro_html = "".join(f"<p>{p}</p>" for p in intro.strip().split("\n\n") if p.strip())

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{book['title']}</title>
<style>
  body {{ font-family: Georgia, serif; max-width: 680px; margin: 40px auto; line-height: 1.8; color: #1a1a1a; font-size: 16px; }}
  h1 {{ font-size: 28px; margin-bottom: 8px; }}
  h2 {{ font-size: 22px; margin-top: 48px; border-bottom: 2px solid #333; padding-bottom: 8px; }}
  h3 {{ font-size: 18px; margin-top: 28px; }}
  p  {{ margin: 0 0 16px 0; }}
  ul, ol {{ margin: 0 0 16px 24px; }}
  li {{ margin-bottom: 8px; }}
  .subtitle {{ font-size: 18px; color: #555; margin-bottom: 32px; }}
  .author  {{ font-size: 16px; color: #777; margin-bottom: 48px; }}
  .chapter {{ margin-bottom: 60px; }}
  .toc {{ background: #f9f9f9; padding: 24px; border-radius: 6px; margin: 32px 0; }}
  .toc ol {{ margin: 8px 0 0 16px; }}
</style>
</head>
<body>

<h1>{book['title']}</h1>
<p class="subtitle">{book['subtitle']}</p>
<p class="author">Gray Horizons Enterprise | grayhorizonsenterprise.com</p>

<div class="toc">
  <strong>Table of Contents</strong>
  <ol>{''.join(f"<li>{ch}</li>" for ch in book['chapters'])}</ol>
</div>

<div class="chapter">
  <h2>Introduction</h2>
  {intro_html}
</div>

{chapters_html}

<hr>
<p style="text-align:center;color:#777;font-size:14px;">
  © {datetime.now().year} Gray Horizons Enterprise. All rights reserved.<br>
  grayhorizonsenterprise.com
</p>

</body>
</html>"""


def run():
    if not ANTHROPIC_KEY:
        print("[KDP] No ANTHROPIC_API_KEY — set it in Railway or .env")
        return

    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    manifest = []

    for book in EBOOKS:
        safe_title = re.sub(r"[^\w]", "_", book["title"][:40]).strip("_")
        out_path   = os.path.join(EBOOK_DIR, f"{safe_title}.html")

        if os.path.exists(out_path):
            print(f"[KDP] Already exists: {book['title'][:50]} — skipping")
            manifest.append({"title": book["title"], "file": out_path, "price": book["price"], "status": "existing"})
            continue

        print(f"\n[KDP] Generating: {book['title'][:60]}...")

        try:
            print("  Writing introduction...")
            intro = generate_intro(client, book)
            time.sleep(1)

            chapters = []
            for i, chapter_title in enumerate(book["chapters"], 1):
                print(f"  Chapter {i}/{len(book['chapters'])}: {chapter_title[:50]}...")
                content = generate_chapter(client, book["title"], chapter_title, book["niche"])
                chapters.append(content)
                time.sleep(0.8)

            html = format_html(book, intro, chapters)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(html)

            manifest.append({
                "title":    book["title"],
                "subtitle": book["subtitle"],
                "keywords": ", ".join(book["keywords"]),
                "price":    book["price"],
                "file":     out_path,
                "status":   "generated",
            })

            print(f"  [OK] Saved to {out_path}")

        except Exception as e:
            print(f"  [ERROR] {e}")
            continue

    manifest_path = os.path.join(EBOOK_DIR, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\n[KDP] Done — {len(manifest)} ebooks ready in {EBOOK_DIR}/")
    print("[KDP] Upload each HTML file to KDP at kdp.amazon.com")
    print("[KDP] Set prices as listed in manifest.json")
    print(f"[KDP] Estimated passive income at 100 sales/book/month: ${sum(b['price'] * 100 * 0.35 for b in EBOOKS):,.0f}/month")


if __name__ == "__main__":
    run()
