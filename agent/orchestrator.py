"""Agent orchestrator: 呼叫 Claude，處理 tool_use 多輪迴圈，回傳 AgentReply。"""
import json
import logging
import os
from typing import Any

from anthropic import Anthropic

from agent.prompts import build_system_prompt
from agent.tool_registry import TOOL_DEFS, dispatch
from line_interface.reply import AgentReply
from storage.db import db, now_utc_iso

log = logging.getLogger("orchestrator")

CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5")
MAX_ITER = int(os.getenv("AGENT_MAX_ITERATIONS", "5"))
MAX_TOKENS = int(os.getenv("AGENT_MAX_TOKENS", "4096"))
HISTORY_WINDOW = int(os.getenv("HISTORY_WINDOW", "6"))

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic()
    return _client


def _load_history(user_id: str, limit: int) -> list[dict]:
    if limit <= 0:
        return []
    with db() as conn:
        rows = conn.execute(
            "SELECT message, reply FROM interactions WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    messages: list[dict] = []
    for row in reversed(rows):
        messages.append({"role": "user", "content": row["message"]})
        messages.append({"role": "assistant", "content": row["reply"]})
    return messages


def _save_interaction(
    user_id: str, message: str, reply: str, tool_calls: list[dict]
) -> None:
    with db() as conn:
        conn.execute(
            "INSERT INTO interactions(user_id, message, reply, tool_calls, ts) VALUES (?, ?, ?, ?, ?)",
            (
                user_id,
                message,
                reply,
                json.dumps(tool_calls, ensure_ascii=False),
                now_utc_iso(),
            ),
        )


def _extract_text(content_blocks: list[Any]) -> str:
    parts = []
    for block in content_blocks:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "\n".join(parts).strip()


def _block_to_dict(block: Any) -> dict:
    """把 SDK 物件序列化成 messages.append 用的 dict。"""
    btype = getattr(block, "type", None)
    if btype == "text":
        return {"type": "text", "text": block.text}
    if btype == "tool_use":
        return {
            "type": "tool_use",
            "id": block.id,
            "name": block.name,
            "input": block.input,
        }
    if btype == "thinking":
        return {"type": "thinking", "thinking": getattr(block, "thinking", "")}
    return {}


def run_agent(client: Anthropic | None = None, *, user_id: str, user_text: str) -> AgentReply:
    """Agent 主迴圈：tool_use → dispatch → tool_result → 直到 end_turn。

    client 參數可選，方便測試注入 mock。
    """
    if not user_text:
        return AgentReply(text="嗨，跟我說你今天花了多少錢吧～例如「午餐 120 元」")

    client = client or _get_client()
    system_prompt = build_system_prompt()
    history = _load_history(user_id, HISTORY_WINDOW)
    messages: list[dict] = history + [{"role": "user", "content": user_text}]

    tool_call_log: list[dict] = []
    final_text = ""
    image_url: str | None = None
    quick_reply: list[str] | None = None

    for _ in range(MAX_ITER):
        try:
            resp = client.messages.create(
                model=CLAUDE_MODEL,
                system=system_prompt,
                tools=TOOL_DEFS,
                messages=messages,
                max_tokens=MAX_TOKENS,
            )
        except Exception as e:
            log.exception("Claude API 呼叫失敗")
            return AgentReply(text=f"AI 服務暫時無法使用：{e}")

        stop_reason = resp.stop_reason
        log.info("claude stop_reason=%s", stop_reason)

        if stop_reason == "tool_use":
            assistant_content = [_block_to_dict(b) for b in resp.content if _block_to_dict(b)]
            messages.append({"role": "assistant", "content": assistant_content})

            tool_results: list[dict] = []
            for block in resp.content:
                if getattr(block, "type", None) != "tool_use":
                    continue
                result = dispatch(block.name, user_id, dict(block.input or {}))
                tool_call_log.append(
                    {"name": block.name, "input": dict(block.input or {}), "result": result}
                )
                # 觀察特殊回傳：圖片 / 刪除預覽
                if block.name == "generate_pie_chart" and result.get("ok"):
                    image_url = result.get("image_url") or image_url
                if block.name == "delete_expense" and result.get("reason") == "preview_only":
                    quick_reply = ["確認刪除", "取消"]

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )
            messages.append({"role": "user", "content": tool_results})
            continue

        # end_turn / max_tokens / stop_sequence / pause_turn 都當作結束
        final_text = _extract_text(resp.content)
        break
    else:
        final_text = final_text or "（已達最大迭代次數）"

    if not final_text and image_url:
        final_text = "圖表已產生 👇"
    if not final_text:
        final_text = "（沒有回應）"

    _save_interaction(user_id, user_text, final_text, tool_call_log)
    return AgentReply(text=final_text, image_url=image_url, quick_reply_actions=quick_reply)
