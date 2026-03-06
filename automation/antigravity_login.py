import logging
from datetime import datetime

import pyotp
from playwright.async_api import async_playwright
from rich.console import Console

from db.database import get_session
from db.models import Member
from automation.browser import launch_member_context
from automation.wait_utils import wait_for_url_change
from automation.utils import take_screenshot, mark_error

console = Console()
logger = logging.getLogger(__name__)


async def antigravity_login(member_id: int, oauth_url: str) -> bool:
    """
    Antigravity OAuth 登录：
    打开 OAuth 链接 → 选 Google 账号 → 处理 2FA → 点 Sign in → 取回调 URL 写入 remark
    """
    with get_session() as session:
        member = session.get(Member, member_id)
        if not member:
            logger.error("成员 ID %s 不存在", member_id)
            return False

        console.print(f"\n[bold cyan]===== Antigravity 登录: {member.email} =====[/bold cyan]")
        logger.info("Antigravity 登录开始: %s, OAuth: %s", member.email, oauth_url[:120])

        async with async_playwright() as p:
            context, page = await launch_member_context(p, member.id)

            try:
                console.print("[dim]打开 OAuth 链接...[/dim]")
                await page.goto(oauth_url, wait_until="domcontentloaded", timeout=60000)
                try:
                    await page.wait_for_load_state("networkidle", timeout=8000)
                except Exception:
                    pass

                callback_url = await _handle_oauth_flow(page, member)
                if not callback_url:
                    mark_error(session, member, "OAuth 流程未完成")
                    await take_screenshot(page, member, "oauth_failed")
                    return False

                logger.info("获取到回调 URL: %s", callback_url[:120])

                try:
                    from automation.oauth_utils import process_callback
                    result = process_callback(callback_url)

                    member.remark = f"已提交API: {result.get('api_result', '')}"
                    console.print(f"[bold green]===== {member.email} Antigravity 授权+上传 全部完成 =====[/bold green]\n")
                except Exception as e:
                    logger.warning("提交回调失败: %s, 回调 URL 已保存", e)
                    console.print(f"[yellow]提交失败: {e}，回调 URL 已保存到 remark[/yellow]")
                    member.remark = callback_url

                member.updated_at = datetime.now()
                session.commit()
                return True

            except Exception as e:
                mark_error(session, member, str(e))
                await take_screenshot(page, member, "antigravity_exception")
                logger.exception("Antigravity 登录异常: %s", member.email)
                return False
            finally:
                await context.close()


