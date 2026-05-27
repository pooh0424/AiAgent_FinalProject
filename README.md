# LINE AI 智慧記帳 Agent

讓記帳像聊天一樣簡單——透過 LINE 訊息，使用 Claude API 自動分類、查詢、畫圖、提醒。

## 功能（對應 5 個情境）

| 情境 | 範例輸入 | 行為 |
|---|---|---|
| A 快速記帳 | `中午在校門口吃麵花了 120 元` | Agent 判斷類別「餐飲」並寫入 |
| B 即時查帳 | `這禮拜我喝飲料花了多少？` | 篩選本週「飲品」並回答 |
| C 視覺統整 | `本月總結` | 產生圓餅圖回傳 |
| D 異常提示 | （連續多筆同類別後）`再記晚餐 250` | 主動提醒週支出偏高 |
| E 刪除項目 | `我想刪除前一筆資料` | 兩階段確認後軟刪除 |

## 架構

```
LINE Webhook ──→ FastAPI /callback
                    ↓
              line_interface/handler.py
                    ↓ (user_id, text)
            agent/orchestrator.py
                    ↓
        Anthropic Claude API (tool_use loop)
                    ↓
           agent/tool_registry.py (dispatch)
                    ↓
        tools/expenses.py / analytics.py / charts.py
                    ↓
        storage/repository.py → SQLite
```

關鍵設計：
- `user_id` 由 orchestrator **強制注入**，禁止 LLM 提供（防跨使用者資料外洩）
- 軟刪除（`is_deleted=1`），保留救援空間
- `interactions.tool_calls` 記錄每輪工具呼叫，「刪除前一筆」靠這個回查
- 圖片透過 FastAPI StaticFiles 對外，URL 走 `PUBLIC_BASE_URL`

## 安裝

```bash
cd final_project_agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 編輯 .env，填入 LINE_CHANNEL_ACCESS_TOKEN / LINE_CHANNEL_SECRET / ANTHROPIC_API_KEY
```

## 啟動

```bash
# Terminal 1：啟動 uvicorn
uvicorn app:app --reload --port 8000

# Terminal 2：開 ngrok（每次 URL 會變）
ngrok http 8000
# 把 https://xxxx.ngrok-free.app 寫進 .env 的 PUBLIC_BASE_URL，重啟 uvicorn

# LINE Developers Console：
# Messaging API → Webhook URL = https://xxxx.ngrok-free.app/callback → Verify
```

## 本機快速測試（跳過 LINE）

```bash
# 用 smoke 腳本直接打 orchestrator
python scripts/smoke.py "中午在校門口吃麵花了 120 元"
python scripts/smoke.py "這禮拜我喝飲料花了多少"
python scripts/smoke.py "本月總結"
python scripts/smoke.py "我想刪除前一筆資料"
python scripts/smoke.py "確認"
```

## 跑測試

```bash
pytest -q
```

涵蓋：
- 工具：add/query/delete/aggregate
- 多使用者隔離
- 兩階段確認流程
- mock Claude 驗證 tool_use 迴圈

## 端對端驗證（在 LINE 上輸入）

| # | 輸入 | 期待 |
|---|---|---|
| 1 | `中午在校門口吃麵花了 120 元` | 已記下餐飲・校門口的麵 NT$120 |
| 2 | `下午買了珍奶 65` | 已記下飲品 |
| 3 | `這禮拜我喝飲料花了多少？` | 飲品 NT$65 |
| 4 | `本月總結` | 文字摘要 + 圓餅圖 |
| 5 | `我想刪除前一筆資料` | 「要刪『X』嗎？」+ Quick Reply |
| 6 | `確認` | 已刪除 |

## 注意事項

- **ngrok URL 變動**：每次重啟需更新 `.env` 的 `PUBLIC_BASE_URL` 與 LINE Console 的 Webhook URL
- **matplotlib 中文字型**：macOS 用 PingFang TC，Linux 部署需安裝 `fonts-noto-cjk`
- **LINE `reply_token` 一次性**：文字 + 圖片務必同一個 reply 送出（已實作於 `handler._build_messages`）
- **時區**：消費日期用台北時間（UTC+8）判斷

## 規格

詳見 `../docs/agent_project_srs.html` 與 `/Users/graytsao/.claude/plans/html-head-title-ai-shimmying-boole.md`
