import logging
import os

from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    ImageMessage,
    MessagingApi,
    QuickReply,
    QuickReplyItem,
    MessageAction,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

from agent.orchestrator import run_agent
from line_interface.reply import AgentReply
from storage.db import ensure_user

log = logging.getLogger("handler")

CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)


def _build_messages(reply: AgentReply) -> list:
    msgs: list = []
    text = (reply.text or "").strip()[:4900]
    if text:
        if reply.quick_reply_actions:
            qr = QuickReply(
                items=[
                    QuickReplyItem(action=MessageAction(label=a[:20], text=a))
                    for a in reply.quick_reply_actions[:13]
                ]
            )
            msgs.append(TextMessage(text=text, quick_reply=qr))
        else:
            msgs.append(TextMessage(text=text))
    if reply.image_url:
        msgs.append(
            ImageMessage(
                original_content_url=reply.image_url,
                preview_image_url=reply.image_url,
            )
        )
    if not msgs:
        msgs.append(TextMessage(text="（沒有回應內容）"))
    return msgs[:5]


@handler.add(MessageEvent, message=TextMessageContent)
def handle_text(event):
    user_id = (
        event.source.user_id
        if event.source and getattr(event.source, "user_id", None)
        else "unknown"
    )
    text = (event.message.text or "").strip()

    ensure_user(user_id)

    try:
        reply = run_agent(user_id=user_id, user_text=text)
    except Exception as e:
        log.exception("agent run error")
        reply = AgentReply(text=f"系統錯誤，請稍後再試：{e}")

    messages = _build_messages(reply)

    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=messages,
            )
        )
