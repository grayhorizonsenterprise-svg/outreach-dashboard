"""
Gray Horizons Enterprise — Comment Bank Generator
Generates 100 unique comments to post on TikTok/YouTube business videos.
Target: small business owners posting about marketing, promotions, growth.

Usage:
  python comment_generator.py
  -> prints 100 comments + saves to comments_today.txt
"""

import random

# =========================
# WHERE TO DROP THESE COMMENTS
# =========================
# Search TikTok / YouTube for:
#   "small business promotion"
#   "business marketing tips"
#   "how to get more clients"
#   "small business growth"
#   "social media for business"
#   "how I grew my business"
#   "business owner content"

# =========================
# COMMENT POOL
# Hook: make them feel seen. Not a pitch.
# =========================

OPENERS = [
    "genuine question —",
    "honest question for you —",
    "not trying to be negative but —",
    "real question —",
    "curious about this —",
    "just wondering —",
    "asking as someone who watches a lot of business content —",
    "not a pitch just a real question —",
    "something i always wonder when i see content like this —",
]

HOOKS = [
    "are you actually getting customers from this content or just views?",
    "how many of these views are turning into actual paying clients?",
    "is this converting into leads for you or just building awareness?",
    "do you track how many clients come directly from your videos?",
    "are the comments here turning into bookings or just engagement?",
    "how many people watching this actually reach out to work with you?",
    "is the content driving revenue or just growing the account?",
    "do you have a system for converting viewers into clients from this?",
    "curious if this is generating actual business or just followers?",
    "how are you turning these views into actual customers?",
]

FOLLOWUPS = [
    "most businesses i talk to say the content gets views but the phone doesn't ring.",
    "a lot of business owners i speak with have the same problem — great content, low conversion.",
    "most people i see posting great content never connect it to a sales system.",
    "the gap between views and actual revenue is where most businesses get stuck.",
    "most small businesses i talk to are posting consistently but not seeing it in the revenue.",
    "a lot of owners i see posting content say the same thing — views don't pay the bills.",
    "content without a conversion system is just expensive visibility.",
    "most business pages i watch have good content but no system to close from it.",
]

CLOSERS = [
    "we help businesses build that bridge. just curious how you're handling it.",
    "we actually help businesses close that gap. just curious what your setup looks like.",
    "we work specifically on that problem. just genuinely curious how you're approaching it.",
    "genuinely curious — do you have something in place for that?",
    "asking because that's the exact problem we solve. not a pitch, just curious.",
    "that's literally what we do for businesses. just wanted to ask the real question.",
    "we help with exactly that. curious if it's something you've thought about.",
    "we actually specialize in that piece. just wanted to ask the honest question.",
]

# =========================
# SEARCH TERMS TO TARGET
# (post these comments on videos matching these searches)
# =========================
TARGET_SEARCHES = [
    "small business promotion tips",
    "how to get more clients social media",
    "small business marketing strategy",
    "business owner content creation",
    "how I grew my small business",
    "social media for local business",
    "business tips for entrepreneurs",
    "how to get customers online",
    "small business growth tips 2025",
    "local business marketing ideas",
]


def generate_comment() -> str:
    opener   = random.choice(OPENERS)
    hook     = random.choice(HOOKS)
    followup = random.choice(FOLLOWUPS)
    closer   = random.choice(CLOSERS)
    return f"{opener} {hook} {followup} {closer}"


def build_bank(n: int = 100) -> list[str]:
    seen = set()
    bank = []
    attempts = 0
    while len(bank) < n and attempts < n * 10:
        attempts += 1
        c = generate_comment()
        key = c[:60]
        if key not in seen:
            seen.add(key)
            bank.append(c)
    return bank


def main():
    print("\n" + "=" * 60)
    print("  COMMENT BANK — GRAY HORIZONS ENTERPRISE")
    print("=" * 60)
    print("\nWhere to drop these:")
    for s in TARGET_SEARCHES:
        print(f"  TikTok/YouTube search: \"{s}\"")

    print("\n" + "=" * 60)
    print("  100 COMMENTS (copy one, paste, repeat)")
    print("=" * 60 + "\n")

    bank = build_bank(100)

    output_lines = []
    for i, comment in enumerate(bank, 1):
        line = f"[{i:03d}] {comment}"
        print(line)
        output_lines.append(line)

    out_file = "comments_today.txt"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write("WHERE TO POST:\n")
        for s in TARGET_SEARCHES:
            f.write(f'  Search: "{s}"\n')
        f.write("\nCOMMENTS:\n\n")
        f.write("\n\n".join(output_lines))

    print(f"\n[SAVED] {out_file}")
    print(f"[GOAL]  Post 50-100 today. Check back in 2-4 hours for replies.")
    print("\nWHEN SOMEONE REPLIES OR FOLLOWS:")
    print("  -> open response_scripts.txt")
    print("  -> pick Stage 1 reply, send it, wait")
    print("=" * 60)


if __name__ == "__main__":
    main()
