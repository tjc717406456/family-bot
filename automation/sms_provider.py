"""豪猪接码平台 API 客户端

API 文档: https://www.showdoc.com.cn/haozhuma
流程: 登录(获取token) → 获取号码 → 轮询获取验证码 → 释放/拉黑号码
"""

import json
import logging
import os
import re
import time

import requests

logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "antigravity_config.json",
)

DEFAULT_API_URL = "https://api.haozhuma.com/sms/"


def _load_sms_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        return {}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


class HaozhumaProvider:
    """豪猪接码平台 HTTP API 封装"""

    def __init__(self, api_url=None, api_user=None, api_pass=None, project=None):
        cfg = _load_sms_config()
        self.api_url = api_url or cfg.get("haozhuma_api_url") or DEFAULT_API_URL
        self.api_user = api_user or cfg.get("haozhuma_api_user", "")
        self.api_pass = api_pass or cfg.get("haozhuma_api_pass", "")
        self.project = project or cfg.get("haozhuma_project", "")
        self.token: str | None = None

    # ------------------------------------------------------------------
    # 内部请求
    # ------------------------------------------------------------------
    def _get(self, params: dict) -> dict:
        try:
            resp = requests.get(self.api_url, params=params, timeout=15)
            try:
                data = resp.json()
            except Exception:
                logger.error("豪猪 API 响应非 JSON (HTTP %s): %s", resp.status_code, resp.text[:200])
                return {"code": -1, "msg": f"HTTP {resp.status_code}"}
            # API 返回的 code 有时是字符串 "0"，有时是整数 0，统一转 int
            if "code" in data:
                try:
                    data["code"] = int(data["code"])
                except (ValueError, TypeError):
                    pass
            return data
        except Exception as e:
            logger.error("豪猪 API 请求失败: %s", e)
            return {"code": -1, "msg": str(e)}

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------
    def login(self) -> bool:
        """登录获取 token（整个会话只需调用一次）"""
        if not self.api_user or not self.api_pass:
            logger.error("豪猪 API 账号或密码未配置")
            return False

        data = self._get({"api": "login", "user": self.api_user, "pass": self.api_pass})
        if data.get("code") == 0:
            self.token = data.get("token")
            logger.info("豪猪登录成功")
            return True

        logger.error("豪猪登录失败: %s", data.get("msg"))
        return False

    def get_account_info(self) -> dict:
        """查询账户余额等信息"""
        return self._get({"api": "getAccountInfo", "token": self.token})

    def get_phone(self, project: str | None = None,
                  operator: str = "", province: str = "") -> str | None:
        """获取一个可用号码

        Args:
            project:  项目 ID，如 ``28209-J42JKRWAAM``
            operator: 运营商代码（可选）
            province: 省份代码（可选）
        """
        params: dict = {
            "api": "getPhone",
            "token": self.token,
            "sid": project or self.project,
        }
        if operator:
            params["operator"] = operator
        if province:
            params["province"] = province

        data = self._get(params)
        if data.get("code") == 0:
            phone = data.get("phone") or data.get("mobile")
            logger.info("获取号码成功: %s", phone)
            return phone

        logger.error("获取号码失败: %s", data.get("msg"))
        return None

    def get_code(self, phone: str, project: str | None = None,
                 max_wait: int = 180, interval: int = 15) -> str | None:
        """轮询获取短信内容

        每 *interval* 秒查询一次，最多等待 *max_wait* 秒。
        返回完整短信文本；超时返回 ``None``。
        """
        sid = project or self.project
        elapsed = 0
        while elapsed < max_wait:
            data = self._get({
                "api": "getMessage",
                "token": self.token,
                "sid": sid,
                "phone": phone,
            })
            if data.get("code") == 0:
                sms = data.get("sms") or data.get("msg", "")
                logger.info("收到短信 [%s]: %s", phone, sms)
                return sms

            logger.debug("等待验证码 ... (%ds/%ds)", elapsed, max_wait)
            time.sleep(interval)
            elapsed += interval

        logger.warning("等待验证码超时 (%ds): %s", max_wait, phone)
        return None

    def release_phone(self, phone: str, project: str | None = None) -> bool:
        """释放号码（用完后调用）"""
        data = self._get({
            "api": "cancelRecv",
            "token": self.token,
            "sid": project or self.project,
            "phone": phone,
        })
        ok = data.get("code") == 0
        logger.info("释放号码 %s: %s", phone, "成功" if ok else data.get("msg"))
        return ok

    def blacklist_phone(self, phone: str, project: str | None = None) -> bool:
        """拉黑号码（收不到码时使用，避免再次取到）"""
        data = self._get({
            "api": "addBlacklist",
            "token": self.token,
            "sid": project or self.project,
            "phone": phone,
        })
        ok = data.get("code") == 0
        logger.info("拉黑号码 %s: %s", phone, "成功" if ok else data.get("msg"))
        return ok

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------
    @staticmethod
    def extract_code(sms_text: str) -> str | None:
        """从短信内容中提取验证码

        支持: G-123456、通用 6 位、4 位数字验证码
        """
        if not sms_text:
            return None
        # Google 格式: G-XXXXXX
        m = re.search(r"G-(\d{6})", sms_text)
        if m:
            return m.group(1)
        # 通用 6 位
        m = re.search(r"(?<!\d)(\d{6})(?!\d)", sms_text)
        if m:
            return m.group(1)
        # 4 位
        m = re.search(r"(?<!\d)(\d{4})(?!\d)", sms_text)
        if m:
            return m.group(1)
        return None


# ======================================================================
# 便捷函数 —— 一次调用完成「取号 → 收码 → 释放」全流程
# ======================================================================

def fetch_sms_code(project: str | None = None,
                   max_wait: int = 180) -> tuple[str | None, str | None, str | None, str | None]:
    """获取手机号并等待验证码

    Returns:
        ``(phone, code, sms_text, error)`` — 成功时 error 为 None
    """
    provider = HaozhumaProvider()
    if not provider.login():
        return None, None, None, "豪猪登录失败，请检查 API 配置"

    phone = provider.get_phone(project=project)
    if not phone:
        return None, None, None, "获取手机号失败"

    sms = provider.get_code(phone, project=project, max_wait=max_wait)
    if not sms:
        provider.blacklist_phone(phone, project=project)
        return phone, None, None, f"等待验证码超时，号码 {phone} 已拉黑"

    code = HaozhumaProvider.extract_code(sms)
    provider.release_phone(phone, project=project)
    return phone, code, sms, None
