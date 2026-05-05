from collections import namedtuple

Choice = namedtuple("Choice", ["text", "tags"])

# ---------- 1) CLASSIFY ----------
def classify(name):
    n = name.lower()
    if "fail" in n: return "fail"
    if "zoom" in n or "dog" in n: return "energy"
    if "chimp" in n or "monkey" in n: return "reaction"
    if "baby" in n or "cute" in n: return "cute"
    if "unexpected" in n or "reaction" in n: return "unexpected"
    return "neutral"

# ---------- 2) CANDIDATE BANKS ----------
TITLES = {
    "fail": [
        Choice("it really thought it had it… 😭 #shorts", {"fail","instant","turn"}),
        Choice("this is where it goes wrong… 😭 #shorts", {"fail","turn"}),
        Choice("the confidence before this… 😭 #shorts", {"fail","setup"}),
    ],
    "reaction": [
        Choice("why did it look back like that… 😳 #shorts", {"specific","lookback","watch_ok"}),
        Choice("it paused for a reason… 😳 #shorts", {"pause","reason"}),
        Choice("that reaction wasn't normal… 😳 #shorts", {"abnormal"}),
    ],
    "energy": [
        Choice("it switched up instantly… 😳 #shorts", {"instant","switch"}),
        Choice("that change was immediate… 😳 #shorts", {"instant"}),
        Choice("the shift happened so fast… 😳 #shorts", {"instant","specific"}),
    ],
    "cute": [
        Choice("this is actually too cute… 😭 #shorts", {"cute"}),
        Choice("i wasn't ready for that… 😭 #shorts", {"surprise","cute"}),
        Choice("that tiny reaction 😭 #shorts", {"micro","cute"}),
    ],
    "unexpected": [
        Choice("this part doesn't make sense… 😳 #shorts", {"confusion"}),
        Choice("something changes right here… 😳 #shorts", {"turn"}),
        Choice("this wasn't supposed to happen… 😳 #shorts", {"assumption_break"}),
        Choice("look at what happens next… 😳 #shorts", {"watch_ok","specific"}),
    ],
    "neutral": [
        Choice("something about this feels off… 😳 #shorts", {"unease"}),
        Choice("this isn't normal behavior… 😳 #shorts", {"abnormal"}),
        Choice("why did it do that… 😳 #shorts", {"specific"}),
        Choice("i replayed this 6 times… 😳 #shorts", {"replay"}),
        Choice("nobody taught it that… 😳 #shorts", {"intelligence"}),
        Choice("it made a decision right here… 😳 #shorts", {"specific"}),
        Choice("the moment it realized… 😳 #shorts", {"moment"}),
    ],
}

DESCS = [
    Choice("it felt normal at first… then something shifted 😳\n#animals #wildlife #shorts", {"shift"}),
    Choice("you can see the exact moment it changes 😳\n#animals #shorts", {"moment"}),
    Choice("that hesitation says everything 😳\n#animals #viral #shorts", {"hesitation"}),
    Choice("started normal… then this happened 😳\n#animals #shorts", {"turn"}),
    Choice("i've never seen an animal do this unprompted 😳\n#animals #wildlife #viral #shorts", {"intelligence"}),
    Choice("nobody taught it that. it just knew. 😳\n#animals #shorts #viral", {"intelligence"}),
    Choice("the part at the end is what got me 😳\n#animals #shorts #viral", {"moment"}),
]

PINS = [
    Choice("did you catch that??", {"question"}),
    Choice("watch it again", {"replay"}),
    Choice("nah that wasn't random", {"assertion"}),
    Choice("what do you think happened there?", {"opinion"}),
    Choice("you saw that too right?", {"agreement"}),
    Choice("the part at the end got me", {"moment"}),
    Choice("i can't stop replaying this", {"replay"}),
    Choice("it knew exactly what it was doing", {"assertion"}),
]

# ---------- 3) POSTED TITLE BLOCKLIST ----------
import os as _os

_BLOCKLIST_PATH = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "posted_titles.txt")

