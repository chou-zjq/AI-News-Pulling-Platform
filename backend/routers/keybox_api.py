"""
KeyBox API 路由：管理 AI Provider 的 API Key。
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from models.database import Database
from models.keybox import ApiKeyRecord
from services.keyvault import KeyVault

router = APIRouter(prefix="/api/keys")
vault = KeyVault()


# ── 请求/响应模型 ────────────────────────────────────

class KeyCreateRequest(BaseModel):
    provider_id: str = Field(..., description="Provider ID，如 'openai', 'deepseek'")
    api_key: str = Field(..., description="API Key 明文")
    label: str = Field("", description="自定义标签")
    org_id: str = Field("", description="Org ID（OpenAI 等需要）")


class KeyUpdateRequest(BaseModel):
    api_key: str = Field("", description="新 API Key 明文（留空则不更新）")
    label: str = Field("", description="新标签")
    is_enabled: bool | None = None


# ── Provider ─────────────────────────────────────────

@router.get("/providers")
async def list_providers():
    """列出所有支持的 AI Provider"""
    db = Database.get()
    rows = db.conn.execute(
        "SELECT * FROM provider_registry ORDER BY display_name"
    ).fetchall()

    providers = []
    for r in rows:
        import json
        p = dict(r)
        p["models"] = json.loads(p.get("models", "[]"))
        p["requires_org_id"] = bool(p.get("requires_org_id", 0))
        providers.append(p)

    return providers


@router.get("/providers/{provider_id}")
async def get_provider(provider_id: str):
    """获取单个 Provider 详情"""
    db = Database.get()
    row = db.conn.execute(
        "SELECT * FROM provider_registry WHERE id = ?", (provider_id,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"未找到 Provider: {provider_id}")
    import json
    p = dict(row)
    p["models"] = json.loads(p.get("models", "[]"))
    p["requires_org_id"] = bool(p.get("requires_org_id", 0))
    return p


# ── Key CRUD ─────────────────────────────────────────

@router.get("")
async def list_keys():
    """列出所有已保存的 Key（脱敏）"""
    db = Database.get()
    rows = db.conn.execute(
        """SELECT k.*, p.display_name as provider_name
           FROM api_keys k
           LEFT JOIN provider_registry p ON k.provider_id = p.id
           ORDER BY k.created_at DESC"""
    ).fetchall()

    keys = []
    for r in rows:
        key_data = dict(r)
        # 脱敏：不传加密密文，只传 masked
        masked = vault.mask(vault.decrypt(key_data["api_key_encrypted"])) if key_data.get("api_key_encrypted") else "***"
        keys.append({
            "id": key_data["id"],
            "provider_id": key_data["provider_id"],
            "provider_name": key_data.get("provider_name", ""),
            "label": key_data.get("label", ""),
            "masked_key": masked,
            "is_enabled": bool(key_data.get("is_enabled", 1)),
            "priority": key_data.get("priority", 0),
            "usage_count": key_data.get("usage_count", 0),
            "last_used_at": key_data.get("last_used_at"),
            "created_at": key_data.get("created_at"),
        })

    return keys


@router.post("")
async def create_key(req: KeyCreateRequest):
    """添加新的 API Key（加密存储）"""
    db = Database.get()

    # 验证 provider 存在
    prov = db.conn.execute(
        "SELECT id FROM provider_registry WHERE id = ?", (req.provider_id,)
    ).fetchone()
    if not prov:
        raise HTTPException(status_code=400, detail=f"未知的 Provider: {req.provider_id}")

    encrypted_key = vault.encrypt(req.api_key)
    encrypted_org = vault.encrypt(req.org_id) if req.org_id else ""

    cursor = db.conn.execute(
        """INSERT INTO api_keys (provider_id, label, api_key_encrypted, org_id_encrypted)
           VALUES (?, ?, ?, ?)""",
        (req.provider_id, req.label, encrypted_key, encrypted_org),
    )
    db.conn.commit()

    return {
        "id": cursor.lastrowid,
        "provider_id": req.provider_id,
        "label": req.label,
        "masked_key": vault.mask(req.api_key),
    }


@router.delete("/{key_id}")
async def delete_key(key_id: int):
    """删除 API Key"""
    db = Database.get()
    db.conn.execute("DELETE FROM api_keys WHERE id = ?", (key_id,))
    db.conn.commit()
    return {"deleted": True, "id": key_id}


# ── Key 测试 ─────────────────────────────────────────

@router.post("/{key_id}/test")
async def test_key(key_id: int):
    """
    发送一个最小请求测试 Key 是否有效。
    根据 provider 类型调用对应的 API ping。
    """
    db = Database.get()
    row = db.conn.execute(
        "SELECT * FROM api_keys WHERE id = ?", (key_id,)
    ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Key 不存在")

    try:
        decrypted = vault.decrypt(row["api_key_encrypted"])
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"解密失败: {e}")

    provider_id = row["provider_id"]

    # 根据 provider 发送测试请求
    import httpx

    test_urls = {
        "openai": ("https://api.openai.com/v1/models", {"Authorization": f"Bearer {decrypted}"}),
        "anthropic": ("https://api.anthropic.com/v1/messages", {"x-api-key": decrypted, "anthropic-version": "2023-06-01"}),
        "deepseek": ("https://api.deepseek.com/v1/models", {"Authorization": f"Bearer {decrypted}"}),
        "google": (f"https://generativelanguage.googleapis.com/v1beta/models?key={decrypted}", {}),
        "moonshot": ("https://api.moonshot.cn/v1/models", {"Authorization": f"Bearer {decrypted}"}),
        "zhipu": ("https://open.bigmodel.cn/api/paas/v4/models", {"Authorization": f"Bearer {decrypted}"}),
        "qwen": ("https://dashscope.aliyuncs.com/compatible-mode/v1/models", {"Authorization": f"Bearer {decrypted}"}),
    }

    test_config = test_urls.get(provider_id)
    if not test_config:
        return {"valid": None, "message": f"Provider '{provider_id}' 暂不支持自动测试，请手动验证"}

    url, headers = test_config
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, headers=headers)
            valid = resp.status_code < 500  # 4xx 通常是密钥问题，5xx 是服务器问题
            return {
                "valid": valid and resp.status_code < 400,
                "status_code": resp.status_code,
                "message": "Key 有效" if resp.status_code < 400 else f"请求失败: HTTP {resp.status_code}",
            }
    except Exception as e:
        return {"valid": False, "status_code": 0, "message": f"请求异常: {str(e)}"}
