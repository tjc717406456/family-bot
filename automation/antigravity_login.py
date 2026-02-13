import os
from datetime import datetime

import pyotp
from playwright.async_api import async_playwright
from rich.console import Console

from config import (
    BROWSER_HEADLESS, BROWSER_SLOW_MO, BROWSER_CHANNEL,
    BROWSER_USER_DATA_DIR, SCREENSHOT_DIR,
)
from db.database import get_session
from db.models import Member

console = Console()


async def antigravity_login(member_id: int, oauth_url: str) -> bool:
    """
    Antigravity OAuth 登录：
    打开 OAuth 链接 → 选 Google 账号 → 处理 2FA → 点 Sign in → 取回调 URL 写入 remark
    """
    session = get_session()
    try:
        member = session.query(Member).get(member_id)
        if not member:
            console.print(f"[red]成员 ID {member_id} 不存在[/red]")
            return False

        console.print(f"\n[bold cyan]===== Antigravity 登录: {member.email} =====[/bold cyan]")
        console.print(f"[dim]OAuth 地址: {oauth_url}[/dim]")

        async with async_playwright() as p:
            member_profile_dir = os.path.join(BROWSER_USER_DATA_DIR, f"member_{member.id}")
            os.makedirs(member_profile_dir, exist_ok=True)

            context = await p.chromium.launch_persistent_context(
                user_data_dir=member_profile_dir,
                headless=BROWSER_HEADLESS,
                slow_mo=BROWSER_SLOW_MO,
                channel=BROWSER_CHANNEL,
                viewport={"width": 1280, "height": 800},
                locale="en-US",
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                    "--no-first-run",
                ],
            )
            page = context.pages[0] if context.pages else await context.new_page()

            try:
                # Step 1: 打开 OAuth 链接
                console.print("[dim]打开 OAuth 链接...[/dim]")
                await page.goto(oauth_url, wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_timeout(5000)

                # Step 2: 检测当前页面状态，按情况处理
                callback_url = await _handle_oauth_flow(page, member)
                if not callback_url:
                    _mark_error(session, member, "OAuth 流程未完成")
                    await _screenshot(page, member, "oauth_failed")
                    return False

                # Step 3: 写入 remark
                console.print(f"[dim]回调 URL: {callback_url[:120]}[/dim]")
                member.remark = callback_url
                member.updated_at = datetime.now()
                session.commit()
                console.print(f"[bold green]===== {member.email} Antigravity 登录完成 =====[/bold green]\n")
                return True

            except Exception as e:
                _mark_error(session, member, str(e))
                await _screenshot(page, member, "antigravity_exception")
                console.print(f"[red]异常: {e}[/red]")
                return False
            finally:
                await context.close()
    finally:
        session.close()


async def _handle_oauth_flow(page, member):
    """处理 OAuth 流程中可能出现的各种页面，返回捕获到的回调 URL 或 None"""
    # 用列表存储捕获到的 localhost 回调 URL
    captured_url = []

    def on_request(request):
        url = request.url
        if url.startswith("http://localhost") or url.startswith("https://localhost"):
            captured_url.append(url)
            console.print(f"[green]捕获到回调 URL: {url[:120]}[/green]")

    page.on("request", on_request)

    try:
        for attempt in range(20):
            await page.wait_for_timeout(3000)

            # 检查是否已捕获回调 URL
            if captured_url:
                return captured_url[0]

            current_url = page.url
            console.print(f"[dim]当前页面: {current_url[:120]}[/dim]")

            # chrome-error 说明跳转到了无法访问的地址，检查是否已捕获
            if "chrome-error" in current_url:
                if captured_url:
                    return captured_url[0]
                await page.wait_for_timeout(3000)
                if captured_url:
                    return captured_url[0]
                console.print("[dim]页面加载错误，等待...[/dim]")
                await page.wait_for_timeout(5000)
                continue

            # 已跳转到 localhost 回调，流程完成
            if current_url.startswith("http://localhost") or current_url.startswith("https://localhost"):
                console.print("[green]已跳转到回调地址[/green]")
                return current_url

            # Google 内部中间跳转页（SetSID 等），等它自动跳转完
            if "accounts.youtube.com" in current_url or "accounts.google.com/SetSID" in current_url:
                console.print("[dim]中间跳转页面，等待自动跳转...[/dim]")
                await page.wait_for_timeout(5000)
                continue

            # OAuth consent 授权确认页面，点 Allow
            if "signin/oauth/consent" in current_url or "oauth/consent" in current_url:
                console.print("[dim]检测到 OAuth 授权确认页面[/dim]")
                await page.wait_for_timeout(3000)
                allowed = await _click_allow(page)
                if allowed:
                    await page.wait_for_timeout(10000)
                    continue

            # "Choose an account" 页面
            if await _is_choose_account_page(page):
                console.print(f"[dim]检测到选择账号页面，选择: {member.email}[/dim]")
                await page.wait_for_timeout(3000)
                selected = await _select_account(page, member.email)
                if not selected:
                    console.print(f"[red]未找到账号: {member.email}[/red]")
                    return None
                await page.wait_for_timeout(5000)
                continue

            # 2FA 页面
            if member.totp_secret:
                totp_input = page.locator('input[type="tel"]')
                try:
                    if await totp_input.is_visible():
                        console.print("[dim]检测到 2FA 页面[/dim]")
                        await page.wait_for_timeout(3000)
                        await _handle_2fa(page, member.totp_secret)
                        await page.wait_for_timeout(5000)
                        continue
                except Exception:
                    pass

            # "Make sure you downloaded this app" / Sign in 页面
            await page.wait_for_timeout(3000)
            signed_in = await _click_sign_in(page)
            if signed_in:
                console.print("[dim]已点击 Sign in，等待跳转...[/dim]")
                await page.wait_for_timeout(10000)
                continue

            # 都不是，等一会再检测
            console.print(f"[dim]等待页面变化 (第 {attempt + 1} 次)...[/dim]")
            await page.wait_for_timeout(5000)
    finally:
        page.remove_listener("request", on_request)

    console.print("[yellow]OAuth 流程超时[/yellow]")
    return None


async def _is_choose_account_page(page) -> bool:
    """检测是否在 Choose an account 页面（排除已到确认页面的情况）"""
    try:
        # 如果页面上有 Sign in / Cancel 按钮，说明是确认页面，不是选账号页面
        for text in ["Sign in", "Cancel", "Allow"]:
            btn = page.locator(f'button:has-text("{text}")').first
            if await btn.is_visible():
                return False

        # 有多个 data-identifier 才是选账号页面（确认页面只有一个 data-email）
        count = await page.locator('[data-identifier]').count()
        if count > 0:
            return True

        return False
    except Exception:
        return False


async def _select_account(page, email: str) -> bool:
    """在 Choose an account 页面按 email 匹配点击"""
    # 用 data-identifier 精准匹配（Google 账号选择页面标准属性）
    try:
        account = page.locator(f'[data-identifier="{email}"]')
        if await account.count() > 0:
            await account.first.click()
            console.print(f"[dim]已选择账号(data-identifier): {email}[/dim]")
            return True
    except Exception:
        pass

    # data-email 匹配
    try:
        account = page.locator(f'[data-email="{email}"]')
        if await account.count() > 0:
            await account.first.click()
            console.print(f"[dim]已选择账号(data-email): {email}[/dim]")
            return True
    except Exception:
        pass

    # JS 兜底
    try:
        clicked = await page.evaluate('''(email) => {
            const els = document.querySelectorAll('[data-identifier], [data-email]');
            for (const el of els) {
                const addr = (el.getAttribute('data-identifier') || el.getAttribute('data-email') || '').toLowerCase();
                if (addr === email.toLowerCase()) {
                    el.click();
                    return true;
                }
            }
            return false;
        }''', email)
        if clicked:
            console.print(f"[dim]已选择账号(JS): {email}[/dim]")
            return True
    except Exception:
        pass

    console.print(f"[red]未找到账号: {email}[/red]")
    return False


async def _handle_2fa(page, totp_secret: str):
    """处理 Google 2FA 验证码输入"""
    try:
        totp_input = page.locator('input[type="tel"]')
        if await totp_input.is_visible():
            totp = pyotp.TOTP(totp_secret)
            code = totp.now()
            console.print(f"[dim]生成 TOTP 验证码: {code}[/dim]")
            await totp_input.fill(code)
            await page.locator("#totpNext").click()
            await page.wait_for_timeout(5000)
    except Exception:
        console.print("[dim]2FA 处理失败，跳过[/dim]")


async def _click_sign_in(page) -> bool:
    """点击 Sign in 按钮"""
    sign_in_selectors = [
        'button:has-text("Sign in")',
        'a:has-text("Sign in")',
        'input[type="submit"][value="Sign in"]',
        'button:has-text("Continue")',
        'button:has-text("继续")',
        'button:has-text("登录")',
    ]
    for sel in sign_in_selectors:
        try:
            btn = page.locator(sel).first
            if await btn.is_visible():
                console.print(f"[dim]点击: {sel}[/dim]")
                await btn.click()
                return True
        except Exception:
            continue
    return False


async def _click_allow(page) -> bool:
    """点击 OAuth 授权确认页面的 Allow/Continue 按钮"""
    allow_selectors = [
        'button:has-text("Allow")',
        'button:has-text("Continue")',
        'button:has-text("允许")',
        'button:has-text("继续")',
        '#submit_approve_access',
        'button[id="submit_approve_access"]',
        'input[id="submit_approve_access"]',
    ]
    for sel in allow_selectors:
        try:
            btn = page.locator(sel).first
            if await btn.is_visible():
                console.print(f"[dim]点击授权: {sel}[/dim]")
                await btn.click()
                return True
        except Exception:
            continue

    # JS 兜底：找所有 button/input 里包含 Allow/Continue 文本的
    try:
        clicked = await page.evaluate('''() => {
            const btns = document.querySelectorAll('button, input[type="submit"], input[type="button"]');
            for (const btn of btns) {
                const text = (btn.innerText || btn.value || '').toLowerCase();
                if (text.includes('allow') || text.includes('continue') || text.includes('允许')) {
                    btn.click();
                    return true;
                }
            }
            return false;
        }''')
        if clicked:
            console.print("[dim]点击授权(JS)[/dim]")
            return True
    except Exception:
        pass

    console.print("[dim]未找到授权按钮[/dim]")
    return False


def _mark_error(session, member: Member, reason: str):
    member.error_msg = reason
    member.updated_at = datetime.now()
    session.commit()
    console.print(f"[red]Antigravity 失败: {member.email} - {reason}[/red]")


async def _screenshot(page, member: Member, tag: str):
    filename = f"{member.id}_{member.email}_ag_{tag}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    path = os.path.join(SCREENSHOT_DIR, filename)
    try:
        await page.screenshot(path=path)
        console.print(f"[dim]截图已保存: {path}[/dim]")
    except Exception:
        pass
