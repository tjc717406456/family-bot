import logging

import pyotp
from playwright.async_api import Page
from rich.console import Console
from config import GOOGLE_SIGNIN_URL, LOGIN_TIMEOUT
from automation.wait_utils import (
    wait_for_networkidle, wait_for_url_change,
    click_and_wait_hidden, click_and_wait_nav,
)

console = Console()
logger = logging.getLogger(__name__)


async def google_login(page: Page, email: str, password: str, totp_secret: str = "") -> bool:
    """
    Google 账号登录，支持 TOTP 自动验证
    每个成员用独立 Chrome profile，不存在账号冲突
    """
    console.print(f"[cyan]开始登录: {email}[/cyan]")
    logger.info("Google 登录开始: %s", email)

    await page.goto(GOOGLE_SIGNIN_URL, wait_until="domcontentloaded", timeout=60000)
    await wait_for_networkidle(page, timeout=8000)

    current_url = page.url
    if "accounts.google.com/signin" not in current_url and "accounts.google.com/v3/signin" not in current_url:
        console.print(f"[green]已有登录态，跳过登录: {email}[/green]")
        return True

    try:
        email_input = page.locator('input[type="email"]')
        await email_input.wait_for(state="visible", timeout=10000)
        await email_input.fill(email)
        console.print(f"[dim]已填入邮箱: {email}[/dim]")
    except Exception:
        # 检查当前 URL 确认是否真的已登录
        if "accounts.google.com/signin" not in page.url:
            console.print(f"[green]已有登录态，跳过登录: {email}[/green]")
            return True
        logger.warning("邮箱输入框未找到且未确认登录态: %s", page.url)
        return False

    await page.locator("#identifierNext").click()

    password_input = page.locator('input[name="Passwd"]')
    await password_input.wait_for(state="visible", timeout=LOGIN_TIMEOUT)
    await password_input.fill(password)
    console.print("[dim]已填入密码[/dim]")

    old_url = page.url
    await page.locator("#passwordNext").click()

    if totp_secret:
        totp_input = page.locator('input[type="tel"]')
        try:
            await totp_input.wait_for(state="visible", timeout=8000)
            totp = pyotp.TOTP(totp_secret)
            code = totp.now()
            logger.debug("生成 TOTP 验证码")
            await totp_input.fill(code)
            await click_and_wait_nav(page, page.locator("#totpNext"), timeout=8000)
        except Exception:
            console.print("[dim]未检测到 2FA 页面，跳过[/dim]")
    else:
        await wait_for_url_change(page, old_url, timeout=8000)

    # 跳过 Passkey 注册页面
    try:
        not_now_btn = page.locator('button:has-text("Not now")').or_(
            page.locator('button:has-text("以后再说")')
        )
        await not_now_btn.wait_for(state="visible", timeout=3000)
        await click_and_wait_hidden(page, not_now_btn, timeout=3000)
        console.print("[dim]跳过 Passkey 注册页面[/dim]")
    except Exception:
        pass

    # 处理 Chrome "Turn on sync?" 弹窗
    try:
        sync_btn = page.locator('button:has-text("Continue")').or_(
            page.locator('button:has-text("继续")').or_(
                page.locator('button:has-text("Yes, I\'m in")').or_(
                    page.locator('button:has-text("Turn on")')
                )
            )
        )
        await sync_btn.first.wait_for(state="visible", timeout=3000)
        await click_and_wait_hidden(page, sync_btn.first, timeout=3000)
        console.print("[dim]确认 Chrome 同步账号[/dim]")
    except Exception:
        pass

    # 验证登录结果
    try:
        await page.wait_for_url("**/myaccount.google.com/**", timeout=LOGIN_TIMEOUT)
        console.print(f"[green]登录成功: {email}[/green]")
        return True
    except Exception:
        current_url = page.url
        if "accounts.google.com/signin" not in current_url:
            console.print(f"[green]登录成功: {email} (当前页面: {current_url})[/green]")
            return True
        logger.warning("登录可能失败: %s, 当前页面: %s", email, current_url)
        return False
