import os
import logging

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "family_bot.db")
SCREENSHOT_DIR = os.path.join(DATA_DIR, "screenshots")

DATABASE_URL = f"sqlite:///{DB_PATH}"

# 浏览器配置
BROWSER_HEADLESS = os.environ.get("BROWSER_HEADLESS", "false").lower() in ("true", "1", "yes")
BROWSER_SLOW_MO = int(os.environ.get("BROWSER_SLOW_MO", "500"))
BROWSER_CHANNEL = os.environ.get("BROWSER_CHANNEL", "chrome")
BROWSER_USER_DATA_DIR = os.path.join(DATA_DIR, "chrome_profiles")

# 超时配置（毫秒，Playwright 使用毫秒单位）
LOGIN_TIMEOUT = 60000

# Google 相关 URL
GOOGLE_SIGNIN_URL = "https://accounts.google.com/signin"
GEMINI_URL = "https://gemini.google.com/gems/create?hl=en-US&pli=1"
GMAIL_URL = "https://mail.google.com/"

# Web 认证配置（设置密码后启用 Basic Auth）
WEB_AUTH_USERNAME = os.environ.get("WEB_AUTH_USERNAME", "admin")
WEB_AUTH_PASSWORD = os.environ.get("WEB_AUTH_PASSWORD", "")

# 并发任务上限
MAX_CONCURRENT_TASKS = int(os.environ.get("MAX_CONCURRENT_TASKS", "5"))

# Web 服务配置
WEB_DEBUG = os.environ.get("WEB_DEBUG", "false").lower() in ("true", "1", "yes")
WEB_HOST = os.environ.get("WEB_HOST", "127.0.0.1")
WEB_PORT = int(os.environ.get("WEB_PORT", "5000"))

# 日志配置
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()


def setup_logging():
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


# 确保目录存在
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(SCREENSHOT_DIR, exist_ok=True)
