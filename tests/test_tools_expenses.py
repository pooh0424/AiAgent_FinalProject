from tools.expenses import add_expense, delete_expense, query_expenses


def test_add_then_query():
    r = add_expense(
        user_id="u1",
        amount=120,
        category="餐飲",
        item="校門口的麵",
        spent_at="2026-05-20",
    )
    assert r["ok"] is True
    assert r["expense_id"] > 0

    q = query_expenses(user_id="u1", start_date="2026-05-01", end_date="2026-05-31")
    assert q["count"] == 1
    assert q["total"] == 120
    assert q["items"][0]["item"] == "校門口的麵"


def test_query_filters_by_category():
    add_expense(user_id="u1", amount=120, category="餐飲", item="麵", spent_at="2026-05-20")
    add_expense(user_id="u1", amount=65, category="飲品", item="珍奶", spent_at="2026-05-20")

    q = query_expenses(
        user_id="u1", start_date="2026-05-01", end_date="2026-05-31", category="飲品"
    )
    assert q["count"] == 1
    assert q["items"][0]["category"] == "飲品"


def test_query_isolates_user():
    add_expense(user_id="u1", amount=120, category="餐飲", item="麵", spent_at="2026-05-20")
    q = query_expenses(user_id="u2", start_date="2026-05-01", end_date="2026-05-31")
    assert q["count"] == 0


def test_delete_requires_confirmation():
    add_expense(user_id="u1", amount=120, category="餐飲", item="麵", spent_at="2026-05-20")
    eid = query_expenses(
        user_id="u1", start_date="2026-05-01", end_date="2026-05-31"
    )["items"][0]["id"]

    # 未確認 → preview only
    r1 = delete_expense(user_id="u1", expense_id=eid, confirmed=False)
    assert r1["ok"] is False
    assert r1["reason"] == "preview_only"
    assert r1["preview"]["item"] == "麵"

    # 沒被真的刪掉
    assert query_expenses(user_id="u1", start_date="2026-05-01", end_date="2026-05-31")["count"] == 1

    # 確認 → 軟刪除
    r2 = delete_expense(user_id="u1", expense_id=eid, confirmed=True)
    assert r2["ok"] is True
    assert r2["deleted"]["id"] == eid

    assert query_expenses(user_id="u1", start_date="2026-05-01", end_date="2026-05-31")["count"] == 0


def test_invalid_amount():
    r = add_expense(user_id="u1", amount=0, category="餐飲", item="x")
    assert r["ok"] is False


def test_unknown_category_falls_back_to_other():
    r = add_expense(user_id="u1", amount=10, category="奇怪", item="x", spent_at="2026-05-20")
    assert r["ok"] is True
    q = query_expenses(user_id="u1", start_date="2026-05-01", end_date="2026-05-31")
    assert q["items"][0]["category"] == "其他"
