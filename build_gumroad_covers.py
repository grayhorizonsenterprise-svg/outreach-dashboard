"""
build_gumroad_covers.py
Generates book-style Gumroad covers (1280x720) and thumbnails (600x600)
for the 3 business guide products.
"""
from PIL import Image, ImageDraw, ImageFont
import os

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "indicators")
os.makedirs(OUT, exist_ok=True)

COVER_W, COVER_H = 1280, 720
THUMB_W, THUMB_H = 600, 600

def load_font(size, bold=True):
    candidates = ["arialbd.ttf", "arial.ttf", "calibrib.ttf", "calibri.ttf", "segoeui.ttf"]
    if not bold:
        candidates = ["arial.ttf", "calibri.ttf", "segoeui.ttf"] + candidates
    for name in candidates:
        try:
            return ImageFont.truetype(f"C:/Windows/Fonts/{name}", size)
        except:
            pass
    return ImageFont.load_default()

def draw_wrapped(draw, text, font, x, y, max_width, fill, line_height):
    words = text.split()
    lines = []
    current = ""
    for w in words:
        test = (current + " " + w).strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] > max_width and current:
            lines.append(current)
            current = w
        else:
            current = test
    if current:
        lines.append(current)
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height
    return y

def vertical_gradient(img, top_color, bottom_color):
    w, h = img.size
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        r = int(top_color[0] + (bottom_color[0] - top_color[0]) * t)
        g = int(top_color[1] + (bottom_color[1] - top_color[1]) * t)
        b = int(top_color[2] + (bottom_color[2] - top_color[2]) * t)
        draw.line([(0, y), (w, y)], fill=(r, g, b))
    return img

def make_cover(title, subtitle, tagline, top_color, bottom_color, accent, out_name, icon_char=None):
    img = Image.new("RGB", (COVER_W, COVER_H))
    img = vertical_gradient(img, top_color, bottom_color)
    draw = ImageDraw.Draw(img)

    # Accent bar left
    draw.rectangle([(56, 56), (66, COVER_H - 56)], fill=accent)

    # GHE brand
    font_brand = load_font(22, bold=False)
    draw.text((84, 70), "GRAY HORIZONS ENTERPRISE", font=font_brand, fill=(180, 180, 180))

    # Large icon on right side
    if icon_char:
        font_icon = load_font(260)
        bbox = draw.textbbox((0, 0), icon_char, font=font_icon)
        iw = bbox[2] - bbox[0]
        ih = bbox[3] - bbox[1]
        ix = COVER_W - iw - 80
        iy = (COVER_H - ih) // 2
        r, g, b = accent
        draw.text((ix, iy), icon_char, font=font_icon, fill=(r, g, b, 40))

    # Title
    font_title = load_font(78)
    y = 120
    y = draw_wrapped(draw, title, font_title, 84, y, 700, (255, 255, 255), 88)

    # Accent line
    draw.rectangle([(84, y + 14), (84 + 380, y + 18)], fill=accent)
    y += 42

    # Subtitle
    font_sub = load_font(36)
    y = draw_wrapped(draw, subtitle, font_sub, 84, y, 700, accent, 46)
    y += 10

    # Tagline
    font_tag = load_font(24, bold=False)
    draw_wrapped(draw, tagline, font_tag, 84, y, 700, (190, 190, 190), 34)

    # Bottom domain
    font_domain = load_font(20, bold=False)
    draw.text((84, COVER_H - 48), "grayhorizonsenterprise.com", font=font_domain, fill=(140, 140, 140))

    # Save cover (square)
    cover_path = os.path.join(OUT, f"{out_name}-Cover.png")
    img.save(cover_path)
    print(f"  Saved cover: {cover_path}")

    # Thumbnail — square crop from left portion of cover
    thumb = img.crop((0, 0, COVER_H, COVER_H))
    thumb = thumb.resize((THUMB_W, THUMB_H), Image.LANCZOS)
    thumb_path = os.path.join(OUT, f"{out_name}-Thumb.png")
    thumb.save(thumb_path)
    print(f"  Saved thumb: {thumb_path}")


PRODUCTS = [
    {
        "title": "AI for Small Business",
        "subtitle": "Automate Everything. Work Less.",
        "tagline": "The exact systems used to run a real service business without hiring more people or working more hours.",
        "top": (10, 22, 38),
        "bottom": (5, 38, 28),
        "accent": (0, 210, 150),
        "icon": "AI",
        "out": "GHE-AI-Small-Business",
    },
    {
        "title": "The Contractor's Playbook",
        "subtitle": "Get More Jobs. Chase Less.",
        "tagline": "The lead follow-up and booking system that runs in the background so you can stay on the job site.",
        "top": (24, 14, 6),
        "bottom": (10, 20, 30),
        "accent": (255, 140, 0),
        "icon": "C",
        "out": "GHE-Contractors-Playbook",
    },
    {
        "title": "HOA Management Made Simple",
        "subtitle": "Automate Your Community Operations.",
        "tagline": "Violation tracking, homeowner communication, and follow-up — handled automatically so your team focuses on what matters.",
        "top": (8, 18, 38),
        "bottom": (4, 10, 28),
        "accent": (80, 160, 255),
        "icon": "H",
        "out": "GHE-HOA-Management",
    },
]

if __name__ == "__main__":
    print("Building Gumroad covers...\n")
    for p in PRODUCTS:
        print(f"[{p['out']}]")
        make_cover(
            p["title"], p["subtitle"], p["tagline"],
            p["top"], p["bottom"], p["accent"],
            p["out"], p.get("icon"),
        )
    print("\nDone. Upload from indicators/ folder to Gumroad.")
