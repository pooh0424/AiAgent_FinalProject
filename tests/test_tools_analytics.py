from tools.analytics import aggregate_expenses
from tools.expenses import add_expense


def test_aggregate_by_category():
    add_expense(user_id="u1", amount=120, category="餐飲", item="麵", spent_at="2026-05-20")
    add_expense(user_id="u1", amount=300, category="餐飲", item="晚餐", spent_at="2026-05-21")
    add_expense(user_id="u1", amount=65, category="飲品", item="珍奶", spent_at="2026-05-20")

    r = aggregate_expenses(
        user_id="u1", start_date="2026-05-01", end_date="2026-05-31", group_by="category"
    )
    assert r["total"] == 485
    by_key = {g["key"]: g["value"] for g in r["groups"]}
    assert by_key["餐飲"] == 420
    assert by_key["飲品"] == 65


def test_aggregate_empty():
    r = aggregate_expenses(user_id="u1", start_date="2026-05-01", end_date="2026-05-31")
    assert r["total"] == 0
    assert r["groups"] == []
