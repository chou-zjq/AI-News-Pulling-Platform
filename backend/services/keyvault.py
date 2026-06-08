"""
KeyVault — API Key 加密/解密服务。
使用 Fernet (AES-128-CBC + HMAC) 对称加密。
"""

import os
from pathlib import Path

from cryptography.fernet import Fernet

from config import KEYBOX_SECRET_FILE


class KeyVault:
    """
    Key 保险箱，提供加密/解密/脱敏。

    安全模型：
    - 首次运行时生成机器密钥，存于 data/.keybox-secret（权限 600）
    - 数据库中的 api_key_encrypted 通过此密钥加密
    - 数据库泄露 + secret 文件未泄露 = Key 安全
    """

    def __init__(self, secret_path: Path = KEYBOX_SECRET_FILE):
        self.secret_path = secret_path
        self._fernet: Fernet | None = None

    @property
    def fernet(self) -> Fernet:
        if self._fernet is None:
            key = self._load_or_create_key()
            self._fernet = Fernet(key)
        return self._fernet

    def _load_or_create_key(self) -> bytes:
        """加载已有密钥，不存在则生成新密钥"""
        if self.secret_path.exists():
            return self.secret_path.read_bytes()

        # 生成新密钥
        key = Fernet.generate_key()
        self.secret_path.parent.mkdir(parents=True, exist_ok=True)
        self.secret_path.write_bytes(key)

        # Windows: 设文件权限为仅 owner 可读写
        try:
            os.chmod(self.secret_path, 0o600)
        except (OSError, PermissionError):
            pass  # 非 Unix 系统可能不支持 chmod，忽略

        return key

    def encrypt(self, plaintext: str) -> str:
        """加密明文 Key"""
        return self.fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        """
        解密密文 Key。
        仅在调用时解密到内存，用完即弃。
        """
        try:
            return self.fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except Exception:
            raise ValueError("密钥解密失败：密文损坏或 secret 文件不匹配")

    def mask(self, plaintext: str) -> str:
        """脱敏显示：保留首尾各 4 个字符，其余替换为 *"""
        if len(plaintext) <= 8:
            return "*" * len(plaintext)
        return f"{plaintext[:4]}{'*' * min(len(plaintext) - 8, 12)}{plaintext[-4:]}"
