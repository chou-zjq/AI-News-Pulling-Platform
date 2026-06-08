"""
AI 新闻摘要服务：调用 LLM 为每条新闻生成中文摘要。
从 KeyBox 读取已保存的 API Key，批量调用 LLM。
对 GitHub 项目会先拉取 README 供 AI 阅读后再写摘要。
"""

import re
import json
import asyncio
from typing import List, Optional

import httpx

from config import GITHUB_TOKEN
from models.database import Database
from models.news import NewsItem
from services.keyvault import KeyVault


# ── Provider → (model, API 格式) 映射 ────────────────
OPENAI_COMPATIBLE = {"openai", "agnes-ai", "deepseek", "moonshot", "zhipu", "qwen"}

PROVIDER_MODEL = {
    "openai":      "gpt-4o-mini",
    "agnes-ai":    "agnes-fast",
    "deepseek":    "deepseek-chat",
    "moonshot":    "moonshot-v1-8k",
    "zhipu":       "glm-4-flash",
    "qwen":        "qwen-max",       # 用户有 qwen-max key，比 turbo 强
    "anthropic":   "claude-haiku-4-5",
    "google":      "gemini-2.5-flash",
}

SUMMARIZE_TIMEOUT = 60       # LLM 调用超时（秒）
GITHUB_README_TIMEOUT = 15   # GitHub README 拉取超时
MAX_ITEMS_PER_BATCH = 5      # 每批最多 5 条，保证摘要质量和中文一致性
PER_ITEM_MAX_CHARS = 500     # 每条新闻的原文素材最大字符数


