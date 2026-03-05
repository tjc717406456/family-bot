import logging
import os

from playwright.async_api import async_playwright
from rich.console import Console

from config import (
    BROWSER_CHANNEL, BROWSER_HEADLESS, BROWSER_SLOW_MO, BROWSER_USER_DATA_DIR,
)
from automation.google_login import google_login
from db.database import get_session
from db.models import Member

console = Console()
logger = logging.getLogger(__name__)


async def open_browser_for_member(member_id: int):
    """启动成员独立 Chrome，自动登录 Google，等待用户手动关闭浏览器"""
    with get_session() as session:
        member = session.get(Member, member_id)
        if not member:
            console.print(f"[red]成员 ID {member_id} 不存在[/red]")
            return False
        email, password, totp_secret = member.email, member.password, member.totp_secret or ""

    profile_dir = os.path.join(BROWSER_USER_DATA_DIR, f"member_{member_id}")
    os.makedirs(profile_dir, exist_ok=True)

    console.print(f"[cyan]打开浏览器: {email}[/cyan]")

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
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
        await google_login(page, email, password, totp_secret)
        console.print(f"[green]浏览器已就绪，等待用户关闭: {email}[/green]")
        await context.wait_for_event("close", timeout=0)

    return True
