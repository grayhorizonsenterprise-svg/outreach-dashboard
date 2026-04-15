import sqlite3
import json
import os
from pathlib import Path
from datetime import datetime

DB_PATH = Path(os.environ.get("DB_PATH", str(Path(__file__).parent.parent / "grant_agent.db")))


def get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS grants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            external_id TEXT,
            name TEXT NOT NULL,
            amount_min INTEGER DEFAULT 0,
            amount_max INTEGER DEFAULT 0,
            deadline TEXT,
            eligibility TEXT,
            description TEXT,
            url TEXT,
            category TEXT,
            tags TEXT,
            posted_date TEXT,
            match_score INTEGER DEFAULT 0,
            win_probability INTEGER DEFAULT 0,
            effort_level TEXT DEFAULT 'medium',
            days_to_apply INTEGER DEFAULT 7,
            status TEXT DEFAULT 'new',
            discovered_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source, external_id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grant_id INTEGER REFERENCES grants(id),
            business_description TEXT,
            mission_statement TEXT,
            use_of_funds TEXT,
            impact_statement TEXT,
            full_narrative TEXT,
            claude_text TEXT,
            openai_text TEXT,
            synthesized_text TEXT,
            ai_mode TEXT DEFAULT 'claude',
            status TEXT DEFAULT 'draft',
            status_notes TEXT,
            generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Safely add columns to existing applications tables
    for col, typedef in [
        ("claude_text", "TEXT"),
        ("openai_text", "TEXT"),
        ("synthesized_text", "TEXT"),
        ("ai_mode", "TEXT DEFAULT 'claude'"),
        ("status_notes", "TEXT"),
        ("updated_at", "TEXT DEFAULT CURRENT_TIMESTAMP"),
    ]:
        try:
            c.execute(f"ALTER TABLE applications ADD COLUMN {col} {typedef}")
        except Exception:
            pass  # Column already exists

    c.execute("""
        CREATE TABLE IF NOT EXISTS scan_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scanned_at TEXT DEFAULT CURRENT_TIMESTAMP,
            source TEXT,
            grants_found INTEGER DEFAULT 0,
            grants_new INTEGER DEFAULT 0,
            error TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS status_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER REFERENCES applications(id),
            grant_id INTEGER REFERENCES grants(id),
            old_status TEXT,
            new_status TEXT,
            notes TEXT,
            changed_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    print(f"[DB] Initialized at {DB_PATH}")


def upsert_grant(grant: dict) -> tuple[int, bool]:
    """Insert or update a grant. Returns (id, is_new)."""
    conn = get_conn()
    c = conn.cursor()

    c.execute(
        "SELECT id FROM grants WHERE source=? AND external_id=?",
        (grant.get("source"), grant.get("external_id"))
    )
    row = c.fetchone()

    tags = json.dumps(grant.get("tags", []))

    if row:
        c.execute("""
            UPDATE grants SET
                name=?, amount_min=?, amount_max=?, deadline=?,
                eligibility=?, description=?, url=?, category=?,
                tags=?, posted_date=?
            WHERE id=?
        """, (
            grant.get("name"), grant.get("amount_min", 0), grant.get("amount_max", 0),
            grant.get("deadline"), grant.get("eligibility"), grant.get("description"),
            grant.get("url"), grant.get("category"), tags,
            grant.get("posted_date"), row["id"]
        ))
        conn.commit()
        conn.close()
        return row["id"], False
    else:
        c.execute("""
            INSERT INTO grants
                (source, external_id, name, amount_min, amount_max, deadline,
                 eligibility, description, url, category, tags, posted_date)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            grant.get("source"), grant.get("external_id"),
            grant.get("name"), grant.get("amount_min", 0), grant.get("amount_max", 0),
            grant.get("deadline"), grant.get("eligibility"), grant.get("description"),
            grant.get("url"), grant.get("category"), tags, grant.get("posted_date")
        ))
        conn.commit()
        grant_id = c.lastrowid
        conn.close()
        return grant_id, True


