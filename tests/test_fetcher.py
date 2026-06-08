"""新闻抓取服务单元测试"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from models.news import NewsItem
from services.fetcher import NewsFetcher


class TestNewsItem:
    """NewsItem 数据模型测试"""

    def test_id_is_stable(self):
        """相同 title + url 应生成相同 ID"""
        n1 = NewsItem(title="Test News", url="https://example.com")
        n2 = NewsItem(title="Test News", url="https://example.com")
        assert n1.id == n2.id

    def test_id_differs_for_different_urls(self):
        """不同 URL 应生成不同 ID"""
        n1 = NewsItem(title="Same Title", url="https://a.com")
        n2 = NewsItem(title="Same Title", url="https://b.com")
        assert n1.id != n2.id

    def test_to_dict_and_from_dict(self):
        """序列化/反序列化 roundtrip"""
        n = NewsItem(
            title="GPT-5 Released",
            url="https://openai.com",
            summary="New model",
            source="NewsAPI",
            category="新功能发布",
            hotness=95.0,
            date="2026-06-08",
        )
        d = n.to_dict()
        restored = NewsItem.from_dict(d)
        assert restored.title == n.title
        assert restored.url == n.url
        assert restored.hotness == 95.0
        assert restored.id == n.id


class TestNormalizeScore:
    """热度归一化测试"""

    def test_linear_normalization(self):
        """线性归一化"""
        fetcher = NewsFetcher()
        score = fetcher._normalize_score(50, max_val=100, use_log=False)
        assert score == 50.0

    def test_log_normalization_small_value(self):
        """对数归一化：小数值"""
        fetcher = NewsFetcher()
        score = fetcher._normalize_score(10, max_val=5000, use_log=True)
        assert 0 < score < 100

    def test_log_normalization_large_value(self):
        """对数归一化：大数值"""
        fetcher = NewsFetcher()
        score = fetcher._normalize_score(100000, max_val=5000, use_log=True)
        assert score == 100.0  # 超出 max_val 应封顶

    def test_zero_score(self):
        """零分输入返回零分"""
        fetcher = NewsFetcher()
        assert fetcher._normalize_score(0, max_val=100) == 0.0


class TestGuessCategory:
    """新闻分类猜测测试"""

    def test_platform_launch(self):
        assert NewsFetcher._guess_category("New AI platform launched") == "新平台上线"
        assert NewsFetcher._guess_category("某某平台上线") == "新平台上线"

    def test_new_feature(self):
        assert NewsFetcher._guess_category("OpenAI releases GPT-5 model") == "新功能发布"
        assert NewsFetcher._guess_category("新功能发布：支持视频理解") == "新功能发布"

    def test_tool(self):
        assert NewsFetcher._guess_category("Best AI productivity tool") == "好用工具"

    def test_github(self):
        assert NewsFetcher._guess_category("New open source GitHub project") == "GitHub项目"
