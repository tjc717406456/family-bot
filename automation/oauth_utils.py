import json
import logging
import os
import threading
from urllib.parse import urlparse, parse_qs

import requests

logger = logging.getLogger(__name__)

_config_cache = None
_config_lock = threading.Lock()


def _load_config():
    global _config_cache
    with _config_lock:
        if _config_cache is not None:
            return _config_cache

        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "antigravity_config.json")
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"配置文件不存在: {config_path}")

        with open(config_path, "r", encoding="utf-8") as f:
            _config_cache = json.load(f)
        return _config_cache


def reload_config():
    """清除配置缓存，下次调用 _load_config 时重新读取文件"""
    global _config_cache
    with _config_lock:
        _config_cache = None


def _extract_oauth_url(data) -> str:
    """从 API 返回数据中提取 OAuth URL（公共逻辑）"""
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        url = data.get("url") or data.get("authUrl") or data.get("oauth_url") or data.get("auth_url")
        if not url and "data" in data:
            inner = data["data"]
            if isinstance(inner, str):
                return inner
            if isinstance(inner, dict):
                url = inner.get("url") or inner.get("authUrl") or inner.get("oauth_url")
        return url or ""
    return ""


def _safe_json(resp) -> dict:
    """安全解析 JSON 响应，空响应视为成功"""
    if not resp.text or not resp.text.strip():
        return {"status": "ok", "message": "服务端返回空响应（已接受）"}
    try:
        return resp.json()
    except (ValueError, requests.exceptions.JSONDecodeError):
        raise RuntimeError(f"API 返回非 JSON 内容: {resp.text[:200]}")


def generate_oauth_url() -> str:
    """根据 service_type 从对应 API 获取 OAuth 授权链接"""
    cfg = _load_config()
    service_type = cfg.get("service_type", "antigravity_manager")

    if service_type == "gcli2api":
        return _generate_oauth_url_gcli2api(cfg)
    else:
        return _generate_oauth_url_antigravity(cfg)


def _generate_oauth_url_antigravity(cfg: dict) -> str:
    """从 Antigravity Manager API 获取 OAuth 授权链接"""
    api_url = cfg.get("antigravity_api_url", "").rstrip("/")
    api_key = cfg.get("antigravity_api_key", "")

    if not api_url:
        raise RuntimeError("未配置 antigravity_api_url")

    url = f"{api_url}/api/auth/url"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "x-api-key": api_key,
    }

    logger.info("请求 OAuth 链接: %s", url)
    resp = requests.get(url, headers=headers, timeout=15)

    if resp.status_code != 200:
        raise RuntimeError(f"获取 OAuth 链接失败 ({resp.status_code}): {resp.text}")

    data = _safe_json(resp)
    oauth_url = _extract_oauth_url(data)

    if not oauth_url:
        raise RuntimeError(f"API 返回中未找到 OAuth 链接: {data}")

    logger.info("获取到 OAuth 链接: %s", oauth_url[:120])
    return oauth_url


def _generate_oauth_url_gcli2api(cfg: dict) -> str:
    """从 gcli2api 获取 OAuth 授权链接"""
    api_url = cfg.get("gcli2api_url", "").rstrip("/")
    api_key = cfg.get("gcli2api_api_key", "")

    if not api_url:
        raise RuntimeError("未配置 gcli2api_url")

    url = f"{api_url}/auth/start"
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {"mode": "antigravity"}

    logger.info("请求 gcli2api OAuth 链接: %s", url)
    resp = requests.post(url, json=payload, headers=headers, timeout=15)

    if resp.status_code != 200:
        raise RuntimeError(f"gcli2api 获取 OAuth 链接失败 ({resp.status_code}): {resp.text}")

    data = _safe_json(resp)
    oauth_url = _extract_oauth_url(data)

    if not oauth_url:
        raise RuntimeError(f"gcli2api 返回中未找到 OAuth 链接: {data}")

    logger.info("获取到 OAuth 链接: %s", oauth_url[:120])
    return oauth_url


def submit_code_to_api(callback_url: str) -> dict:
    """根据 service_type 将回调 URL 提交给对应 API"""
    cfg = _load_config()
    service_type = cfg.get("service_type", "antigravity_manager")

    if service_type == "gcli2api":
        return _submit_code_gcli2api(cfg, callback_url)
    else:
        return _submit_code_antigravity(cfg, callback_url)


def _submit_code_antigravity(cfg: dict, callback_url: str) -> dict:
    """将回调 URL 提交给 Antigravity Manager API"""
    api_url = cfg.get("antigravity_api_url", "").rstrip("/")
    api_key = cfg.get("antigravity_api_key", "")

    if not api_url:
        raise RuntimeError("未配置 antigravity_api_url")

    submit_url = f"{api_url}/api/accounts/oauth/submit-code"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "x-api-key": api_key,
    }
    payload = {
        "code": callback_url,
    }

    logger.info("提交回调到 API: %s", submit_url)
    resp = requests.post(submit_url, json=payload, headers=headers, timeout=30)

    if resp.status_code not in (200, 201):
        raise RuntimeError(f"submit-code 失败 ({resp.status_code}): {resp.text}")

    result = _safe_json(resp)
    logger.info("API 处理成功: %s", result)
    return result


def _submit_code_gcli2api(cfg: dict, callback_url: str) -> dict:
    """将回调 URL 提交给 gcli2api"""
    api_url = cfg.get("gcli2api_url", "").rstrip("/")
    api_key = cfg.get("gcli2api_api_key", "")

    if not api_url:
        raise RuntimeError("未配置 gcli2api_url")

    submit_url = f"{api_url}/auth/callback-url"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "callback_url": callback_url,
        "mode": "antigravity",
    }

    logger.info("提交回调到 gcli2api: %s", submit_url)
    resp = requests.post(submit_url, json=payload, headers=headers, timeout=30)

    if resp.status_code not in (200, 201):
        raise RuntimeError(f"gcli2api callback-url 失败 ({resp.status_code}): {resp.text}")

    result = _safe_json(resp)
    logger.info("gcli2api 处理成功: %s", result)
    return result


def process_callback(callback_url: str) -> dict:
    """完整处理回调 URL：提交给 API 一步完成换票+上传"""
    parsed = urlparse(callback_url)
    qs = parse_qs(parsed.query)
    code = qs.get("code", [None])[0]

    if not code:
        raise RuntimeError(f"回调 URL 中没有 code 参数: {callback_url}")

    api_result = submit_code_to_api(callback_url)

    return {
        "uploaded": True,
        "api_result": api_result,
    }
