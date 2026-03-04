import json
import os
from urllib.parse import urlparse, parse_qs

import requests
from rich.console import Console

console = Console()

_config_cache = None


def _load_config():
    global _config_cache
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
    _config_cache = None


def generate_oauth_url() -> str:
    """从 Antigravity Manager API 获取 OAuth 授权链接"""
    cfg = _load_config()
    api_url = cfg.get("antigravity_api_url", "").rstrip("/")
    api_key = cfg.get("antigravity_api_key", "")

    if not api_url:
        raise RuntimeError("未配置 antigravity_api_url")

    url = f"{api_url}/api/auth/url"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "x-api-key": api_key,
    }

    console.print(f"[dim]请求 OAuth 链接: {url}[/dim]")
    resp = requests.get(url, headers=headers, timeout=15)

    if resp.status_code != 200:
        raise RuntimeError(f"获取 OAuth 链接失败 ({resp.status_code}): {resp.text}")

    data = resp.json()

    oauth_url = None
    if isinstance(data, str):
        oauth_url = data
    elif isinstance(data, dict):
        oauth_url = data.get("url") or data.get("authUrl") or data.get("oauth_url")
        if not oauth_url and "data" in data:
            inner = data["data"]
            if isinstance(inner, str):
                oauth_url = inner
            elif isinstance(inner, dict):
                oauth_url = inner.get("url") or inner.get("authUrl") or inner.get("oauth_url")

    if not oauth_url:
        raise RuntimeError(f"API 返回中未找到 OAuth 链接: {data}")

    console.print(f"[dim]获取到 OAuth 链接: {oauth_url[:120]}[/dim]")
    return oauth_url


def submit_code_to_api(callback_url: str) -> dict:
    """将回调 URL 直接提交给 Antigravity API，由服务端完成换票+上传"""
    cfg = _load_config()
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
        "state": None,
    }

    console.print(f"[dim]提交回调到 API: {submit_url}[/dim]")
    resp = requests.post(submit_url, json=payload, headers=headers, timeout=30)

    if resp.status_code not in (200, 201):
        raise RuntimeError(f"submit-code 失败 ({resp.status_code}): {resp.text}")

    result = resp.json()
    console.print(f"[green]API 处理成功: {result}[/green]")
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