def _clean(title):
    return title.split(" #")[0].split(" 😳")[0].split(" 😭")[0].strip().lower()

def _load_blocklist():
    if not _os.path.exists(_BLOCKLIST_PATH):
        return set()
    with open(_BLOCKLIST_PATH, encoding="utf-8") as f:
        return {_clean(line) for line in f if line.strip()}

# ---------- 4) BATCH DEDUP ----------
recent_titles = _load_blocklist()

def unique_title(t):
    clean = _clean(t)
    if clean in recent_titles:
        t = t.replace("…", "… (watch closely)")
    else:
        # genuinely new title — write once, never again
        recent_titles.add(clean)
        with open(_BLOCKLIST_PATH, "a", encoding="utf-8") as f:
            f.write(clean + "\n")
    return t

# ---------- 4) SCORING ----------
def score_title(choice, kind, duration_sec):
    s = 0
    if "specific" in choice.tags:     s += 2
    if "intelligence" in choice.tags: s += 1
    if "moment" in choice.tags:       s += 1
    if kind == "fail"       and "fail"       in choice.tags: s += 3
    if kind == "fail"       and "setup"      in choice.tags: s += 1
    if kind == "reaction"   and "pause"      in choice.tags: s += 3
    if kind == "reaction"   and "abnormal"   in choice.tags: s += 2
    if kind == "energy"     and "instant"    in choice.tags: s += 3
    if kind == "energy"     and "movement"   in choice.tags: s += 2
    if kind == "cute"       and "micro"      in choice.tags: s += 4
    if kind == "cute"       and "cute"       in choice.tags: s += 3
    if kind == "cute"       and "surprise"   in choice.tags: s += 2
    if kind == "unexpected" and "confusion"  in choice.tags: s += 3
    if kind == "unexpected" and "assumption_break" in choice.tags: s += 2
    if kind == "unexpected" and "turn"       in choice.tags: s += 1
    if kind == "neutral"    and "specific"   in choice.tags: s += 2
    if duration_sec and duration_sec <= 8 and "instant" in choice.tags: s += 1
    if "unease" in choice.tags: s -= 1
    # watch/look hooks only when payoff is confirmed
    text_lower = choice.text.lower()
    has_watch_word = "watch" in text_lower or "look" in text_lower
    payoff_kind    = kind in ("reaction", "unexpected")
    if has_watch_word and not payoff_kind and "watch_ok" not in choice.tags:
        s -= 3
    return s

def score_desc(choice, kind):
    s = 0
    if "shift"       in choice.tags: s += 2
    if "turn"        in choice.tags: s += 2
    if "moment"      in choice.tags: s += 1
    if kind == "reaction"  and "hesitation"   in choice.tags: s += 3
    if kind == "neutral"   and "intelligence" in choice.tags: s += 3
    if kind == "cute"      and "moment"       in choice.tags: s += 2
    if kind == "fail"      and "turn"         in choice.tags: s += 2
    if kind == "energy"    and "shift"        in choice.tags: s += 2
    if kind == "unexpected" and "turn"        in choice.tags: s += 2
    return s

def score_pin(choice):
    if "replay"   in choice.tags: return 3
    if "question" in choice.tags: return 2
    if "opinion"  in choice.tags: return 2
    if "assertion" in choice.tags: return 1
    return 0

# ---------- 5) SELECT (fully deterministic — score wins, no randomness) ----------
def pick_best(options, score_fn, *args):
    scored = [(score_fn(opt, *args) if args else score_fn(opt), opt) for opt in options]
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]

# ---------- 6) PUBLIC API ----------
def generate_metadata(filename, duration_sec=7):
    kind  = classify(filename)
    title = unique_title(
        pick_best(TITLES.get(kind, TITLES["neutral"]), score_title, kind, duration_sec).text
    )
    desc  = pick_best(DESCS, score_desc, kind).text
    pin   = pick_best(PINS, score_pin).text
    return title, desc, pin

def reset_batch():
    """Reset per-session dedup but keep the permanent posted blocklist."""
    recent_titles.clear()
    recent_titles.update(_load_blocklist())
