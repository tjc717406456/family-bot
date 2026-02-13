from playwright.async_api import Page
from rich.console import Console
from config import GMAIL_URL, NAVIGATION_TIMEOUT

console = Console()


async def accept_family_invite(page: Page) -> bool:
    """
    在 Gmail 中找到家庭组邀请邮件并接受
    返回 True 表示加入成功
    """
    console.print("[cyan]开始处理家庭组邀请[/cyan]")
    console.print(f"[dim]请求地址: {GMAIL_URL}[/dim]")

    await page.goto(GMAIL_URL, wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(8000)

    # 暴力关闭 Gmail 所有弹窗：先按 Escape，再逐个点关闭按钮
    for _ in range(3):
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(500)

    for dismiss_text in ["Not now", "No thanks", "OK", "Got it", "Close", "Dismiss", "以后再说", "关闭"]:
        try:
            dismiss_btn = page.locator(f'button:has-text("{dismiss_text}")').first
            if await dismiss_btn.is_visible():
                await dismiss_btn.click()
                console.print(f"[dim]关闭提示框: {dismiss_text}[/dim]")
                await page.wait_for_timeout(1000)
        except Exception:
            pass

    await page.wait_for_timeout(2000)

    # 搜索家庭组邀请邮件（带问号的是邀请，不带的是加入成功通知）
    search_queries = [
        "Join family group?",
        "wants you to join",
        "family group invitation",
        "Join family group",
    ]

    mail_found = False
    for query in search_queries:
        console.print(f"[dim]搜索邮件: {query}[/dim]")
        search_input = page.locator('input[aria-label="搜索邮件"]').or_(
            page.locator('input[aria-label="Search mail"]')
        )
        try:
            await search_input.wait_for(state="visible", timeout=10000)
            # 清空搜索框再填
            await search_input.click()
            await search_input.fill("")
            await page.wait_for_timeout(500)
            await search_input.fill(query)
            await page.wait_for_timeout(1000)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(5000)

            # 检查是否有 "No messages matched" 提示
            no_result = page.locator('td:has-text("No messages matched")')
            if await no_result.count() > 0:
                console.print(f"[dim]搜索 '{query}' 无结果[/dim]")
                continue

            # 优先点击包含 "?" 的邮件行（邀请邮件），避免点到 Welcome 通知
            clicked = await page.evaluate('''() => {
                const rows = document.querySelectorAll('tr.zA, tr.zE');
                // 优先找包含 "?" 的行（邀请邮件标题带问号）
                for (const row of rows) {
                    const text = row.innerText || '';
                    if (text.includes('?') && (row.offsetParent !== null || row.getBoundingClientRect().height > 0)) {
                        row.click();
                        return 'invite';
                    }
                }
                // 兜底：点第一个可见行
                for (const row of rows) {
                    if (row.offsetParent !== null || row.getBoundingClientRect().height > 0) {
                        row.click();
                        return 'first';
                    }
                }
                if (rows.length > 0) {
                    rows[0].click();
                    return 'fallback';
                }
                return '';
            }''')

            if clicked:
                console.print(f"[dim]已点击邮件 (匹配方式: {clicked})[/dim]")
                await page.wait_for_timeout(10000)
                mail_found = True
                break
            else:
                console.print(f"[dim]搜索 '{query}' 未找到可点击的邮件行[/dim]")
        except Exception as e:
            console.print(f"[dim]搜索 '{query}' 未找到结果: {e}[/dim]")
            continue

    if not mail_found:
        console.print("[red]未找到家庭组邀请邮件[/red]")
        return False

    # Gmail 邮件正文渲染在 iframe 里，遍历所有 frame 找 Accept invitation 链接
    accept_clicked = False
    accept_href = None

    console.print(f"[dim]当前页面 frame 数量: {len(page.frames)}[/dim]")
    for i, frame in enumerate(page.frames):
        try:
            # 打印每个 frame 里的链接，方便排查
            links_info = await frame.evaluate('''() => {
                const links = document.querySelectorAll('a');
                return Array.from(links).slice(0, 20).map(a => ({
                    text: (a.innerText || '').trim().substring(0, 80),
                    href: (a.href || '').substring(0, 100)
                }));
            }''')
            if links_info:
                console.print(f"[dim]Frame {i} 链接: {links_info}[/dim]")

            for text in ["Accept invitation", "Accept the invitation", "Join family group",
                         "Join", "Accept", "接受邀请", "加入", "Open invitation"]:
                link = frame.locator(f'a:has-text("{text}")').first
                if await link.is_visible():
                    accept_href = await link.get_attribute("href")
                    console.print(f"[dim]找到邀请链接: text='{text}', href={accept_href[:100] if accept_href else 'None'}[/dim]")
                    break
            if accept_href:
                break
        except Exception:
            continue

    # 直接用主页面导航到链接，不靠 click
    if accept_href:
        console.print(f"[dim]导航到邀请链接...[/dim]")
        await page.goto(accept_href, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(8000)
        await _confirm_join(page)
        accept_clicked = True

    if accept_clicked:
        console.print("[green]家庭组邀请处理完成[/green]")
        return True

    console.print("[red]未能找到或点击接受邀请链接[/red]")
    return False


async def _confirm_join(page: Page):
    """在家庭组确认页面点击同意加入"""
    await page.wait_for_timeout(3000)
    console.print(f"[dim]确认加入页面: {page.url}[/dim]")

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

    for selector in confirm_selectors:
        try:
            btn = page.locator(selector).first
            if await btn.is_visible():
                console.print(f"[dim]确认加入: {selector}[/dim]")
                await btn.click()
                await page.wait_for_timeout(10000)
                console.print(f"[dim]点击后页面: {page.url}[/dim]")
                return
        except Exception:
            continue

    console.print("[yellow]未找到确认按钮，可能已自动加入或页面结构不同[/yellow]")
