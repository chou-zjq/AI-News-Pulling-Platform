"""
新闻相关 API 路由。
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from config import RECORD_LIBRARY_DIR
from models.database import Database
from models.news import NewsItem
from services.fetcher import NewsFetcher
from services.recorder import RecordManager
from services.summarizer import NewsSummarizer

router = APIRouter(prefix="/api")


@router.get("/news/fetch")
async def fetch_news(force: bool = Query(False, description="强制重新抓取，忽略缓存")):
    """
    主查询接口：抓取当日 AI 新闻，返回 Top 20。
    - 如果当天已抓取且 force=False，直接返回缓存
    - 否则并发调用 NewsAPI + GitHub API
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    db = Database.get()

    # 检查缓存
    if not force:
        cached = db.conn.execute(
            "SELECT top20_ids, fetch_count FROM fetch_log WHERE date = ?", (today,)
        ).fetchone()

        if cached:
            top20_ids = json.loads(cached["top20_ids"])
            if top20_ids:
                # 从 news_index 重建列表
                items = _query_by_ids(db, top20_ids)
                # 如果缓存数据没有中文摘要，补充生成
                if items and not any(item.get("summary_cn") for item in items):
                    news_objs = [NewsItem(
                        title=it["title"], url=it["url"],
                        summary=it.get("summary", ""), source=it.get("source", ""),
                        category=it.get("category", "未分类"), hotness=it.get("hotness", 0),
                        date=it.get("date", today),
                    ) for it in items]
                    summarizer = NewsSummarizer()
                    await summarizer.summarize(news_objs)
                    for i, it in enumerate(items):
                        it["summary_cn"] = news_objs[i].summary_cn
                        db.conn.execute(
                            "UPDATE news_index SET summary_cn = ? WHERE id = ?",
                            (news_objs[i].summary_cn, it["id"]),
                        )
                    db.conn.commit()
                return {
                    "date": today,
                    "total_fetched": cached["fetch_count"],
                    "count": len(items),
                    "cached": True,
                    "news": [item for item in items],
                }

    # 抓取新数据
    try:
        fetcher = NewsFetcher()
        raw_news = await fetcher.fetch_all()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not raw_news:
        return {
            "date": today,
            "total_fetched": 0,
            "count": 0,
            "cached": False,
            "news": [],
            "message": "今日未获取到 AI 相关新闻，请稍后再试",
        }

    # 排序 + Top 20
    sorted_news = sorted(raw_news, key=lambda n: n.hotness, reverse=True)
    top20 = sorted_news[:20]

    # AI 生成中文摘要
    summarizer = NewsSummarizer()
    await summarizer.summarize(top20)

    # 存入 news_index
    _save_to_index(db, top20, today)

    # 存入 fetch_log
    top20_ids = [n.id for n in top20]
    db.conn.execute(
        """INSERT OR REPLACE INTO fetch_log (date, fetch_count, top20_ids, fetched_at)
           VALUES (?, ?, ?, ?)""",
        (today, len(raw_news), json.dumps(top20_ids), datetime.now(timezone.utc).isoformat()),
    )
    db.conn.commit()

    # 生成 Markdown 记录本
    recorder = RecordManager()
    record_path = recorder.generate(top20, today)

    # 更新 record_path
    for n in top20:
        db.conn.execute("UPDATE news_index SET record_path = ? WHERE id = ?", (str(record_path), n.id))
    db.conn.commit()

    return {
        "date": today,
        "total_fetched": len(raw_news),
        "count": len(top20),
        "cached": False,
        "record_path": str(record_path),
        "news": [n.to_dict() for n in top20],
    }


@router.get("/records")
async def get_record(date: str = Query(..., description="日期 YYYY-MM-DD")):
    """获取指定日期的记录本内容"""
    db = Database.get()
    rows = db.conn.execute(
        "SELECT * FROM news_index WHERE date = ? ORDER BY hotness DESC", (date,)
    ).fetchall()

    if not rows:
        # 尝试从文件系统读取
        year, month, day = date.split("-")
        file_path = RECORD_LIBRARY_DIR / year / month / f"{date}.md"
        if file_path.exists():
            return {
                "date": date,
                "source": "file",
                "markdown": file_path.read_text(encoding="utf-8"),
            }
        raise HTTPException(status_code=404, detail=f"未找到 {date} 的记录本")

    return {
        "date": date,
        "source": "database",
        "count": len(rows),
        "news": [dict(r) for r in rows],
    }


@router.get("/records/history")
async def get_history():
    """
    返回历史记录树形结构，格式：
    [
      {"year": "2026", "months": [
        {"month": "06", "days": ["06-08", "06-07"]},
        {"month": "05", "days": ["05-31"]}
      ]}
    ]
    """
    db = Database.get()
    rows = db.conn.execute(
        "SELECT DISTINCT date FROM news_index ORDER BY date DESC"
    ).fetchall()

    # 同时扫描文件系统中的记录
    file_dates = set()
    if RECORD_LIBRARY_DIR.exists():
        for md_file in RECORD_LIBRARY_DIR.rglob("*.md"):
            # 路径格式: RecordLibrary/2026/06/2026-06-08.md
            date_str = md_file.stem  # "2026-06-08"
            file_dates.add(date_str)

    # 合并数据库和文件系统的日期
    all_dates = set(r["date"] for r in rows) | file_dates
    sorted_dates = sorted(all_dates, reverse=True)

    # 构建树
    tree: dict[str, dict[str, list]] = {}
    for d in sorted_dates:
        parts = d.split("-")
        if len(parts) != 3:
            continue
        year, month, day = parts
        if year not in tree:
            tree[year] = {}
        if month not in tree[year]:
            tree[year][month] = []
        tree[year][month].append(day)

    result = []
    for year in sorted(tree.keys(), reverse=True):
        months = []
        for month in sorted(tree[year].keys(), reverse=True):
            months.append({
                "month": month,
                "days": sorted(tree[year][month], reverse=True),
            })
        result.append({"year": year, "months": months})

    return result


# ── 辅助函数 ─────────────────────────────────────────

def _save_to_index(db: Database, news_list: list, date: str):
    """批量 upsert 新闻到索引表"""
    rows = [
        (n.id, n.title, n.summary, n.summary_cn, n.url, n.source, n.category, n.hotness, date, "")
        for n in news_list
    ]
    db.conn.executemany(
        """INSERT OR REPLACE INTO news_index
           (id, title, summary, summary_cn, url, source, category, hotness, date, record_path)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )


def _query_by_ids(db: Database, ids: list[str]) -> list[dict]:
    """按 ID 列表查询并保持原有排序"""
    if not ids:
        return []
    placeholders = ",".join("?" for _ in ids)
    rows = db.conn.execute(
        f"SELECT * FROM news_index WHERE id IN ({placeholders})",
        ids,
    ).fetchall()
    # 按传入 ID 顺序排列
    row_map = {r["id"]: dict(r) for r in rows}
    return [row_map[i] for i in ids if i in row_map]