async def _handle_oauth_flow(page, member):
    """处理 OAuth 流程中可能出现的各种页面，返回捕获到的回调 URL 或 None"""
    captured_url = []

    def on_request(request):
        url = request.url
        if url.startswith("http://localhost") or url.startswith("https://localhost"):
            captured_url.append(url)
            logger.info("捕获到回调 URL: %s", url[:120])

    page.on("request", on_request)

    try:
        for attempt in range(20):
            await page.wait_for_timeout(1000)

            if captured_url:
                return captured_url[0]

            current_url = page.url
            console.print(f"[dim]当前页面: {current_url[:120]}[/dim]")

            if "chrome-error" in current_url:
                await page.wait_for_timeout(2000)
                if captured_url:
                    return captured_url[0]
                console.print("[dim]页面加载错误，等待...[/dim]")
                await page.wait_for_timeout(2000)
                continue

            if current_url.startswith("http://localhost") or current_url.startswith("https://localhost"):
                console.print("[green]已跳转到回调地址[/green]")
                return current_url

            if "accounts.youtube.com" in current_url or "accounts.google.com/SetSID" in current_url:
                console.print("[dim]中间跳转页面，等待自动跳转...[/dim]")
                await wait_for_url_change(page, current_url, timeout=8000)
                continue

            if "firstparty/nativeapp" in current_url or "signin/oauth/consent" in current_url or "oauth/consent" in current_url:
                console.print("[dim]检测到 OAuth 授权/确认页面[/dim]")
                allowed = await _click_allow(page)
                if not allowed:
                    allowed = await _click_sign_in(page)
                if allowed:
                    await wait_for_url_change(page, current_url, timeout=10000)
                    continue

            if await _handle_unverified_app_warning(page):
                await wait_for_url_change(page, current_url, timeout=8000)
                continue

            if await _is_choose_account_page(page):
                console.print(f"[dim]检测到选择账号页面，选择: {member.email}[/dim]")
                selected = await _select_account(page, member.email)
                if selected:
                    await wait_for_url_change(page, current_url, timeout=8000)
                    continue
                console.print("[dim]尝试在新登录页面输入凭据...[/dim]")
                await _handle_login_form(page, member)
                await wait_for_url_change(page, current_url, timeout=10000)
                continue

            if member.totp_secret:
                totp_input = page.locator('input[type="tel"]')
                try:
                    if await totp_input.is_visible():
                        console.print("[dim]检测到 2FA 页面[/dim]")
                        await _handle_2fa(page, member.totp_secret)
                        await wait_for_url_change(page, current_url, timeout=8000)
                        continue
                except Exception:
                    pass

            signed_in = await _click_sign_in(page)
            if signed_in:
                console.print("[dim]已点击 Sign in，等待跳转...[/dim]")
                await wait_for_url_change(page, current_url, timeout=10000)
                continue

            console.print(f"[dim]等待页面变化 (第 {attempt + 1} 次)...[/dim]")
            await page.wait_for_timeout(3000)
    finally:
        page.remove_listener("request", on_request)

    logger.warning("OAuth 流程超时")
    return None


async def _handle_unverified_app_warning(page) -> bool:
    """处理 'Google hasn't verified this app' 未验证应用警告页面"""
    try:
        body_text = await page.locator("body").inner_text()
        body_lower = body_text.lower().replace("\u2019", "'").replace("\u2018", "'")
        warning_keywords = ["hasn't verified", "isn't verified", "unverified app", "this app isn't verified"]
        if not any(kw in body_lower for kw in warning_keywords):
            return False

        console.print("[dim]检测到未验证应用警告页面[/dim]")

        advanced_selectors = [
            '#details-button',
            'a:has-text("Advanced")',
            'a:has-text("高级")',
            'button:has-text("Advanced")',
            '[id="advanced-link"]',
        ]
        clicked_advanced = False
        for sel in advanced_selectors:
            try:
                el = page.locator(sel).first
                if await el.is_visible():
                    await el.click()
                    console.print(f"[dim]已点击 Advanced: {sel}[/dim]")
                    clicked_advanced = True
                    break
            except Exception:
                continue

        if not clicked_advanced:
            clicked_advanced = await page.evaluate('''() => {
                const links = document.querySelectorAll('a, button');
                for (const el of links) {
                    const text = (el.innerText || '').trim().toLowerCase();
                    if (text === 'advanced' || text === '高级' || text.includes('advanced')) {
                        el.click();
                        return true;
                    }
                }
                return false;
            }''')
            if clicked_advanced:
                console.print("[dim]已点击 Advanced(JS)[/dim]")

        if not clicked_advanced:
            console.print("[dim]未找到 Advanced 按钮[/dim]")
            return False

        await page.wait_for_timeout(1000)

        go_selectors = [
            'a:has-text("Go to")',
            'a:has-text("转到")',
            'a[id="proceed-link"]',
            '#proceed-link',
        ]
        for sel in go_selectors:
            try:
                el = page.locator(sel).first
                if await el.is_visible():
                    await el.click()
                    console.print(f"[dim]已点击 Go to (unsafe): {sel}[/dim]")
                    return True
            except Exception:
                continue

        clicked_go = await page.evaluate('''() => {
            const links = document.querySelectorAll('a');
            for (const el of links) {
                const text = (el.innerText || '').toLowerCase();
                if (text.includes('go to') || text.includes('转到') || text.includes('unsafe')) {
                    el.click();
                    return true;
                }
            }
            return false;
        }''')
        if clicked_go:
            console.print("[dim]已点击 Go to (unsafe)(JS)[/dim]")
            return True

        console.print("[dim]未找到 Go to (unsafe) 链接[/dim]")
        return False
    except Exception:
        return False


