"""
统一新闻条目数据模型。
所有新闻源的数据经过 normalize() 后统一为此格式。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import hashlib


@dataclass
class NewsItem:
    """统一的新闻条目"""
    title: str
    url: str
    summary: str = ""
    summary_cn: str = ""       # AI 生成的中文摘要
    source: str = ""           # "NewsAPI" | "GitHub" | "RSS"
    category: str = "未分类"    # "新功能发布" | "新平台上线" | "好用工具" | "GitHub项目"
    hotness: float = 0.0
    date: str = ""             # "2026-06-08"
    fetched_at: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def id(self) -> str:
        """基于 title + url 生成唯一 ID，用于去重"""
        raw = f"{self.title}|{self.url}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:12]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "summary": self.summary,
            "summary_cn": self.summary_cn,
            "url": self.url,
            "source": self.source,
            "category": self.category,
            "hotness": round(self.hotness, 1),
            "date": self.date,
            "fetched_at": self.fetched_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NewsItem":
        return cls(
            title=data.get("title", ""),
            url=data.get("url", ""),
            summary=data.get("summary", ""),
            summary_cn=data.get("summary_cn", ""),
            source=data.get("source", ""),
            category=data.get("category", "未分类"),
            hotness=data.get("hotness", 0.0),
            date=data.get("date", ""),
            fetched_at=data.get("fetched_at", datetime.now().isoformat()),
        )
