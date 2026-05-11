"""
clean_ebooks.py — removes AI-generated patterns from ebook HTML files
Fixes: markdown headers in h tags, **bold**, *italic*, -- double hyphens, - bullet lists in p tags
"""
import re
import os
import glob

EBOOK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ebooks")

def clean(html):
    # Remove markdown # prefixes inside h2/h3 tags
    html = re.sub(r'(<h[23][^>]*>)\s*#{1,3}\s*', r'\1', html)

    # Convert **bold** to <strong>
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)

    # Convert *italic* to <em>
    html = re.sub(r'\*([^*\n]+?)\*', r'<em>\1</em>', html)

    # Remove double hyphens
    html = html.replace('--', '-')

    # Remove triple dashes
    html = html.replace('---', '-')

    # Fix markdown bullet lists inside <p> tags — convert to proper ul/li
    def fix_bullets(m):
        block = m.group(0)
        lines = block.split('\n')
        result = []
        in_list = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('- '):
                if not in_list:
                    result.append('<ul>')
                    in_list = True
                result.append(f'<li>{stripped[2:]}</li>')
            else:
                if in_list:
                    result.append('</ul>')
                    in_list = False
                result.append(line)
        if in_list:
            result.append('</ul>')
        return '\n'.join(result)

    # Fix bullet lists inside <p> tags
    html = re.sub(r'<p>[^<]*(?:\n- [^\n]+)+[^<]*</p>', fix_bullets, html)

    # Remove stray # at start of <p> content
    html = re.sub(r'<p>\s*#+\s*', '<p>', html)

    # Fix markdown table inside <p> (just remove the table wrapper)
    html = re.sub(r'<p>(\|.+?\|)\n</p>', r'<p>\1</p>', html, flags=re.DOTALL)

    # Remove excessive "In conclusion", "Furthermore", "Moreover" — AI tells
    for phrase in ["In conclusion,", "Furthermore,", "Moreover,", "It's worth noting that", "It is worth noting that"]:
        html = html.replace(phrase, "")

    # Clean up empty <h3> tags that just had markdown content removed
    html = re.sub(r'<h3>\s*</h3>', '', html)

    # Normalize multiple blank lines
    html = re.sub(r'\n{3,}', '\n\n', html)

    return html


files = glob.glob(os.path.join(EBOOK_DIR, "*.html"))
for path in files:
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    cleaned = clean(content)
    with open(path, "w", encoding="utf-8") as f:
        f.write(cleaned)
    print(f"[OK] Cleaned: {os.path.basename(path)}")

print(f"\nDone — {len(files)} files cleaned.")