async def _is_choose_account_page(page) -> bool:
    """检测是否在 Choose an account 页面（排除已到确认页面的情况）"""
    try:
        for text in ["Sign in", "Cancel", "Allow"]:
            btn = page.locator(f'button:has-text("{text}")').first
            if await btn.is_visible():
                return False

        count = await page.locator('[data-identifier]').count()
        return count > 0
    except Exception:
        return False


async def _select_account(page, email: str) -> bool:
    """在 Choose an account 页面按 email 匹配点击，找不到则点击 Use another account"""
    for attr in ["data-identifier", "data-email"]:
        try:
            account = page.locator(f'[{attr}="{email}"]')
            if await account.count() > 0:
                await account.first.click()
                console.print(f"[dim]已选择账号({attr}): {email}[/dim]")
                return True
        except Exception:
            continue

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

    console.print(f"[yellow]账号列表中未找到 {email}，尝试点击 Use another account...[/yellow]")
    if await _click_use_another_account(page):
        return True

    console.print(f"[red]未找到账号且无法切换: {email}[/red]")
    return False


async def _click_use_another_account(page) -> bool:
    """点击 'Use another account' 按钮进入登录页面"""
    selectors = [
        'li[data-identifier=""]',
        '[data-identifier=""]',
        'div:has-text("Use another account")',
        'div:has-text("使用其他帐号")',
        'div:has-text("使用其他账号")',
    ]
    for sel in selectors:
        try:
            el = page.locator(sel).first
            if await el.is_visible():
                await el.click()
                console.print("[dim]已点击 Use another account[/dim]")
                return True
        except Exception:
            continue

    try:
        clicked = await page.evaluate('''() => {
            const items = document.querySelectorAll('li, div[role="link"], div[tabindex]');
            for (const el of items) {
                const text = (el.innerText || '').toLowerCase();
                if (text.includes('use another account') || text.includes('使用其他帐号') || text.includes('使用其他账号')) {
                    el.click();
                    return true;
                }
            }
            return false;
        }''')
        if clicked:
            console.print("[dim]已点击 Use another account(JS)[/dim]")
            return True
    except Exception:
        pass

    return False


async def _handle_login_form(page, member):
    """在 OAuth 流程中处理 Google 登录表单（输入邮箱、密码）"""
    from utils.crypto import decrypt_safe

    try:
        email_input = page.locator('input[type="email"]')
        await email_input.wait_for(state="visible", timeout=8000)
        await email_input.fill(member.email)
        console.print(f"[dim]已填入邮箱: {member.email}[/dim]")

        await page.locator("#identifierNext").click()

        password_input = page.locator('input[name="Passwd"]')
        await password_input.wait_for(state="visible", timeout=10000)
        plain_pwd = decrypt_safe(member.password) if member.password else ""
        await password_input.fill(plain_pwd)
        console.print("[dim]已填入密码[/dim]")

        old_url = page.url
        await page.locator("#passwordNext").click()
        await wait_for_url_change(page, old_url, timeout=10000)
    except Exception:
        logger.warning("OAuth 登录表单处理失败", exc_info=True)


async def _handle_2fa(page, totp_secret: str):
    """处理 Google 2FA 验证码输入"""
    try:
        totp_input = page.locator('input[type="tel"]')
        if await totp_input.is_visible():
            totp = pyotp.TOTP(totp_secret)
            code = totp.now()
            logger.debug("生成 TOTP 验证码")
            old_url = page.url
            await totp_input.fill(code)
            try:
                await page.locator("#totpNext").click(no_wait_after=True)
            except Exception:
                logger.debug("totpNext 点击后页面已导航，视为成功")
            await wait_for_url_change(page, old_url, timeout=10000)
    except Exception:
        logger.warning("2FA 处理失败", exc_info=True)


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
