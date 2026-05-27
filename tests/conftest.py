"""共用 fixture：每個測試用獨立的暫存 SQLite。"""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    # storage.db 是 module 載入時讀 DB_PATH，要 reload 才會生效
    import importlib

    import storage.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()
    # 預建測試常用 user，避免每個測試重複呼叫
    for uid in ("u1", "u2", "u_smoke"):
        db_mod.ensure_user(uid)
    yield db_path
