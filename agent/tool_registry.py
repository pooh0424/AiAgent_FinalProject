"""Tool definitions (Anthropic schema) + name → impl dispatch."""
from typing import Any, Callable

from agent.prompts import CATEGORIES
from tools import analytics, charts, expenses

TOOL_DEFS: list[dict] = [
    {
        "name": "add_expense",
        "description": "記錄一筆新的消費。當使用者描述自己花了多少錢買什麼東西時呼叫。若使用者沒明確說日期就不要填 spent_at，工具會預設為今天。",
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {"type": "number", "description": "新台幣金額，正數"},
                "category": {
                    "type": "string",
                    "enum": CATEGORIES,
                    "description": "支出類別，從清單中挑最貼切的一個",
                },
                "item": {"type": "string", "description": "簡短品項描述，例如「校門口的麵」"},
                "note": {"type": "string", "description": "選填備註"},
                "spent_at": {"type": "string", "description": "消費日期 YYYY-MM-DD，未提供則為今天"},
            },
            "required": ["amount", "category", "item"],
        },
    },
    {
        "name": "query_expenses",
        "description": "查詢符合條件的消費紀錄明細。用在使用者問『這禮拜我喝飲料花了多少』『上個月買了哪些書』等。",
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "description": "起始日 YYYY-MM-DD（含）"},
                "end_date": {"type": "string", "description": "結束日 YYYY-MM-DD（含）"},
                "category": {"type": "string", "description": "可選，只看單一類別"},
                "keyword": {"type": "string", "description": "可選，item/note 模糊比對"},
                "limit": {"type": "integer", "description": "預設 50"},
            },
            "required": ["start_date", "end_date"],
        },
    },
    {
        "name": "aggregate_expenses",
        "description": "對消費資料做加總、平均、依類別/日/週分組統計，是查帳與圖表的資料來源。",
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string"},
                "end_date": {"type": "string"},
                "group_by": {
                    "type": "string",
                    "enum": ["category", "day", "week", "none"],
                    "description": "預設 category",
                },
                "metric": {
                    "type": "string",
                    "enum": ["sum", "avg", "count", "max"],
                    "description": "預設 sum",
                },
                "category": {"type": "string", "description": "可選，只算單一類別"},
            },
            "required": ["start_date", "end_date"],
        },
    },
    {
        "name": "generate_pie_chart",
        "description": "把分組資料畫成圓餅圖並回傳一個公開的圖片 URL，可以直接在 LINE 顯示。",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "圖片標題，例如「2026 年 5 月支出分布」"},
                "groups": {
                    "type": "array",
                    "description": "從 aggregate_expenses 取得的 groups 陣列",
                    "items": {
                        "type": "object",
                        "properties": {
                            "key": {"type": "string"},
                            "value": {"type": "number"},
                        },
                        "required": ["key", "value"],
                    },
                },
            },
            "required": ["title", "groups"],
        },
    },
    {
        "name": "delete_expense",
        "description": "刪除消費紀錄。若使用者說『前一筆』『剛剛那筆』『最後一筆』，傳 reference='last'。若使用者明確指 id，傳 expense_id。第一次呼叫時 confirmed 留 false，工具會回傳要刪的內容讓你跟使用者確認；等使用者明確同意後，再呼叫一次並設 confirmed=true。",
        "input_schema": {
            "type": "object",
            "properties": {
                "expense_id": {"type": "integer"},
                "reference": {"type": "string", "enum": ["last"]},
                "confirmed": {"type": "boolean", "description": "使用者已明確同意刪除才設為 true"},
            },
        },
    },
    {
        "name": "detect_anomaly",
        "description": "檢查使用者最近的消費是否有異常（例如本週某類別超過過去 4 週平均的 1.5 倍）。",
        "input_schema": {
            "type": "object",
            "properties": {
                "kind": {
                    "type": "string",
                    "enum": ["weekly_category_spike", "monthly_total_spike"],
                    "description": "預設 weekly_category_spike",
                },
            },
        },
    },
]


TOOL_IMPLS: dict[str, Callable[..., dict]] = {
    "add_expense": expenses.add_expense,
    "query_expenses": expenses.query_expenses,
    "delete_expense": expenses.delete_expense,
    "aggregate_expenses": analytics.aggregate_expenses,
    "detect_anomaly": analytics.detect_anomaly,
    "generate_pie_chart": charts.generate_pie_chart,
}


def dispatch(name: str, user_id: str, args: dict[str, Any]) -> dict:
    impl = TOOL_IMPLS.get(name)
    if impl is None:
        return {"ok": False, "error": f"unknown tool: {name}"}
    safe_args = {k: v for k, v in (args or {}).items() if k != "user_id"}
    try:
        return impl(user_id=user_id, **safe_args)
    except TypeError as e:
        return {"ok": False, "error": f"參數錯誤：{e}"}
    except Exception as e:
        return {"ok": False, "error": f"工具執行失敗：{e}"}
