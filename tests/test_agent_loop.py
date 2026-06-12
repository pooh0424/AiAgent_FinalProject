"""Mock Anthropic client，驗證 tool_use 多輪迴圈。"""
from dataclasses import dataclass
from typing import Any

from agent.orchestrator import run_agent
from storage.db import ensure_user


@dataclass
class FakeBlock:
    type: str
    text: str = ""
    id: str = ""
    name: str = ""
    input: dict = None


@dataclass
class FakeResponse:
    content: list
    stop_reason: str


class FakeClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    @property
    def messages(self):
        return self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


def test_tool_use_loop_add_expense():
    ensure_user("u1")
    client = FakeClient(
        [
            # 第 1 輪：Claude 要求呼叫 add_expense
            FakeResponse(
                content=[
                    FakeBlock(
                        type="tool_use",
                        id="tool_1",
                        name="add_expense",
                        input={
                            "amount": 120,
                            "category": "餐飲",
                            "item": "校門口的麵",
                            "spent_at": "2026-05-20",
                        },
                    )
                ],
                stop_reason="tool_use",
            ),
            # 第 2 輪：Claude 看到 tool_result 後回最終文字
            FakeResponse(
                content=[FakeBlock(type="text", text="OK，已記下餐飲・校門口的麵 NT$120")],
                stop_reason="end_turn",
            ),
        ]
    )

    reply = run_agent(client=client, user_id="u1", user_text="中午吃麵 120")

    assert "已記下" in reply.text
    assert reply.image_url is None
    assert reply.quick_reply_actions is None

    # Claude 被呼叫兩次
    assert len(client.calls) == 2

    # 第二次呼叫時 messages 多了 assistant 的 tool_use 與 user 的 tool_result
    second_messages = client.calls[1]["messages"]
    assert any(
        isinstance(m["content"], list) and any(b.get("type") == "tool_use" for b in m["content"])
        for m in second_messages
    )
    assert any(
        isinstance(m["content"], list)
        and any(b.get("type") == "tool_result" for b in m["content"])
        for m in second_messages
    )


def test_delete_two_step_triggers_quick_reply():
    ensure_user("u1")
    # 先有一筆紀錄
    from tools.expenses import add_expense

    r = add_expense(
        user_id="u1", amount=250, category="餐飲", item="晚餐", spent_at="2026-05-20"
    )
    eid = r["expense_id"]

    # 模擬 Claude 用 reference="last" 但 confirmed=False
    client = FakeClient(
        [
            FakeResponse(
                content=[
                    FakeBlock(
                        type="tool_use",
                        id="tool_1",
                        name="delete_expense",
                        input={"reference": "last", "confirmed": False},
                    )
                ],
                stop_reason="tool_use",
            ),
            FakeResponse(
                content=[
                    FakeBlock(type="text", text="你要刪的是『晚餐 NT$250』嗎？回覆確認我就刪掉")
                ],
                stop_reason="end_turn",
            ),
        ]
    )

    # 注入一筆 interaction 以便 find_last_added_expense_id 找得到
    from storage.db import db, now_utc_iso
    import json as _json

    with db() as conn:
        conn.execute(
            "INSERT INTO interactions(user_id, message, reply, tool_calls, ts) VALUES (?, ?, ?, ?, ?)",
            (
                "u1",
                "晚餐 250",
                "ok",
                _json.dumps(
                    [{"name": "add_expense", "input": {}, "result": {"ok": True, "expense_id": eid}}]
                ),
                now_utc_iso(),
            ),
        )

    reply = run_agent(client=client, user_id="u1", user_text="刪除前一筆")

    assert reply.quick_reply_actions == ["確認刪除", "取消"]
    assert "晚餐" in reply.text or "確認" in reply.text
