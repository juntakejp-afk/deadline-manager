import sqlite3
import os
from datetime import datetime, date
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), "deadline.db")


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS cases (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                case_number      TEXT NOT NULL,
                title            TEXT NOT NULL,
                ip_type          TEXT NOT NULL CHECK(ip_type IN ('patent','trademark','design')),
                client           TEXT NOT NULL,
                filing_date      DATE NOT NULL,
                priority_date    DATE,
                registration_date DATE,
                status           TEXT NOT NULL DEFAULT 'active'
                                 CHECK(status IN ('active','completed','abandoned')),
                notes            TEXT,
                created_at       DATETIME DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS deadlines (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id       INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
                deadline_type TEXT NOT NULL,
                due_date      DATE NOT NULL,
                alert_90      DATE,
                alert_60      DATE,
                alert_30      DATE,
                is_done       BOOLEAN NOT NULL DEFAULT 0,
                notes         TEXT
            );
        """)


# ── Cases ──────────────────────────────────────────────────────────────────

def insert_case(case_number, title, ip_type, client, filing_date,
                priority_date=None, registration_date=None,
                status="active", notes=None):
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO cases
               (case_number, title, ip_type, client, filing_date,
                priority_date, registration_date, status, notes)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (case_number, title, ip_type, client, filing_date,
             priority_date, registration_date, status, notes),
        )
        return cur.lastrowid


def update_case(case_id, **fields):
    allowed = {"case_number", "title", "ip_type", "client", "filing_date",
                "priority_date", "registration_date", "status", "notes"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    cols = ", ".join(f"{k}=?" for k in updates)
    vals = list(updates.values()) + [case_id]
    with get_conn() as conn:
        conn.execute(f"UPDATE cases SET {cols} WHERE id=?", vals)


def delete_case(case_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM cases WHERE id=?", (case_id,))


def get_case(case_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
        return dict(row) if row else None


def list_cases(ip_type=None, status=None, client=None, search=None):
    sql = "SELECT * FROM cases WHERE 1=1"
    params = []
    if ip_type:
        sql += " AND ip_type=?"
        params.append(ip_type)
    if status:
        sql += " AND status=?"
        params.append(status)
    if client:
        sql += " AND client=?"
        params.append(client)
    if search:
        sql += " AND (case_number LIKE ? OR title LIKE ?)"
        params += [f"%{search}%", f"%{search}%"]
    sql += " ORDER BY filing_date DESC"
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


# ── Deadlines ───────────────────────────────────────────────────────────────

def insert_deadline(case_id, deadline_type, due_date, notes=None):
    from logic import compute_alerts
    alert_90, alert_60, alert_30 = compute_alerts(due_date)
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO deadlines
               (case_id, deadline_type, due_date, alert_90, alert_60, alert_30, notes)
               VALUES (?,?,?,?,?,?,?)""",
            (case_id, deadline_type, due_date, alert_90, alert_60, alert_30, notes),
        )
        return cur.lastrowid


def bulk_insert_deadlines(rows):
    """rows: list of (case_id, deadline_type, due_date, notes)"""
    from logic import compute_alerts
    prepared = []
    for case_id, deadline_type, due_date, notes in rows:
        a90, a60, a30 = compute_alerts(due_date)
        prepared.append((case_id, deadline_type, due_date, a90, a60, a30, notes))
    with get_conn() as conn:
        conn.executemany(
            """INSERT INTO deadlines
               (case_id, deadline_type, due_date, alert_90, alert_60, alert_30, notes)
               VALUES (?,?,?,?,?,?,?)""",
            prepared,
        )


def update_deadline_done(deadline_id, is_done):
    with get_conn() as conn:
        conn.execute("UPDATE deadlines SET is_done=? WHERE id=?", (int(is_done), deadline_id))


def delete_deadline(deadline_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM deadlines WHERE id=?", (deadline_id,))


def list_deadlines_for_case(case_id):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM deadlines WHERE case_id=? ORDER BY due_date",
            (case_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def list_upcoming_deadlines(days=None, overdue=False):
    """
    Returns deadlines joined with case info, optionally filtered by urgency.
    For patents, only the nearest annual fee per case is returned.
    """
    today = date.today().isoformat()
    sql = """
        SELECT d.*, c.case_number, c.title, c.ip_type, c.client, c.status as case_status
        FROM deadlines d
        JOIN cases c ON c.id = d.case_id
        WHERE d.is_done = 0
          AND c.status = 'active'
    """
    params = []
    if overdue:
        sql += " AND d.due_date < ?"
        params.append(today)
    elif days is not None:
        sql += " AND d.due_date >= ? AND d.due_date <= date(?, '+' || ? || ' days')"
        params += [today, today, days]
    sql += " ORDER BY d.due_date"
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def get_status_summary():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM cases GROUP BY status"
        ).fetchall()
        return {r["status"]: r["cnt"] for r in rows}
