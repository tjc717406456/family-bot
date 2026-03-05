import logging

from playwright.async_api import Page
from rich.console import Console
from config import GMAIL_URL
from automation.wait_utils import wait_for_url_change

console = Console()
logger = logging.getLogger(__name__)


async def accept_family_invite(page: Page) -> bool:
    """
    在 Gmail 中找到家庭组邀请邮件并接受
    返回 True 表示加入成功
    """
    console.print("[cyan]开始处理家庭组邀请[/cyan]")
    logger.info("开始查找家庭组邀请: %s", GMAIL_URL)

    await page.goto(GMAIL_URL, wait_until="domcontentloaded", timeout=60000)

    search_input = page.locator('input[aria-label="搜索邮件"], input[aria-label="Search mail"]').first
    try:
        await search_input.wait_for(state="visible", timeout=20000)
        console.print("[dim]Gmail 搜索框已就绪[/dim]")
    except Exception:
        logger.warning("Gmail 搜索框未出现，尝试继续")

    await _dismiss_gmail_popups(page)

    search_queries = [
        "Join family group?",
        "wants you to join",
        "family group invitation",
        "Join family group",
    ]

    result_indicator = page.locator('tr.zA, tr.zE, td:has-text("No messages matched")')

    mail_found = False
    for query in search_queries:
        console.print(f"[dim]搜索邮件: {query}[/dim]")
        try:
            await search_input.click()
            await search_input.fill("")
            await search_input.fill(query)
            await page.keyboard.press("Enter")

            try:
                await result_indicator.first.wait_for(state="attached", timeout=15000)
                await page.wait_for_timeout(2000)
            except Exception:
                console.print(f"[dim]搜索 '{query}' 等待超时[/dim]")
                continue

            no_result = page.locator('td:has-text("No messages matched")')
            if await no_result.count() > 0:
                console.print(f"[dim]搜索 '{query}' 无结果[/dim]")
                continue

            await _dismiss_gmail_popups(page)

            rows = page.locator('tr.zA, tr.zE')
            row_count = await rows.count()
            clicked = ""

            for idx in range(row_count):
                row = rows.nth(idx)
                if await row.is_visible():
                    text = await row.inner_text()
                    if "?" in text:
                        await row.click()
                        clicked = "invite"
                        break

            if not clicked:
                for idx in range(row_count):
                    row = rows.nth(idx)
                    if await row.is_visible():
                        await row.click()
                        clicked = "first"
                        break

            if clicked:
                console.print(f"[dim]已点击邮件 (匹配方式: {clicked})[/dim]")
                await page.wait_for_timeout(2000)

                try:
                    await page.wait_for_function(
                        '() => document.querySelectorAll("iframe").length > 0',
                        timeout=10000,
                    )
                except Exception:
                    console.print("[yellow]点击后未进入邮件正文，重试点击[/yellow]")
                    await _dismiss_gmail_popups(page)
                    for idx in range(await rows.count()):
                        row = rows.nth(idx)
                        if await row.is_visible():
                            text = await row.inner_text()
                            if "?" in text:
                                await row.click()
                                break
                    try:
                        await page.wait_for_function(
                            '() => document.querySelectorAll("iframe").length > 0',
                            timeout=10000,
                        )
                    except Exception:
                        await page.wait_for_timeout(3000)

                mail_found = True
                break
            else:
                console.print(f"[dim]搜索 '{query}' 未找到可点击的邮件行[/dim]")
        except Exception as e:
            logger.debug("搜索 '%s' 失败: %s", query, e)
            continue

    if not mail_found:
        logger.warning("未找到家庭组邀请邮件")
        return False

    accept_href = None

    console.print(f"[dim]当前页面 frame 数量: {len(page.frames)}[/dim]")
    for i, frame in enumerate(page.frames):
        try:
            links_info = await frame.evaluate('''() => {
                const links = document.querySelectorAll('a');
                return Array.from(links).map(a => ({
                    text: (a.innerText || '').trim().substring(0, 80),
                    href: (a.href || '').substring(0, 150)
                }));
            }''')
            if links_info:
                console.print(f"[dim]Frame {i} 链接数: {len(links_info)}[/dim]")
                for li in links_info:
                    if li.get('text') or 'families.google' in li.get('href', ''):
                        console.print(f"[dim]  -> text='{li['text']}' href={li['href']}[/dim]")

            for text in ["Accept invitation", "Accept the invitation", "Join family group",
                         "Join", "Accept", "接受邀请", "加入", "Open invitation"]:
                link = frame.locator(f'a:has-text("{text}")').first
                if await link.is_visible():
                    accept_href = await link.get_attribute("href")
                    console.print(f"[dim]找到邀请链接(文本匹配): text='{text}', href={accept_href[:100] if accept_href else 'None'}[/dim]")
                    break

            if not accept_href:
                family_link = await frame.evaluate('''() => {
                    const links = document.querySelectorAll('a');
                    for (const a of links) {
                        if (a.href && a.href.includes('families.google.com')) {
                            return a.href;
                        }
                    }
                    return null;
                }''')
                if family_link:
                    accept_href = family_link
                    console.print(f"[dim]找到邀请链接(URL匹配): href={accept_href[:100]}[/dim]")

            if accept_href:
                break
        except Exception:
            continue

    if accept_href:
        console.print("[dim]导航到邀请链接...[/dim]")
        await page.goto(accept_href, wait_until="domcontentloaded", timeout=60000)
        await _confirm_join(page)
        console.print("[green]家庭组邀请处理完成[/green]")
        return True

    logger.warning("未能找到或点击接受邀请链接")
    return False


