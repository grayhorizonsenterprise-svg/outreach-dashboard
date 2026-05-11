"""
html_to_pdf.py — converts all ebook HTML files to PDF using Chrome headless
"""
import subprocess
import os
import glob

EBOOK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ebooks")

CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]

def find_browser():
    for path in CHROME_PATHS:
        if os.path.exists(path):
            return path
    return None

browser = find_browser()
if not browser:
    print("[ERROR] Chrome or Edge not found. Install Chrome and try again.")
    exit(1)

print(f"[PDF] Using browser: {browser}")

html_files = glob.glob(os.path.join(EBOOK_DIR, "*.html"))

for html_path in html_files:
    pdf_path = html_path.replace(".html", ".pdf")
    file_url = "file:///" + html_path.replace("\\", "/")

    cmd = [
        browser,
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        f"--print-to-pdf={pdf_path}",
        "--print-to-pdf-no-header",
        file_url,
    ]

    print(f"[PDF] Converting: {os.path.basename(html_path)}")
    try:
        subprocess.run(cmd, timeout=60, capture_output=True)
        if os.path.exists(pdf_path):
            size = os.path.getsize(pdf_path)
            print(f"[OK]  Saved: {os.path.basename(pdf_path)} ({size:,} bytes)")
        else:
            print(f"[FAIL] PDF not created for {os.path.basename(html_path)}")
    except Exception as e:
        print(f"[ERROR] {e}")

print(f"\nDone — PDFs saved in {EBOOK_DIR}")
