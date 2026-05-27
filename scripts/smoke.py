"""跳過 LINE 直接呼叫 orchestrator，方便手動測試 5 個情境。

用法：
    python scripts/smoke.py "我吃了校門口的麵 120 元"
    python scripts/smoke.py "這禮拜飲料花了多少"
    python scripts/smoke.py --user u_test "本月總結"
"""
import argparse
import sys
from pathlib import Path

# 讓 script 從 repo 根目錄跑都能 import
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv()

from agent.orchestrator import run_agent  # noqa: E402
from storage.db import ensure_user, init_db  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("text", help="要傳給 agent 的文字")
    p.add_argument("--user", default="u_smoke", help="user_id（預設 u_smoke）")
    args = p.parse_args()

    init_db()
    ensure_user(args.user)

    reply = run_agent(user_id=args.user, user_text=args.text)
    print(f"[text]  {reply.text}")
    if reply.image_url:
        print(f"[image] {reply.image_url}")
    if reply.quick_reply_actions:
        print(f"[qr]    {reply.quick_reply_actions}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
