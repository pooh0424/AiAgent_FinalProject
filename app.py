import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from linebot.v3.exceptions import InvalidSignatureError

load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("app")

REQUIRED = ("LINE_CHANNEL_ACCESS_TOKEN", "LINE_CHANNEL_SECRET", "ANTHROPIC_API_KEY")
missing = [k for k in REQUIRED if not os.getenv(k)]
if missing:
    raise RuntimeError(f"缺少必要環境變數：{', '.join(missing)}，請檢查 .env")

# 必須在 import handler 之前載入環境變數，handler 內部會讀
from line_interface.handler import handler  # noqa: E402
from storage.db import init_db  # noqa: E402

init_db()

app = FastAPI(title="LINE Expense Agent")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def root():
    return {"status": "ok", "service": "line-expense-agent"}


@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body = (await request.body()).decode("utf-8")
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception:
        log.exception("webhook 例外，但仍回 200 避免 LINE 重試")
    return "OK"
