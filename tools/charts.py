"""Chart tool: generate pie chart PNG and return public URL."""
import hashlib
import os
import platform
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # 必須在 import pyplot 前
import matplotlib.pyplot as plt
from matplotlib import font_manager

CHARTS_DIR = Path("static/charts")

_FONT_INIT_DONE = False


def _init_chinese_font() -> None:
    """設定中文字型，避免方塊。"""
    global _FONT_INIT_DONE
    if _FONT_INIT_DONE:
        return
    candidates = (
        ["PingFang TC", "Heiti TC", "Apple LiGothic", "Arial Unicode MS"]
        if platform.system() == "Darwin"
        else ["Noto Sans CJK TC", "Noto Sans CJK SC", "WenQuanYi Zen Hei", "DejaVu Sans"]
    )
    installed = {f.name for f in font_manager.fontManager.ttflist}
    for name in candidates:
        if name in installed:
            plt.rcParams["font.sans-serif"] = [name]
            break
    plt.rcParams["axes.unicode_minus"] = False
    _FONT_INIT_DONE = True


def generate_pie_chart(user_id: str, title: str, groups: list[dict]) -> dict:
    if not groups:
        return {"ok": False, "error": "沒有資料可以畫圖"}
    _init_chinese_font()

    labels = [str(g["key"]) for g in groups]
    sizes = [float(g["value"]) for g in groups]
    if sum(sizes) <= 0:
        return {"ok": False, "error": "所有金額為 0，無法畫圖"}

    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    base_url = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
    if not base_url:
        return {"ok": False, "error": "未設定 PUBLIC_BASE_URL，無法產生公開圖片 URL"}

    user_hash = hashlib.sha1(user_id.encode("utf-8")).hexdigest()[:8]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"{user_hash}_{ts}.png"
    filepath = CHARTS_DIR / filename

    fig, ax = plt.subplots(figsize=(6, 6), dpi=130)
    wedges, _texts, autotexts = ax.pie(
        sizes,
        labels=labels,
        autopct=lambda pct: f"{pct:.1f}%" if pct >= 3 else "",
        startangle=90,
        textprops={"fontsize": 11},
    )
    for at in autotexts:
        at.set_color("white")
        at.set_fontsize(10)
    ax.set_title(title, fontsize=14, pad=12)
    ax.axis("equal")
    fig.tight_layout()
    fig.savefig(filepath, bbox_inches="tight")
    plt.close(fig)

    url = f"{base_url}/static/charts/{filename}"
    return {"ok": True, "image_url": url, "preview_url": url}


def cleanup_old_charts(days: int = 1) -> int:
    """刪除超過 N 天的圖片，回傳刪除數量。"""
    if not CHARTS_DIR.exists():
        return 0
    cutoff = datetime.now().timestamp() - days * 86400
    n = 0
    for p in CHARTS_DIR.glob("*.png"):
        try:
            if p.stat().st_mtime < cutoff:
                p.unlink()
                n += 1
        except OSError:
            pass
    return n
