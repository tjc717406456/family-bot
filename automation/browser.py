"""
公共浏览器上下文创建 — 消除 open_browser / auto_cmd / antigravity_login 中的重复代码
"""

import os

from config import (
    BROWSER_CHANNEL, BROWSER_HEADLESS, BROWSER_SLOW_MO, BROWSER_USER_DATA_DIR,
)


async def launch_member_context(playwright, member_id):
    """
    为指定成员启动独立 Chrome Profile 的持久化浏览器上下文。

    返回 (context, page) 元组。调用方负责关闭 context。
    """
    profile_dir = os.path.join(BROWSER_USER_DATA_DIR, f"member_{member_id}")
    os.makedirs(profile_dir, exist_ok=True)

    context = await playwright.chromium.launch_persistent_context(
        user_data_dir=profile_dir,
        headless=BROWSER_HEADLESS,
        slow_mo=BROWSER_SLOW_MO,
        channel=BROWSER_CHANNEL,
        viewport={"width": 1280, "height": 800},
        locale="en-US",
        args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--no-first-run",
        ],
    )
    page = context.pages[0] if context.pages else await context.new_page()
    return context, page
