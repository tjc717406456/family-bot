import logging

from playwright.async_api import async_playwright
from rich.console import Console

from automation.browser import launch_member_context
from automation.google_login import google_login
from db.database import get_session
from db.models import Member
from utils.crypto import decrypt_safe

console = Console()
logger = logging.getLogger(__name__)


async def open_browser_for_member(member_id: int):
    """启动成员独立 Chrome，自动登录 Google，等待用户手动关闭浏览器"""
    with get_session() as session:
        member = session.get(Member, member_id)
        if not member:
            console.print(f"[red]成员 ID {member_id} 不存在[/red]")
            return False
        email = member.email
        password = decrypt_safe(member.password)
        totp_secret = decrypt_safe(member.totp_secret) if member.totp_secret else ""

    console.print(f"[cyan]打开浏览器: {email}[/cyan]")

    async with async_playwright() as p:
        context, page = await launch_member_context(p, member_id)
        await google_login(page, email, password, totp_secret)
        console.print(f"[green]浏览器已就绪，等待用户关闭: {email}[/green]")
        await context.wait_for_event("close", timeout=0)

    return True
