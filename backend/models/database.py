"""
SQLite 数据库管理：建表、连接、初始化。
"""

import sqlite3
import json
from pathlib import Path
from typing import Optional

from config import DATABASE_PATH
from models import keybox


SCHEMA_SQL = """
-- 新闻索引表
CREATE TABLE IF NOT EXISTS news_index (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    summary TEXT DEFAULT '',
    url TEXT NOT NULL,
    source TEXT DEFAULT '',
    category TEXT DEFAULT '未分类',
    hotness REAL DEFAULT 0.0,
    date TEXT NOT NULL,
    record_path TEXT DEFAULT '',
    summary_cn TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_news_date ON news_index(date);
CREATE INDEX IF NOT EXISTS idx_news_hotness ON news_index(date, hotness DESC);

-- 抓取日志表
CREATE TABLE IF NOT EXISTS fetch_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT UNIQUE NOT NULL,
    fetch_count INTEGER DEFAULT 0,
    top20_ids TEXT DEFAULT '[]',
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Provider 注册表
CREATE TABLE IF NOT EXISTS provider_registry (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    api_base_url TEXT DEFAULT '',
    models TEXT DEFAULT '[]',
    docs_url TEXT DEFAULT '',
    logo_color TEXT DEFAULT '#666666',
    requires_org_id INTEGER DEFAULT 0
);

-- API Keys 表
CREATE TABLE IF NOT EXISTS api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id TEXT NOT NULL REFERENCES provider_registry(id),
    label TEXT DEFAULT '',
    api_key_encrypted TEXT NOT NULL,
    org_id_encrypted TEXT DEFAULT '',
    is_enabled INTEGER DEFAULT 1,
    priority INTEGER DEFAULT 0,
    usage_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_keys_provider ON api_keys(provider_id, is_enabled);

-- Key 使用日志
CREATE TABLE IF NOT EXISTS key_usage_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key_id INTEGER REFERENCES api_keys(id),
    task TEXT DEFAULT '',
    tokens_used INTEGER DEFAULT 0,
    success INTEGER DEFAULT 1,
    error_message TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


class Database:
    """SQLite 数据库管理器（单例模式）"""

    _instance: Optional["Database"] = None

    def __init__(self, db_path: Path = DATABASE_PATH):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    @classmethod
    def get(cls) -> "Database":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
            )
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def init_db(self):
        """初始化表结构和预置数据"""
        cursor = self.conn.cursor()
        cursor.executescript(SCHEMA_SQL)

        # 插入内置 Provider（幂等）
        for p in keybox.BUILTIN_PROVIDERS:
            cursor.execute(
                """INSERT OR IGNORE INTO provider_registry
                   (id, display_name, api_base_url, models, docs_url, logo_color, requires_org_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    p["id"], p["display_name"], p["api_base_url"],
                    json.dumps(p["models"], ensure_ascii=False),
                    p["docs_url"], p["logo_color"],
                    1 if p.get("requires_org_id") else 0,
                ),
            )

        # 迁移：添加 summary_cn 列（兼容旧数据库）
        cols = [c[1] for c in cursor.execute("PRAGMA table_info(news_index)").fetchall()]
        if "summary_cn" not in cols:
            cursor.execute("ALTER TABLE news_index ADD COLUMN summary_cn TEXT DEFAULT ''")

        self.conn.commit()

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