class NewsSummarizer:
    """调用 LLM 批量生成新闻中文摘要"""

    def __init__(self):
        self._api_key: Optional[str] = None
        self._provider_id: Optional[str] = None
        self._api_base: Optional[str] = None
        self._model: Optional[str] = None
        self._load_key()

    # ── Key 加载 ──────────────────────────────────

    def _load_key(self):
        """从 KeyBox 取第一个启用的 Key，解密并配置 API 参数"""
        db = Database.get()
        row = db.conn.execute(
            """SELECT k.*, p.api_base_url
               FROM api_keys k
               JOIN provider_registry p ON k.provider_id = p.id
               WHERE k.is_enabled = 1
               ORDER BY k.priority DESC, k.created_at DESC
               LIMIT 1"""
        ).fetchone()

        if not row:
            print("[Summarizer] 没有可用的 API Key，跳过 AI 摘要")
            return

        vault = KeyVault()
        try:
            self._api_key = vault.decrypt(row["api_key_encrypted"])
        except ValueError as e:
            print(f"[Summarizer] Key 解密失败: {e}")
            return

        self._provider_id = row["provider_id"]
        self._api_base = row["api_base_url"].rstrip("/")
        self._model = PROVIDER_MODEL.get(self._provider_id, "gpt-4o-mini")
        print(f"[Summarizer] 使用 {self._provider_id}/{self._model} 生成摘要")

    # ── 公开入口 ──────────────────────────────────

    async def summarize(self, news_items: List[NewsItem]) -> None:
        """
        为 news_items 批量生成中文摘要，结果直接写入各 item.summary_cn。
        无可用 Key 时静默跳过。
        """
        if not self._api_key or not news_items:
            return

        # 先为 GitHub 项目拉取 README 内容（存临时 dict，不污染原数据）
        enriched = await self._enrich_github(news_items)

        # 分批处理（每批最多 MAX_ITEMS_PER_BATCH 条，保证摘要质量）
        for batch_start in range(0, len(news_items), MAX_ITEMS_PER_BATCH):
            batch = news_items[batch_start:batch_start + MAX_ITEMS_PER_BATCH]
            prompt = self._build_prompt(batch, enriched)

            try:
                raw = await self._call_llm(prompt)
                summaries = self._parse_response(raw, len(batch))
            except Exception as e:
                print(f"[Summarizer] LLM 调用失败 (batch {batch_start}): {e}")
                self._fallback(batch)
                continue

            # 检查中文率，太低则重试一次
            cn_ratio = sum(1 for s in summaries if self._is_chinese(s)) / max(len(summaries), 1)
            if cn_ratio < 0.5:
                print(f"[Summarizer] 中文率仅 {cn_ratio:.0%}，重试中...")
                retry_prompt = "【重要：你必须用中文回复，禁止英文！】\n\n" + prompt
                try:
                    raw = await self._call_llm(retry_prompt)
                    summaries = self._parse_response(raw, len(batch))
                except Exception as e:
                    print(f"[Summarizer] 重试失败: {e}")

            for i, item in enumerate(batch):
                if i < len(summaries) and summaries[i] and self._is_chinese(summaries[i]):
                    item.summary_cn = summaries[i]
                else:
                    item.summary_cn = item.summary[:100] + "…" if len(item.summary) > 100 else item.summary

    def _fallback(self, news_items: List[NewsItem]):
        """降级：截取原文摘要"""
        for item in news_items:
            text = item.summary or item.title
            item.summary_cn = (text[:100] + "…") if len(text) > 100 else text

    # ── GitHub README 拉取 ────────────────────────

    async def _enrich_github(self, news_items: List[NewsItem]) -> dict:
        """
        为 GitHub 来源的新闻拉取 README 内容。
        返回 dict: item_id → readme_text（不修改原始数据）
        """
        github_items = [item for item in news_items if item.source == "GitHub"]
        result: dict[str, str] = {}

        if not github_items or not GITHUB_TOKEN:
            return result

        print(f"[Summarizer] 拉取 {len(github_items)} 个 GitHub 项目的 README...")

        async def fetch_readme(item: NewsItem):
            try:
                parts = item.url.rstrip("/").split("/")
                if len(parts) < 5:
                    return
                owner, repo = parts[-2], parts[-1]

                headers = {
                    "Authorization": f"Bearer {GITHUB_TOKEN}",
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "AI-News-Platform/1.0",
                }

                async with httpx.AsyncClient(timeout=GITHUB_README_TIMEOUT) as client:
                    resp = await client.get(
                        f"https://api.github.com/repos/{owner}/{repo}/readme",
                        headers=headers,
                    )
                    if resp.status_code != 200:
                        return

                    readme_data = resp.json()
                    readme_content = readme_data.get("content", "")

                    import base64
                    try:
                        text = base64.b64decode(readme_content).decode("utf-8", errors="replace")
                    except Exception:
                        return

                    text = text.strip()[:800]
                    result[item.id] = text
                    print(f"  [OK] {owner}/{repo}: README {len(text)} 字符")
            except Exception as e:
                print(f"  [skip] {item.title}: {e}")

        sem = asyncio.Semaphore(3)
        async def limited(item):
            async with sem:
                await fetch_readme(item)

        await asyncio.gather(*[limited(item) for item in github_items])
        return result

    # ── Prompt 构建 ───────────────────────────────

    def _build_prompt(self, news_items: List[NewsItem], enriched: dict[str, str] | None = None) -> str:
        """构建中文摘要 prompt。enriched: item_id → GitHub README 文本（可选）"""
        if enriched is None:
            enriched = {}

        lines = []
        for i, item in enumerate(news_items, 1):
            title = item.title.strip()
            has_non_ascii = any(ord(c) > 127 for c in title)
            lang_hint = "" if has_non_ascii else " [原文为英文]"

            # 拼合原文素材：GitHub README（如有） + 原文摘要
            parts = []
            readme_text = enriched.get(item.id, "")
            if readme_text:
                parts.append(f"GitHub README：{readme_text}")
            raw_summary = (item.summary or "").strip()
            if raw_summary and len(raw_summary) > 10:
                parts.append(f"项目描述：{raw_summary[:PER_ITEM_MAX_CHARS]}")

            if parts:
                context = "\n".join(parts)
                lines.append(f"新闻{i}：{title}{lang_hint}\n原文信息：\n{context}\n")
            else:
                lines.append(f"新闻{i}：{title}{lang_hint}\n")

        items_text = "\n".join(lines)

        return f"""请用中文为以下每条新闻写摘要。必须使用中文！

要求（每条新闻）：
- 写 2~3 句话，总计 50~120 字
- 第一句：概括新闻核心事件（谁、做了什么）
- 第二句：补充关键细节或技术要点
- 第三句（可选）：说明意义或影响
- 保留专有名词原文（公司名、产品名、技术名）
- 禁止使用英文！必须用中文重新编写所有内容

{items_text}

请严格按以下格式回复（必须中文，每条一行）：
1. [中文摘要]
2. [中文摘要]
..."""

    @staticmethod
    def _is_chinese(text: str) -> bool:
        """检查文本是否包含中文字符"""
        return any('一' <= c <= '鿿' or '㐀' <= c <= '䶿' for c in text)

    # ── 响应解析 ──────────────────────────────────

    def _parse_response(self, raw: str, expected_count: int) -> List[str]:
        """从 LLM 回复中提取编号列表"""
        pattern = r'^\s*(\d+)\s*[.、)）]\s*(.+)$'
        results: dict[int, str] = {}

        for line in raw.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            m = re.match(pattern, line)
            if m:
                idx = int(m.group(1))
                text = m.group(2).strip()
                text = text.strip('"\'"\'；;，,。.')
                if text:
                    results[idx] = text

        summaries = [results.get(i + 1, "") for i in range(expected_count)]
        return summaries

    # ── LLM API 调用 ──────────────────────────────

    async def _call_llm(self, prompt: str) -> str:
        """根据 provider 类型调用对应的 LLM API"""
        if self._provider_id in OPENAI_COMPATIBLE:
            return await self._call_openai_compatible(prompt)
        elif self._provider_id == "anthropic":
            return await self._call_anthropic(prompt)
        elif self._provider_id == "google":
            return await self._call_google(prompt)
        else:
            return await self._call_openai_compatible(prompt)

    async def _call_openai_compatible(self, prompt: str) -> str:
        """OpenAI /chat/completions 兼容格式"""
        url = f"{self._api_base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        body = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": "你是一名中国科技新闻编辑。你必须使用中文回复，禁止使用英文。即使原文是英文，你也要理解后用中文重新编写摘要。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.4,
            "max_tokens": 4000,
        }

        async with httpx.AsyncClient(timeout=SUMMARIZE_TIMEOUT) as client:
            resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def _call_anthropic(self, prompt: str) -> str:
        """Anthropic /v1/messages 格式"""
        url = f"{self._api_base}/messages"
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        body = {
            "model": self._model,
            "max_tokens": 4000,
            "temperature": 0.4,
            "system": "你是专业的中文科技新闻编辑。你对AI、编程、开源领域有深入理解。你善于从英文原文中提取关键信息并用简洁流畅的中文重新编写。你严格按编号列表格式回复。",
            "messages": [{"role": "user", "content": prompt}],
        }

        async with httpx.AsyncClient(timeout=SUMMARIZE_TIMEOUT) as client:
            resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()
            return data["content"][0]["text"]

    async def _call_google(self, prompt: str) -> str:
        """Google AI generateContent 格式"""
        model = self._model or "gemini-2.5-flash"
        url = f"{self._api_base}/models/{model}:generateContent?key={self._api_key}"
        body = {
            "systemInstruction": {
                "parts": [{"text": "你是专业的中文科技新闻编辑。你对AI、编程、开源领域有深入理解。你善于从英文原文中提取关键信息并用简洁流畅的中文重新编写。你严格按编号列表格式回复。"}],
            },
            "contents": [{
                "parts": [{"text": prompt}],
            }],
        }

        async with httpx.AsyncClient(timeout=SUMMARIZE_TIMEOUT) as client:
            resp = await client.post(url, json=body)
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
