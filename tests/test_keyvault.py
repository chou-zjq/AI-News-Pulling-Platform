"""KeyVault 加解密单元测试"""

import os
import tempfile
from pathlib import Path

import pytest

# 确保 backend 在 sys.path 中
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from services.keyvault import KeyVault


class TestKeyVault:
    """KeyVault 加解密功能测试"""

    def test_encrypt_decrypt_roundtrip(self):
        """加密后解密应该得到原文"""
        with tempfile.TemporaryDirectory() as tmpdir:
            secret_path = Path(tmpdir) / ".keybox-secret"
            vault = KeyVault(secret_path=secret_path)

            plaintext = "sk-test-api-key-12345678"
            encrypted = vault.encrypt(plaintext)
            decrypted = vault.decrypt(encrypted)

            assert decrypted == plaintext
            assert encrypted != plaintext  # 密文不等于原文

    def test_key_persists_across_instances(self):
        """密钥文件应持久化，不同实例共用"""
        with tempfile.TemporaryDirectory() as tmpdir:
            secret_path = Path(tmpdir) / ".keybox-secret"

            # 第一个实例生成密钥并加密
            vault1 = KeyVault(secret_path=secret_path)
            encrypted = vault1.encrypt("my-secret-key")

            # 第二个实例应能解密
            vault2 = KeyVault(secret_path=secret_path)
            decrypted = vault2.decrypt(encrypted)

            assert decrypted == "my-secret-key"

    def test_decrypt_invalid_ciphertext_raises(self):
        """解密损坏的密文应抛出错误"""
        vault = KeyVault()

        with pytest.raises(ValueError, match="解密失败"):
            vault.decrypt("this-is-not-valid-ciphertext")

    def test_mask_short_key(self):
        """短 Key 脱敏"""
        vault = KeyVault()
        assert vault.mask("abc") == "***"
        assert vault.mask("12345678") == "********"

    def test_mask_long_key(self):
        """长 Key 脱敏：保留首尾 4 字符"""
        vault = KeyVault()
        masked = vault.mask("sk-proj-abcdefg-12345678")
        assert masked.startswith("sk-p")
        assert masked.endswith("5678")
        assert "****" in masked
