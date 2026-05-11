"""
fix_toc.py — adds proper anchor-linked Table of Contents to all ebook HTML files
KDP requires NCX/HTML TOC with id anchors on headings.
"""
import re
import os
import glob

EBOOK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ebooks")

def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return text[:50]

def fix_toc(html):
    # Find all h2 headings
    headings = re.findall(r'<h2[^>]*>(.*?)</h2>', html)

    # Add id attributes to each h2
    counter = [0]
    def add_id(m):
        tag_attrs = m.group(1)
        content = m.group(2)
        clean = re.sub(r'<[^>]+>', '', content).strip()
        slug = slugify(clean)
        if not slug:
            slug = f"section-{counter[0]}"
        counter[0] += 1
        return f'<h2 id="{slug}"{tag_attrs}>{content}</h2>'

    html = re.sub(r'<h2([^>]*)>(.*?)</h2>', add_id, html)

    # Build new TOC from the anchored headings
    anchored = re.findall(r'<h2 id="([^"]+)"[^>]*>(.*?)</h2>', html)

    toc_items = ""
    for slug, title in anchored:
        clean_title = re.sub(r'<[^>]+>', '', title).strip()
        toc_items += f'    <li><a href="#{slug}">{clean_title}</a></li>\n'

    new_toc = f'''<div class="toc">
  <strong>Table of Contents</strong>
  <ol>
{toc_items}  </ol>
</div>'''

    # Replace existing toc div
    html = re.sub(r'<div class="toc">.*?</div>', new_toc, html, flags=re.DOTALL)

    return html


files = glob.glob(os.path.join(EBOOK_DIR, "*.html"))
for path in files:
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    fixed = fix_toc(content)
    with open(path, "w", encoding="utf-8") as f:
        f.write(fixed)
    print(f"[OK] TOC fixed: {os.path.basename(path)}")

print(f"\nDone — {len(files)} files updated. Re-upload each HTML to KDP.")
