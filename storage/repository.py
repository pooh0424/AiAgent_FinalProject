"""高階查詢函式：給 tools 用，不直接被 LLM 呼叫。"""
import json
from typing import Any

from storage.db import db, now_utc_iso, today_tpe_iso


def insert_expense(
    user_id: str,
    amount: float,
    category: str,
    item: str,
    note: str | None,
    spent_at: str | None,
) -> int:
    spent_at = spent_at or today_tpe_iso()
    with db() as conn:
        cur = conn.execute(
            """INSERT INTO expenses(user_id, amount, category, item, note, spent_at, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, float(amount), category, item, note, spent_at, now_utc_iso()),
        )
        return int(cur.lastrowid)


def fetch_expenses(
    user_id: str,
    start_date: str,
    end_date: str,
    category: str | None = None,
    keyword: str | None = None,
    limit: int = 50,
) -> list[dict]:
    sql = """SELECT id, amount, category, item, note, spent_at
             FROM expenses
             WHERE user_id = ? AND is_deleted = 0
               AND spent_at >= ? AND spent_at <= ?"""
    args: list[Any] = [user_id, start_date, end_date]
    if category:
        sql += " AND category = ?"
        args.append(category)
    if keyword:
        sql += " AND (item LIKE ? OR IFNULL(note,'') LIKE ?)"
        like = f"%{keyword}%"
        args += [like, like]
    sql += " ORDER BY spent_at DESC, id DESC LIMIT ?"
    args.append(int(limit))
    with db() as conn:
        rows = conn.execute(sql, args).fetchall()
    return [dict(r) for r in rows]


def soft_delete_expense(user_id: str, expense_id: int) -> dict | None:
    with db() as conn:
        row = conn.execute(
            "SELECT id, amount, category, item, spent_at FROM expenses WHERE id = ? AND user_id = ? AND is_deleted = 0",
            (expense_id, user_id),
        ).fetchone()
        if not row:
            return None
        conn.execute(
            "UPDATE expenses SET is_deleted = 1 WHERE id = ? AND user_id = ?",
            (expense_id, user_id),
        )
    return dict(row)


def find_last_added_expense_id(user_id: str) -> int | None:
    """從 interactions.tool_calls 回查最近一筆 add_expense 的 expense_id。"""
    with db() as conn:
        rows = conn.execute(
            "SELECT tool_calls FROM interactions WHERE user_id = ? AND tool_calls IS NOT NULL ORDER BY id DESC LIMIT 20",
            (user_id,),
        ).fetchall()
    for row in rows:
        try:
            calls = json.loads(row["tool_calls"] or "[]")
        except json.JSONDecodeError:
            continue
        for call in reversed(calls):
            if call.get("name") == "add_expense":
                result = call.get("result") or {}
                if result.get("ok") and result.get("expense_id"):
                    # 確認此 expense 還沒被軟刪除
                    eid = int(result["expense_id"])
                    with db() as conn:
                        alive = conn.execute(
                            "SELECT 1 FROM expenses WHERE id = ? AND user_id = ? AND is_deleted = 0",
                            (eid, user_id),
                        ).fetchone()
                    if alive:
                        return eid
    return None
