"""
Email Notification — Grant Digest

Sends a formatted daily digest of top-matched grants to notify_email in user_profile.json.
Uses Gmail SMTP (or any SMTP server). Set credentials in .env.

Required .env keys:
    NOTIFY_EMAIL=you@gmail.com
    SMTP_HOST=smtp.gmail.com
    SMTP_PORT=587
    SMTP_USER=you@gmail.com
    SMTP_PASSWORD=your-app-password   ← Gmail App Password (not your main password)
"""
import json
import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from datetime import date

# Load config from .env manually (avoid circular import)
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
NOTIFY_EMAIL = os.getenv("NOTIFY_EMAIL", "")


def _load_profile() -> dict:
    p = Path(__file__).parent.parent / "user_profile.json"
    return json.loads(p.read_text()) if p.exists() else {}


def _fmt_amount(amount_max: int) -> str:
    if not amount_max:
        return "Amount TBD"
    if amount_max >= 1_000_000:
        return f"${amount_max/1_000_000:.1f}M"
    if amount_max >= 1_000:
        return f"${amount_max/1_000:.0f}K"
    return f"${amount_max:,}"


def _effort_emoji(level: str) -> str:
    return {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(level, "⚪")


def build_html_digest(grants: list[dict], scan_stats: dict = None) -> str:
    """Build a clean HTML email with top grants."""
    today = date.today().strftime("%B %d, %Y")
    count = len(grants)

    rows = ""
    for g in grants[:20]:  # Cap at 20 in email
        score = g.get("match_score", 0)
        score_color = "#3fb950" if score >= 70 else "#d29922" if score >= 50 else "#f85149"
        amount = _fmt_amount(g.get("amount_max", 0))
        deadline = g.get("deadline") or "Rolling"
        effort = _effort_emoji(g.get("effort_level", "medium"))
        win = g.get("win_probability", 0)
        url = g.get("url", "#")
        name = g.get("name", "—")
        source = g.get("source", "")

        rows += f"""
        <tr style="border-bottom:1px solid #30363d;">
          <td style="padding:12px 8px;text-align:center;">
            <span style="background:{score_color}22;color:{score_color};border:1px solid {score_color}44;
              border-radius:50%;width:38px;height:38px;display:inline-flex;align-items:center;
              justify-content:center;font-weight:700;font-size:13px;">{score}</span>
          </td>
          <td style="padding:12px 8px;">
            <a href="{url}" style="color:#58a6ff;text-decoration:none;font-weight:500;">{name}</a>
            <div style="color:#8b949e;font-size:11px;margin-top:2px;">{source}</div>
          </td>
          <td style="padding:12px 8px;color:#3fb950;font-weight:600;">{amount}</td>
          <td style="padding:12px 8px;color:#e6edf3;">{deadline}</td>
          <td style="padding:12px 8px;">{effort} {win}%</td>
        </tr>"""

    stats_html = ""
    if scan_stats:
        stats_html = f"""
        <div style="display:flex;gap:20px;margin:16px 0;flex-wrap:wrap;">
          <div style="background:#21262d;border:1px solid #30363d;border-radius:8px;padding:14px 20px;flex:1;min-width:120px;">
            <div style="color:#8b949e;font-size:11px;text-transform:uppercase;">Grants Found</div>
            <div style="font-size:24px;font-weight:700;color:#3fb950;">{scan_stats.get('total', 0)}</div>
          </div>
          <div style="background:#21262d;border:1px solid #30363d;border-radius:8px;padding:14px 20px;flex:1;min-width:120px;">
            <div style="color:#8b949e;font-size:11px;text-transform:uppercase;">High Match</div>
            <div style="font-size:24px;font-weight:700;color:#58a6ff;">{scan_stats.get('high_match', 0)}</div>
          </div>
          <div style="background:#21262d;border:1px solid #30363d;border-radius:8px;padding:14px 20px;flex:1;min-width:120px;">
            <div style="color:#8b949e;font-size:11px;text-transform:uppercase;">New Today</div>
            <div style="font-size:24px;font-weight:700;color:#f0883e;">{scan_stats.get('new_today', 0)}</div>
          </div>
        </div>"""

    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"/></head>
<body style="background:#0d1117;color:#e6edf3;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;margin:0;padding:0;">
  <div style="max-width:700px;margin:0 auto;padding:32px 24px;">

    <div style="margin-bottom:24px;">
      <h1 style="font-size:20px;font-weight:700;margin:0;">
        Grant Agent <span style="color:#3fb950;">Daily Digest</span>
      </h1>
      <p style="color:#8b949e;font-size:13px;margin:4px 0 0;">{today} — {count} matching grants found</p>
    </div>

    {stats_html}

    <div style="background:#161b22;border:1px solid #30363d;border-radius:8px;overflow:hidden;margin-top:20px;">
      <table style="width:100%;border-collapse:collapse;">
        <thead>
          <tr style="background:#21262d;">
            <th style="padding:10px 8px;text-align:center;font-size:11px;color:#8b949e;text-transform:uppercase;">Score</th>
            <th style="padding:10px 8px;text-align:left;font-size:11px;color:#8b949e;text-transform:uppercase;">Grant</th>
            <th style="padding:10px 8px;text-align:left;font-size:11px;color:#8b949e;text-transform:uppercase;">Amount</th>
            <th style="padding:10px 8px;text-align:left;font-size:11px;color:#8b949e;text-transform:uppercase;">Deadline</th>
            <th style="padding:10px 8px;text-align:left;font-size:11px;color:#8b949e;text-transform:uppercase;">Effort / Win%</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>

    <div style="margin-top:24px;text-align:center;">
      <a href="http://localhost:8000" style="background:#3fb950;color:#000;padding:12px 28px;border-radius:6px;text-decoration:none;font-weight:600;font-size:14px;">
        Open Dashboard →
      </a>
    </div>

    <p style="color:#30363d;font-size:11px;text-align:center;margin-top:24px;">
      Grant Agent System — GRAY HORIZONS ENTERPRISE
    </p>
  </div>
</body>
</html>"""
    return html


def send_digest(grants: list[dict], scan_stats: dict = None) -> bool:
    """Send the grant digest email. Returns True on success."""
    profile = _load_profile()

    # Determine recipient — .env takes priority, then profile
    to_email = NOTIFY_EMAIL or profile.get("notify_email") or profile.get("contact", {}).get("email", "")
    from_email = SMTP_USER

    if not to_email:
        print("[Email] No notify_email set. Add NOTIFY_EMAIL to .env to receive digests.")
        return False

    if not SMTP_USER or not SMTP_PASSWORD:
        print("[Email] SMTP_USER or SMTP_PASSWORD not set in .env. Email skipped.")
        return False

    if not grants:
        print("[Email] No grants to report. Skipping digest.")
        return False

    today = date.today().strftime("%B %d, %Y")
    count = len(grants)
    top_score = grants[0].get("match_score", 0) if grants else 0

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[Grant Agent] {count} Opportunities Found — Top Match: {top_score}/100 | {today}"
    msg["From"] = f"Grant Agent <{from_email}>"
    msg["To"] = to_email

    # Plain text fallback
    plain = f"Grant Agent Daily Digest — {today}\n\n"
    plain += f"{count} grants found. Top {min(5, count)} matches:\n\n"
    for g in grants[:5]:
        plain += f"  [{g.get('match_score', 0)}/100] {g.get('name', '—')}\n"
        plain += f"    Amount: {_fmt_amount(g.get('amount_max', 0))} | Deadline: {g.get('deadline', 'Rolling')}\n"
        plain += f"    {g.get('url', '')}\n\n"
    plain += "\nOpen dashboard: http://localhost:8000\n"

    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(build_html_digest(grants, scan_stats), "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(from_email, to_email, msg.as_string())
        print(f"[Email] Digest sent to {to_email} — {count} grants")
        return True
    except Exception as e:
        print(f"[Email] Failed to send: {e}")
        return False
