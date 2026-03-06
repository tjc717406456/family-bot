"""
密码对称加密工具 — 基于 Fernet (AES-128-CBC + HMAC-SHA256)

密钥自动生成并持久化到 data/.encryption_key，首次调用时创建。
提供 encrypt / decrypt / decrypt_safe 三个公共函数。
"""

import logging
import os

from cryptography.fernet import Fernet, InvalidToken

from config import DATA_DIR

logger = logging.getLogger(__name__)

_KEY_FILE = os.path.join(DATA_DIR, ".encryption_key")
_fernet_instance = None


def _get_fernet() -> Fernet:
    global _fernet_instance
    if _fernet_instance is not None:
        return _fernet_instance

    if os.path.exists(_KEY_FILE):
        with open(_KEY_FILE, "rb") as f:
            key = f.read().strip()
    else:
        key = Fernet.generate_key()
        with open(_KEY_FILE, "wb") as f:
            f.write(key)
        logger.info("已生成新的加密密钥: %s", _KEY_FILE)

    _fernet_instance = Fernet(key)
    return _fernet_instance


def encrypt(plaintext: str) -> str:
    """加密明文，返回 base64 编码密文字符串"""
    return _get_fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt(ciphertext: str) -> str:
    """解密密文，返回明文字符串。密文无效时抛出 InvalidToken。"""
    return _get_fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")


def decrypt_safe(value: str) -> str:
    """
    尝试解密；如果失败则假定为未加密的旧数据，原样返回。
    用于向后兼容：已有的明文密码在首次读取时不会报错。
    """
    if not value:
        return value
    try:
        return decrypt(value)
    except (InvalidToken, Exception):
        return value
