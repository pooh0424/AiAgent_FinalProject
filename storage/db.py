import os
import sqlite3
from datetime import datetime, timezone, timedelta

DB_PATH = os.getenv("DB_PATH", "./data/expenses.db")

TAIPEI_TZ = timezone(timedelta(hours=8))


def db() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id   TEXT PRIMARY KEY,
                joined_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS expenses (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    TEXT    NOT NULL,
                amount     REAL    NOT NULL,
                category   TEXT    NOT NULL,
                item       TEXT    NOT NULL,
                note       TEXT,
                spent_at   TEXT    NOT NULL,
                created_at TEXT    NOT NULL,
                is_deleted INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );
            CREATE INDEX IF NOT EXISTS idx_expenses_user_date ON expenses(user_id, spent_at);
            CREATE INDEX IF NOT EXISTS idx_expenses_user_cat  ON expenses(user_id, category);

            CREATE TABLE IF NOT EXISTS interactions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    TEXT NOT NULL,
                message    TEXT NOT NULL,
                reply      TEXT NOT NULL,
                tool_calls TEXT,
                ts         TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_interactions_user_ts ON interactions(user_id, ts);
            """
        )


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def today_tpe_iso() -> str:
    return datetime.now(TAIPEI_TZ).date().isoformat()


def now_tpe() -> datetime:
    return datetime.now(TAIPEI_TZ)


def ensure_user(user_id: str) -> None:
    with db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users(user_id, joined_at) VALUES (?, ?)",
            (user_id, now_utc_iso()),
        )
