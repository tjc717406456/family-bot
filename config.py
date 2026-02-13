import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "family_bot.db")
SCREENSHOT_DIR = os.path.join(DATA_DIR, "screenshots")

DATABASE_URL = f"sqlite:///{DB_PATH}"

# 浏览器配置
BROWSER_HEADLESS = False
BROWSER_SLOW_MO = 500  # 毫秒，放慢操作便于观察
BROWSER_CHANNEL = "chrome"  # 使用本机 Google Chrome
BROWSER_USER_DATA_DIR = os.path.join(DATA_DIR, "chrome_profiles")  # 保存浏览器登录状态

# 超时配置（秒）
PAGE_LOAD_TIMEOUT = 30000
LOGIN_TIMEOUT = 60000
NAVIGATION_TIMEOUT = 30000

# Google 相关 URL
GOOGLE_SIGNIN_URL = "https://accounts.google.com/signin"
GEMINI_URL = "https://gemini.google.com/gems/create?hl=en-US&pli=1"
GMAIL_URL = "https://mail.google.com/"

# 确保目录存在
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(SCREENSHOT_DIR, exist_ok=True)
