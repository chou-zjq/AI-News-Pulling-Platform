"""
记录本生成器：将 NewsItem 列表转为 Markdown 文件，按年月归档。
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import List

from config import RECORD_LIBRARY_DIR
from models.news import NewsItem


MARKDOWN_TEMPLATE = """# 🤖 AI 新闻日报 — {date_display}

> 共抓取 {total} 条新闻，精选 Top {top_n} | 生成时间：{generated_at}

---

{content}

---

*本记录由 AI 新闻调取平台自动生成*
"""


class RecordManager:
    """管理 Markdown 记录本的生成与存储"""

    def generate(self, news_list: List[NewsItem], date: str | None = None) -> Path:
        """
        生成当天的 Markdown 记录本，保存到 RecordLibrary/年/月/日.md。
        返回文件路径。
        """
        if date is None:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # 按分类分组
        groups: dict[str, list[NewsItem]] = {
            "新功能发布": [],
            "新平台上线": [],
            "好用工具": [],
            "GitHub项目": [],
            "AI新闻": [],
        }
        for n in news_list:
            cat = n.category if n.category in groups else "AI新闻"
            groups[cat].append(n)

        # 生成各分类表格
        sections = []
        emoji_map = {
            "新功能发布": "🔥",
            "新平台上线": "🚀",
            "好用工具": "🛠",
            "GitHub项目": "📦",
            "AI新闻": "📰",
        }

        for cat, items in groups.items():
            if not items:
                continue
            emoji = emoji_map.get(cat, "📌")
            section = f"## {emoji} {cat}\n\n"
            has_cn = any(item.summary_cn for item in items)
            if has_cn:
                section += "| # | 标题 | 中文摘要 | 热度 |\n"
                section += "|---|------|----------|------|\n"
                for i, item in enumerate(items, 1):
                    cn = item.summary_cn or item.summary[:60]
                    section += f"| {i} | [{item.title}]({item.url}) | {cn} | ⭐{item.hotness:.0f} |\n"
            else:
                section += "| # | 标题 | 热度 |\n"
                section += "|---|------|------|\n"
                for i, item in enumerate(items, 1):
                    section += f"| {i} | [{item.title}]({item.url}) — {item.summary[:80]} | ⭐{item.hotness:.0f} |\n"
            sections.append(section)

        content = "\n\n".join(sections) if sections else "*今日无相关新闻*"

        # 格式化日期显示
        try:
            dt = datetime.strptime(date, "%Y-%m-%d")
            date_display = dt.strftime("%Y年%m月%d日")
        except ValueError:
            date_display = date

        markdown = MARKDOWN_TEMPLATE.format(
            date_display=date_display,
            total=len(news_list),
            top_n=len(news_list),
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
            content=content,
        )

        # 写入文件
        year, month, day = date.split("-")
        dir_path = RECORD_LIBRARY_DIR / year / month
        dir_path.mkdir(parents=True, exist_ok=True)

        file_path = dir_path / f"{date}.md"
        file_path.write_text(markdown, encoding="utf-8")

        return file_path

    def read(self, date: str) -> str | None:
        """读取指定日期的记录本"""
        try:
            year, month, day = date.split("-")
            file_path = RECORD_LIBRARY_DIR / year / month / f"{date}.md"
            if file_path.exists():
                return file_path.read_text(encoding="utf-8")
        except (ValueError, OSError):
            pass
        return None

    def list_dates(self) -> list[str]:
        """扫描文件系统，返回所有有记录本的日期列表"""
        dates = []
        if RECORD_LIBRARY_DIR.exists():
            for md_file in sorted(RECORD_LIBRARY_DIR.rglob("*.md"), reverse=True):
                dates.append(md_file.stem)
        return dates
