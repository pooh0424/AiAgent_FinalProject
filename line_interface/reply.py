from dataclasses import dataclass


@dataclass
class AgentReply:
    text: str
    image_url: str | None = None
    quick_reply_actions: list[str] | None = None
