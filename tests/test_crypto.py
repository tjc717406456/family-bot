"""加密工具单元测试"""

import os


class TestCrypto:
    def test_encrypt_decrypt_roundtrip(self, tmp_path, monkeypatch):
        monkeypatch.setattr("utils.crypto.DATA_DIR", str(tmp_path))
        monkeypatch.setattr("utils.crypto._fernet_instance", None)
        monkeypatch.setattr("utils.crypto._KEY_FILE", str(tmp_path / ".encryption_key"))

        from utils.crypto import encrypt, decrypt
        original = "my-secret-password-123"
        encrypted = encrypt(original)

        assert encrypted != original
        assert decrypt(encrypted) == original

    def test_decrypt_safe_with_plaintext(self, tmp_path, monkeypatch):
        monkeypatch.setattr("utils.crypto.DATA_DIR", str(tmp_path))
        monkeypatch.setattr("utils.crypto._fernet_instance", None)
        monkeypatch.setattr("utils.crypto._KEY_FILE", str(tmp_path / ".encryption_key"))

        from utils.crypto import decrypt_safe
        assert decrypt_safe("plain-text-password") == "plain-text-password"

    def test_decrypt_safe_with_encrypted(self, tmp_path, monkeypatch):
        monkeypatch.setattr("utils.crypto.DATA_DIR", str(tmp_path))
        monkeypatch.setattr("utils.crypto._fernet_instance", None)
        monkeypatch.setattr("utils.crypto._KEY_FILE", str(tmp_path / ".encryption_key"))

        from utils.crypto import encrypt, decrypt_safe
        encrypted = encrypt("secret123")
        assert decrypt_safe(encrypted) == "secret123"

    def test_decrypt_safe_empty_string(self, tmp_path, monkeypatch):
        monkeypatch.setattr("utils.crypto.DATA_DIR", str(tmp_path))
        monkeypatch.setattr("utils.crypto._fernet_instance", None)
        monkeypatch.setattr("utils.crypto._KEY_FILE", str(tmp_path / ".encryption_key"))

        from utils.crypto import decrypt_safe
        assert decrypt_safe("") == ""
        assert decrypt_safe(None) is None

    def test_key_persistence(self, tmp_path, monkeypatch):
        key_file = str(tmp_path / ".encryption_key")
        monkeypatch.setattr("utils.crypto.DATA_DIR", str(tmp_path))
        monkeypatch.setattr("utils.crypto._fernet_instance", None)
        monkeypatch.setattr("utils.crypto._KEY_FILE", key_file)

        from utils.crypto import encrypt
        encrypt("test")
        assert os.path.exists(key_file)
