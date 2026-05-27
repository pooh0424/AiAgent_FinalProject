"""Expense tools: add / query / delete."""
from agent.prompts import CATEGORIES
from storage.repository import (
    fetch_expenses,
    find_last_added_expense_id,
    insert_expense,
    soft_delete_expense,
)


def add_expense(
    user_id: str,
    amount: float,
    category: str,
    item: str,
    note: str | None = None,
    spent_at: str | None = None,
) -> dict:
    if amount is None or float(amount) <= 0:
        return {"ok": False, "error": "金額必須大於 0"}
    if category not in CATEGORIES:
        category = "其他"
    eid = insert_expense(user_id, float(amount), category, item, note, spent_at)
    summary = f"已記錄：{category}・{item} NT${float(amount):g}"
    if spent_at:
        summary += f"（{spent_at}）"
    return {"ok": True, "expense_id": eid, "summary": summary}


def query_expenses(
    user_id: str,
    start_date: str,
    end_date: str,
    category: str | None = None,
    keyword: str | None = None,
    limit: int = 50,
) -> dict:
    items = fetch_expenses(user_id, start_date, end_date, category, keyword, limit)
    total = round(sum(i["amount"] for i in items), 2)
    return {"count": len(items), "total": total, "items": items}


def delete_expense(
    user_id: str,
    expense_id: int | None = None,
    reference: str | None = None,
    confirmed: bool = False,
) -> dict:
    # 解析目標 expense_id
    target_id: int | None = None
    if expense_id:
        target_id = int(expense_id)
    elif reference == "last":
        target_id = find_last_added_expense_id(user_id)
        if target_id is None:
            return {"ok": False, "error": "找不到最近新增的紀錄"}
    else:
        return {"ok": False, "error": "請提供 expense_id 或 reference='last'"}

    # 先取出 preview
    from storage.db import db

    with db() as conn:
        row = conn.execute(
            "SELECT id, amount, category, item, spent_at FROM expenses WHERE id = ? AND user_id = ? AND is_deleted = 0",
            (target_id, user_id),
        ).fetchone()
    if not row:
        return {"ok": False, "error": f"找不到 id={target_id} 的紀錄（可能已刪除）"}
    preview = dict(row)

    if not confirmed:
        return {"ok": False, "preview": preview, "reason": "preview_only"}

    deleted = soft_delete_expense(user_id, target_id)
    if not deleted:
        return {"ok": False, "error": "刪除失敗"}
    return {"ok": True, "deleted": deleted}