def update_scores(grant_id: int, scores: dict):
    conn = get_conn()
    conn.execute("""
        UPDATE grants SET
            match_score=?, win_probability=?, effort_level=?, days_to_apply=?
        WHERE id=?
    """, (
        scores.get("match_score", 0),
        scores.get("win_probability", 0),
        scores.get("effort_level", "medium"),
        scores.get("days_to_apply", 7),
        grant_id
    ))
    conn.commit()
    conn.close()


def get_grants(
    min_score: int = 0,
    status: str = None,
    limit: int = 50,
    search: str = None
) -> list[dict]:
    conn = get_conn()
    query = "SELECT * FROM grants WHERE match_score >= ?"
    params: list = [min_score]

    if status:
        query += " AND status=?"
        params.append(status)

    if search:
        query += " AND (name LIKE ? OR description LIKE ? OR eligibility LIKE ?)"
        term = f"%{search}%"
        params.extend([term, term, term])

    query += " ORDER BY match_score DESC, deadline ASC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_grant_by_id(grant_id: int) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM grants WHERE id=?", (grant_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def save_application(grant_id: int, app: dict) -> int:
    """Save a generated application. Supports claude-only and dual-AI modes."""
    conn = get_conn()
    c = conn.cursor()
    ai_mode = app.get("ai_mode", "claude")
    now = datetime.utcnow().isoformat()
    c.execute("""
        INSERT INTO applications
            (grant_id, business_description, mission_statement,
             use_of_funds, impact_statement, full_narrative,
             claude_text, openai_text, synthesized_text, ai_mode,
             status, generated_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        grant_id,
        app.get("business_description"),
        app.get("mission_statement"),
        app.get("use_of_funds"),
        app.get("impact_statement"),
        app.get("full_narrative"),
        app.get("claude_text"),
        app.get("openai_text"),
        app.get("synthesized_text"),
        ai_mode,
        "draft",
        now,
        now,
    ))
    conn.commit()
    app_id = c.lastrowid
    conn.close()
    return app_id


def get_application(app_id: int) -> dict | None:
    """Get a single application with its grant name."""
    conn = get_conn()
    row = conn.execute("""
        SELECT a.*, g.name AS grant_name, g.amount_max, g.deadline, g.url AS grant_url,
               g.match_score, g.win_probability
        FROM applications a
        LEFT JOIN grants g ON g.id = a.grant_id
        WHERE a.id=?
    """, (app_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_applications(status: str = None, limit: int = 100) -> list[dict]:
    """List all applications with grant info, newest first."""
    conn = get_conn()
    query = """
        SELECT a.*, g.name AS grant_name, g.amount_max, g.deadline,
               g.url AS grant_url, g.match_score, g.win_probability
        FROM applications a
        LEFT JOIN grants g ON g.id = a.grant_id
    """
    params = []
    if status:
        query += " WHERE a.status=?"
        params.append(status)
    query += " ORDER BY a.generated_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_application_status(app_id: int, new_status: str, notes: str = "") -> bool:
    """Update an application's status and log the change."""
    conn = get_conn()
    c = conn.cursor()
    row = c.execute("SELECT status, grant_id FROM applications WHERE id=?", (app_id,)).fetchone()
    if not row:
        conn.close()
        return False
    old_status = row["status"]
    grant_id = row["grant_id"]
    now = datetime.utcnow().isoformat()
    c.execute(
        "UPDATE applications SET status=?, status_notes=?, updated_at=? WHERE id=?",
        (new_status, notes, now, app_id)
    )
    c.execute(
        "INSERT INTO status_log (application_id, grant_id, old_status, new_status, notes) VALUES (?,?,?,?,?)",
        (app_id, grant_id, old_status, new_status, notes)
    )
    conn.commit()
    conn.close()
    return True


def get_application_stats() -> dict:
    """Count applications per status."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT status, COUNT(*) as cnt FROM applications GROUP BY status"
    ).fetchall()
    conn.close()
    return {r["status"]: r["cnt"] for r in rows}


def log_scan(source: str, found: int, new: int, error: str = None):
    conn = get_conn()
    conn.execute(
        "INSERT INTO scan_log (source, grants_found, grants_new, error) VALUES (?,?,?,?)",
        (source, found, new, error)
    )
    conn.commit()
    conn.close()