async def _dismiss_gmail_popups(page: Page):
    """关闭 Gmail 各种弹窗和通知栏"""
    for _ in range(3):
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(200)

    dismiss_texts = [
        "Not now", "No thanks", "OK", "Got it", "Close", "Dismiss",
        "No, thanks", "以后再说", "关闭", "不用了", "知道了",
    ]

    # 合并选择器，减少 CDP 调用次数
    for text in dismiss_texts:
        combined = page.locator(
            f'button:has-text("{text}"), a:has-text("{text}"), span:has-text("{text}")'
        ).first
        try:
            if await combined.is_visible():
                await combined.click()
                await page.wait_for_timeout(300)
                console.print(f"[dim]关闭弹窗: {text}[/dim]")
        except Exception:
            pass

    try:
        close_icon = page.locator('[aria-label="Close"], [aria-label="关闭"]').first
        if await close_icon.is_visible():
            await close_icon.click()
            await page.wait_for_timeout(300)
            console.print("[dim]关闭通知栏[/dim]")
    except Exception:
        pass


async def _confirm_join(page: Page):
    """在家庭组确认页面点击同意加入"""
    confirm_selectors = [
        'button:has-text("Join Family Group")',
        'button:has-text("Join family group")',
        'a:has-text("Join Family Group")',
        'a:has-text("Join family group")',
        '[role="button"]:has-text("Join")',
        'button:has-text("Join")',
        'button:has-text("加入家庭群组")',
        'button:has-text("加入")',
        'button:has-text("Accept")',
        'button:has-text("接受")',
        'button:has-text("Confirm")',
        'button:has-text("确认")',
        'button:has-text("Yes")',
        'a:has-text("Join")',
        'a:has-text("Accept")',
        'span:has-text("Join Family Group")',
    ]

    all_btns = page.locator(', '.join(confirm_selectors))
    try:
        await all_btns.first.wait_for(state="visible", timeout=15000)
    except Exception:
        logger.warning("未找到确认按钮，可能已自动加入或页面结构不同")
        return

    console.print(f"[dim]确认加入页面: {page.url}[/dim]")

    for selector in confirm_selectors:
        try:
            btn = page.locator(selector).first
            if await btn.is_visible():
                console.print(f"[dim]确认加入: {selector}[/dim]")
                old_url = page.url
                await btn.click()
                await wait_for_url_change(page, old_url, timeout=15000)
                console.print(f"[dim]点击后页面: {page.url}[/dim]")
                return
        except Exception:
            continue

    logger.warning("未找到确认按钮，可能已自动加入或页面结构不同")
