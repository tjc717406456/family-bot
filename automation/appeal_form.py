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

APPEAL_FORM_URL = "https://forms.gle/hGzM9MEUv2azZsrb9"


async def open_appeal_form(member_id: int):
    """登录成员 Google 账号，自动填写并提交申诉表单"""
    with get_session() as session:
        member = session.get(Member, member_id)
        if not member:
            console.print(f"[red]成员 ID {member_id} 不存在[/red]")
            return False
        email = member.email
        password = decrypt_safe(member.password)
        totp_secret = decrypt_safe(member.totp_secret) if member.totp_secret else ""

    console.print(f"[cyan]认罪: 打开浏览器并登录 {email}[/cyan]")

    async with async_playwright() as p:
        context, page = await launch_member_context(p, member_id)
        await google_login(page, email, password, totp_secret)

        console.print(f"[cyan]登录完成，正在打开申诉表单: {email}[/cyan]")
        await page.goto(APPEAL_FORM_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)

        # 1) 点击 "Okay" 关闭 Autosave 弹窗
        try:
            okay_btn = page.get_by_role("button", name="Okay")
            await okay_btn.wait_for(state="visible", timeout=8000)
            await okay_btn.click()
            console.print(f"[cyan]已点击 Okay: {email}[/cyan]")
            await page.wait_for_timeout(1000)
        except Exception:
            console.print(f"[yellow]未出现 Autosave 弹窗，跳过: {email}[/yellow]")

        # 2) 勾选 "Record ... email" 复选框
        try:
            record_checkbox = page.locator("label").filter(has_text="Record").first
            await record_checkbox.click()
            console.print(f"[cyan]已勾选 Record email: {email}[/cyan]")
            await page.wait_for_timeout(500)
        except Exception as e:
            logger.warning("勾选 Record email 失败: %s - %s", email, e)

        # 3) 选择 "Yes, I understand" 单选按钮
        try:
            yes_option = page.locator("label").filter(has_text="Yes, I understand").first
            await yes_option.click()
            console.print(f"[cyan]已选择 Yes, I understand: {email}[/cyan]")
            await page.wait_for_timeout(500)
        except Exception as e:
            logger.warning("选择 Yes, I understand 失败: %s - %s", email, e)

        # 4) 点击 Submit
        try:
            submit_btn = page.get_by_role("button", name="Submit")
            await submit_btn.click()
            console.print(f"[cyan]已点击 Submit: {email}[/cyan]")
            await page.wait_for_timeout(3000)
        except Exception as e:
            logger.warning("点击 Submit 失败: %s - %s", email, e)

        # 5) 确认提交成功
        try:
            await page.wait_for_selector("text=Thanks", timeout=10000)
            console.print(f"[green]认罪提交成功: {email}[/green]")
        except Exception:
            console.print(f"[yellow]未检测到成功页面，可能提交失败: {email}[/yellow]")

        await context.close()

    return True
