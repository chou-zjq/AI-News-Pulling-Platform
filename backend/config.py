"""
应用配置管理。
从 .env 文件加载敏感配置，提供默认值。
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 项目根目录 = backend/ 的父目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 加载 .env 文件
load_dotenv(PROJECT_ROOT / ".env")

# ── 数据目录 ──────────────────────────────────────────
DATA_DIR = PROJECT_ROOT / "data"
RECORD_LIBRARY_DIR = DATA_DIR / "RecordLibrary"
KEYBOX_SECRET_FILE = DATA_DIR / ".keybox-secret"
DATABASE_PATH = DATA_DIR / "news_index.db"

# ── 新闻源 API ────────────────────────────────────────
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "")
NEWSAPI_BASE_URL = "https://newsapi.org/v2"

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_API_BASE_URL = "https://api.github.com"

# ── 应用设置 ──────────────────────────────────────────
TOP_N = 20                           # 默认返回的新闻条数
MAX_CONCURRENT_REQUESTS = 3          # 并发抓取上限
REQUEST_TIMEOUT = 15                  # 单次请求超时（秒）

# ── LLM 默认配置 ─────────────────────────────────────
DEFAULT_LLM_PROVIDER = os.getenv("DEFAULT_LLM_PROVIDER", "")

# 确保必要目录存在
DATA_DIR.mkdir(parents=True, exist_ok=True)
RECORD_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
