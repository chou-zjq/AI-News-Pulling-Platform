"""
KeyBox 数据模型：Provider 注册表 + API Key 管理。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


# ── 内置 Provider 注册表 ──────────────────────────────
# 这些数据随代码发布，用户可以通过数据库追加自定义 Provider

BUILTIN_PROVIDERS = [
    {
        "id": "openai",
        "display_name": "OpenAI",
        "api_base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o3-mini"],
        "docs_url": "https://platform.openai.com/api-keys",
        "logo_color": "#10A37F",
        "requires_org_id": True,
    },
    {
        "id": "anthropic",
        "display_name": "Anthropic",
        "api_base_url": "https://api.anthropic.com/v1",
        "models": ["claude-opus-4-8", "claude-sonnet-4-6", "claude-haiku-4-5"],
        "docs_url": "https://console.anthropic.com/keys",
        "logo_color": "#D97757",
        "requires_org_id": False,
    },
    {
        "id": "deepseek",
        "display_name": "DeepSeek",
        "api_base_url": "https://api.deepseek.com/v1",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "docs_url": "https://platform.deepseek.com/api_keys",
        "logo_color": "#4D6BFE",
        "requires_org_id": False,
    },
    {
        "id": "agnes-ai",
        "display_name": "Agnes AI",
        "api_base_url": "https://api.agnes.ai/v1",
        "models": ["agnes-pro", "agnes-fast"],
        "docs_url": "https://agnes.ai/dashboard",
        "logo_color": "#FF6B6B",
        "requires_org_id": False,
    },
    {
        "id": "google",
        "display_name": "Google AI",
        "api_base_url": "https://generativelanguage.googleapis.com/v1beta",
        "models": ["gemini-2.5-pro", "gemini-2.5-flash"],
        "docs_url": "https://aistudio.google.com/apikey",
        "logo_color": "#4285F4",
        "requires_org_id": False,
    },
    {
        "id": "zhipu",
        "display_name": "智谱 GLM",
        "api_base_url": "https://open.bigmodel.cn/api/paas/v4",
        "models": ["glm-4-plus", "glm-4-flash", "glm-4-flashx"],
        "docs_url": "https://open.bigmodel.cn/usercenter/apikeys",
        "logo_color": "#3859F3",
        "requires_org_id": False,
    },
    {
        "id": "moonshot",
        "display_name": "Moonshot (Kimi)",
        "api_base_url": "https://api.moonshot.cn/v1",
        "models": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
        "docs_url": "https://platform.moonshot.cn/console/api-keys",
        "logo_color": "#00D4AA",
        "requires_org_id": False,
    },
    {
        "id": "qwen",
        "display_name": "通义千问",
        "api_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": ["qwen-max", "qwen-plus", "qwen-turbo"],
        "docs_url": "https://dashscope.console.aliyun.com/apiKey",
        "logo_color": "#6B57FF",
        "requires_org_id": False,
    },
]

# ── KeyBox 数据类 ─────────────────────────────────────

@dataclass
class ApiKeyRecord:
    """存储在数据库中的 Key 记录"""
    id: Optional[int] = None
    provider_id: str = ""
    label: str = ""
    api_key_encrypted: str = ""      # Fernet 加密后的密文
    org_id_encrypted: str = ""       # 可选的 org_id 密文
    is_enabled: bool = True
    priority: int = 0
    usage_count: int = 0
    last_used_at: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_masked_dict(self) -> dict:
        """返回给前端的字典（Key 脱敏）"""
        masked = self._mask(self._decrypt_length(self.api_key_encrypted))
        return {
            "id": self.id,
            "provider_id": self.provider_id,
            "label": self.label,
            "masked_key": masked,
            "is_enabled": self.is_enabled,
            "priority": self.priority,
            "usage_count": self.usage_count,
            "last_used_at": self.last_used_at,
        }

    @staticmethod
    def _decrypt_length(encrypted: str) -> int:
        """估算原始 Key 长度（Fernet 加密后长度可推算）"""
        # Fernet: base64 编码，粗略估计原始长度
        try:
            from base64 import b64decode
            decoded = b64decode(encrypted.encode() if isinstance(encrypted, str) else encrypted)
            # Fernet token: version(1) + timestamp(8) + iv(16) + ciphertext + tag(16)
            padding = 1 + 8 + 16 + 16
            return max(len(decoded) - padding, 0)
        except Exception:
            return len(encrypted)  # fallback

    @staticmethod
    def _mask(estimated_len: int) -> str:
        """生成脱敏字符串，如 'sk-****x9a1'"""
        if estimated_len <= 8:
            return "*" * min(estimated_len, 6)
        return "*" * 8
