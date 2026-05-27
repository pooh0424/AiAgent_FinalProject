"""Analytics tools: aggregate / detect_anomaly（pandas）。"""
from datetime import date, datetime, timedelta

import pandas as pd

from agent.prompts import CATEGORIES
from storage.repository import fetch_expenses


def _as_df(items: list[dict]) -> pd.DataFrame:
    if not items:
        return pd.DataFrame(columns=["id", "amount", "category", "item", "spent_at"])
    df = pd.DataFrame(items)
    df["spent_at"] = pd.to_datetime(df["spent_at"])
    df["amount"] = df["amount"].astype(float)
    return df


def aggregate_expenses(
    user_id: str,
    start_date: str,
    end_date: str,
    group_by: str = "category",
    metric: str = "sum",
    category: str | None = None,
) -> dict:
    items = fetch_expenses(user_id, start_date, end_date, category=category, limit=10000)
    df = _as_df(items)
    if df.empty:
        return {"metric": metric, "group_by": group_by, "total": 0, "groups": []}

    total = round(float(df["amount"].sum()), 2)

    if group_by == "none":
        agg_val = float(getattr(df["amount"], metric)())
        return {
            "metric": metric,
            "group_by": "none",
            "total": total,
            "groups": [{"key": "all", "value": round(agg_val, 2)}],
        }

    if group_by == "day":
        df["_key"] = df["spent_at"].dt.strftime("%Y-%m-%d")
    elif group_by == "week":
        # ISO week 起始為週一
        df["_key"] = df["spent_at"].dt.to_period("W-MON").apply(lambda p: str(p.start_time.date()))
    else:  # category
        df["_key"] = df["category"]

    grouped = df.groupby("_key")["amount"].agg(metric).sort_values(ascending=False)
    groups = [{"key": str(k), "value": round(float(v), 2)} for k, v in grouped.items()]
    return {"metric": metric, "group_by": group_by, "total": total, "groups": groups}


def _week_range(d: date) -> tuple[date, date]:
    """回傳 d 所在週的週一與週日（ISO 週）。"""
    start = d - timedelta(days=d.weekday())
    return start, start + timedelta(days=6)


def detect_anomaly(user_id: str, kind: str = "weekly_category_spike") -> dict:
    today = datetime.now().date()
    if kind == "weekly_category_spike":
        cur_start, cur_end = _week_range(today)
        cur = fetch_expenses(user_id, cur_start.isoformat(), cur_end.isoformat(), limit=10000)
        df_cur = _as_df(cur)
        if df_cur.empty:
            return {"anomalies": [], "note": "本週尚無紀錄"}

        # 過去 4 週（不含本週）
        past_start = cur_start - timedelta(days=28)
        past_end = cur_start - timedelta(days=1)
        past = fetch_expenses(user_id, past_start.isoformat(), past_end.isoformat(), limit=10000)
        df_past = _as_df(past)

        cur_by_cat = df_cur.groupby("category")["amount"].sum()
        if df_past.empty:
            past_avg_by_cat = pd.Series(dtype=float)
        else:
            # 過去 4 週每週平均
            past_by_cat_total = df_past.groupby("category")["amount"].sum()
            past_avg_by_cat = past_by_cat_total / 4.0

        anomalies = []
        for cat in CATEGORIES:
            cur_v = float(cur_by_cat.get(cat, 0.0))
            avg_v = float(past_avg_by_cat.get(cat, 0.0))
            if cur_v < 100:  # 太小的金額不報警
                continue
            if avg_v <= 0:
                continue
            ratio = cur_v / avg_v
            if ratio > 1.5:
                anomalies.append(
                    {
                        "category": cat,
                        "current_week": round(cur_v, 2),
                        "avg_last_4_weeks": round(avg_v, 2),
                        "ratio": round(ratio, 2),
                        "suggestion_hint": f"本週{cat}支出比過去 4 週平均高 {int((ratio-1)*100)}%",
                    }
                )
        return {"anomalies": anomalies, "window": f"{cur_start} ~ {cur_end}"}

    elif kind == "monthly_total_spike":
        first = today.replace(day=1)
        cur = fetch_expenses(user_id, first.isoformat(), today.isoformat(), limit=10000)
        df_cur = _as_df(cur)
        if df_cur.empty:
            return {"anomalies": [], "note": "本月尚無紀錄"}
        cur_total = float(df_cur["amount"].sum())

        # 過去 3 個月同期天數
        anomalies = []
        # 簡化：只比較總額 vs 過去 3 個月平均（不切同期）
        three_months_ago = (first - timedelta(days=90))
        past_end = first - timedelta(days=1)
        past = fetch_expenses(user_id, three_months_ago.isoformat(), past_end.isoformat(), limit=10000)
        df_past = _as_df(past)
        if df_past.empty:
            return {"anomalies": [], "note": "歷史資料不足"}
        past_avg = float(df_past["amount"].sum()) / 3.0
        if past_avg > 0 and cur_total / past_avg > 1.5:
            anomalies.append(
                {
                    "metric": "monthly_total",
                    "current_month": round(cur_total, 2),
                    "avg_last_3_months": round(past_avg, 2),
                    "ratio": round(cur_total / past_avg, 2),
                    "suggestion_hint": f"本月總支出比過去 3 個月平均高 {int((cur_total/past_avg-1)*100)}%",
                }
            )
        return {"anomalies": anomalies}

    return {"anomalies": [], "error": f"unknown kind: {kind}"}
