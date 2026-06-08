"""
新闻抓取服务：NewsAPI + GitHub API。
异步并发抓取，统一标准化为 NewsItem 格式。
"""

import asyncio
import math
from datetime import datetime, timezone
from typing import List

import httpx

from config import (
    NEWSAPI_KEY,
    NEWSAPI_BASE_URL,
    GITHUB_TOKEN,
    GITHUB_API_BASE_URL,
    REQUEST_TIMEOUT,
    MAX_CONCURRENT_REQUESTS,
)
from models.news import NewsItem


# ── AI 主题搜索关键词 ─────────────────────────────────
SEARCH_QUERIES = [
    "artificial intelligence new release",
    "AI platform launch",
    "AI tools productivity",
    "machine learning breakthrough",
]


class NewsFetcher:
    """新闻抓取器：封装多源 API 调用和数据标准化"""

    def __init__(self):
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    # ── 公开入口 ──────────────────────────────────────

    async def fetch_all(self) -> List[NewsItem]:
        """
        并发抓取所有新闻源，返回标准化 NewsItem 列表。
        各源内部独立归一化，保证跨源可比较。
        """
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            tasks = []
            if NEWSAPI_KEY:
                tasks.append(self._fetch_newsapi(client, today))
            if GITHUB_TOKEN:
                tasks.append(self._fetch_github(client))

            if not tasks:
                raise ValueError("未配置任何新闻源 API Key。请在 .env 中设置 NEWSAPI_KEY 或 GITHUB_TOKEN")

            results = await asyncio.gather(*tasks, return_exceptions=True)

        all_news: List[NewsItem] = []
        for result in results:
            if isinstance(result, Exception):
                print(f"[Fetcher] source failed: {result}")
                continue
            all_news.extend(result)

        # 跨源归一化：各源内部重新映射到 0-100
        all_news = self._normalize_across_sources(all_news)

        # 跨源去重（基于 URL 相似度）
        all_news = self._deduplicate(all_news)

        return all_news

    def _normalize_across_sources(self, news_list: List[NewsItem]) -> List[NewsItem]:
        """各源内部独立 min-max 归一化，保证两源结果可比较"""
        from collections import defaultdict
        groups: dict[str, list[NewsItem]] = defaultdict(list)
        for n in news_list:
            groups[n.source].append(n)

        result = []
        for source, items in groups.items():
            if len(items) <= 1:
                for n in items:
                    n.hotness = 70.0
                result.extend(items)
                continue

            scores = [n.hotness for n in items]
            min_s, max_s = min(scores), max(scores)
            span = max_s - min_s if max_s > min_s else 1

            for n in items:
                # 归一化到 [40, 98] 区间，给两个源的交集留空间
                normalized = 40 + ((n.hotness - min_s) / span) * 58
                n.hotness = round(normalized, 1)
                result.append(n)

        return result

    def _deduplicate(self, news_list: List[NewsItem]) -> List[NewsItem]:
        """基于 URL 去重（保留热度高的）"""
        seen: dict[str, NewsItem] = {}
        for n in news_list:
            url_key = n.url.rstrip("/").lower()
            if url_key in seen:
                if n.hotness > seen[url_key].hotness:
                    seen[url_key] = n
            else:
                seen[url_key] = n
        return list(seen.values())

    # ── NewsAPI ───────────────────────────────────────

    async def _fetch_newsapi(self, client: httpx.AsyncClient, date: str) -> List[NewsItem]:
        """从 NewsAPI 抓取 AI 相关新闻"""
        all_articles = []
        for query in SEARCH_QUERIES:
            async with self._semaphore:
                try:
                    response = await client.get(
                        f"{NEWSAPI_BASE_URL}/everything",
                        params={
                            "q": query,
                            "sortBy": "popularity",
                            "language": "en",
                            "pageSize": 25,
                            "apiKey": NEWSAPI_KEY,
                        },
                    )
                    response.raise_for_status()
                    data = response.json()
                    if data.get("status") == "ok":
                        all_articles.extend(data.get("articles", []))
                except Exception as e:
                    print(f"[NewsAPI] query '{query}' failed: {e}")
                    continue

        return self._normalize_newsapi(all_articles, date)

    def _normalize_newsapi(self, articles: list, date: str) -> List[NewsItem]:
        """将 NewsAPI 原始数据转为 NewsItem"""
        items = []
        total = len(articles)
        for i, a in enumerate(articles):
            # NewsAPI 免费版无 popularity 字段，用排名倒序作为初始分
            raw_pop = a.get("popularity", 0) or 0
            if raw_pop > 0:
                hotness = self._normalize_score(raw_pop, max_val=10000)
            else:
                # 按返回顺序给分：越靠前分数越高 (90 → 50)
                hotness = 90 - (i / max(total, 1)) * 40 if total > 1 else 70
            items.append(NewsItem(
                title=a.get("title", "无标题"),
                url=a.get("url", ""),
                summary=(a.get("description") or "")[:500],
                source="NewsAPI",
                category=self._guess_category(a.get("title", "")),
                hotness=round(hotness, 1),
                date=date,
            ))
        return items

    # ── GitHub API ────────────────────────────────────

    async def _fetch_github(self, client: httpx.AsyncClient) -> List[NewsItem]:
        """从 GitHub 搜索 AI 相关热门仓库（最近一周创建/更新）"""
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "AI-News-Platform/1.0",
        }

        # 多个搜索维度并发
        search_queries = [
            "ai+topic:ai+created:>=" + self._last_week(),
            "llm+topic:llm+pushed:>=" + self._last_week(),
            "agent+topic:agent+pushed:>=" + self._last_week(),
        ]

        all_repos = []
        for q in search_queries:
            async with self._semaphore:
                try:
                    # 手写 URL：避免 httpx 把 + 编码为 %2B，GitHub API 不认
                    url = f"{GITHUB_API_BASE_URL}/search/repositories?q={q}&sort=stars&order=desc&per_page=15"
                    response = await client.get(url, headers=headers)
                    response.raise_for_status()
                    data = response.json()
                    all_repos.extend(data.get("items", []))
                except Exception as e:
                    print(f"[GitHub] search failed: {e}")
                    continue

        return self._normalize_github(all_repos)

    def _normalize_github(self, repos: list) -> List[NewsItem]:
        """将 GitHub repo 数据转为 NewsItem（含去重）"""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        seen = set()
        items = []
        for r in repos:
            full_name = r.get("full_name", "")
            if full_name in seen:
                continue
            seen.add(full_name)

            stars = r.get("stargazers_count", 0)
            hotness = self._normalize_score(stars, max_val=200000, use_log=True)

            items.append(NewsItem(
                title=full_name,
                url=r.get("html_url", ""),
                summary=(r.get("description") or "无描述")[:500],
                source="GitHub",
                category="GitHub项目",
                hotness=hotness,
                date=today,
            ))
        return items

    # ── 工具方法 ──────────────────────────────────────

    def _last_week(self) -> str:
        """返回 7 天前的日期字符串 (YYYY-MM-DD)"""
        from datetime import timedelta
        return (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")

    @staticmethod
    def _normalize_score(raw: float, max_val: float, use_log: bool = False) -> float:
        """
        将不同量纲的原始分数归一化到 [0, 100]。

        NewsAPI popularity: 线性归一化
        GitHub stars: 对数归一化（避免极端值）
        """
        if raw <= 0:
            return 0.0
        if use_log:
            # 对数归一化：log10 使 10 星 ≈ 20分, 100星 ≈ 40分, 1000星 ≈ 60分
            normalized = min(math.log10(raw + 1) / math.log10(max_val + 1) * 100, 100)
        else:
            normalized = min(raw / max_val * 100, 100)
        return round(normalized, 1)

    @staticmethod
    def _guess_category(title: str) -> str:
        """根据标题关键词猜测新闻分类"""
        title_lower = title.lower()
        if any(kw in title_lower for kw in ["launch", "发布", "上线", "platform", "平台"]):
            return "新平台上线"
        if any(kw in title_lower for kw in ["release", "update", "新功能", "发布", "model", "模型"]):
            return "新功能发布"
        if any(kw in title_lower for kw in ["tool", "工具", "app", "应用", "productivity"]):
            return "好用工具"
        if any(kw in title_lower for kw in ["github", "open source", "开源"]):
            return "GitHub项目"
        return "AI新闻"
