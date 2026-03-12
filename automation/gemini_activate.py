import logging
import random

from playwright.async_api import Page
from rich.console import Console
from config import GEMINI_URL
from automation.wait_utils import (
    wait_for_networkidle, click_and_wait_hidden,
)

console = Console()
logger = logging.getLogger(__name__)

FIRST_NAMES = [
    "James", "John", "Robert", "Michael", "David", "William", "Richard", "Joseph",
    "Thomas", "Daniel", "Matthew", "Anthony", "Mark", "Steven", "Paul", "Andrew",
    "Emily", "Sarah", "Jessica", "Ashley", "Amanda", "Sophia", "Isabella", "Olivia",
    "Emma", "Mia", "Charlotte", "Amelia", "Harper", "Evelyn", "Abigail", "Ella",
]


async def activate_gemini(page: Page) -> bool:
    """
    开通 Gemini 服务
    返回 True 表示开通成功
    """
    console.print("[cyan]开始开通 Gemini[/cyan]")
    logger.info("开通 Gemini: %s", GEMINI_URL)

    await page.goto(GEMINI_URL, wait_until="domcontentloaded", timeout=60000)
    await wait_for_networkidle(page, timeout=10000)

    agree_selectors = [
        'button:has-text("I agree")',
        'button:has-text("同意")',
        'button:has-text("Accept")',
        'button:has-text("Get started")',
        'button:has-text("开始使用")',
        'button:has-text("Continue")',
        'button:has-text("继续")',
    ]

    for selector in agree_selectors:
        try:
            btn = page.locator(selector).first
            if await btn.is_visible():
                console.print(f"[dim]点击按钮: {selector}[/dim]")
                await btn.click()
                await wait_for_networkidle(page, timeout=5000)
        except Exception:
            continue

    # 关闭所有 Got it 提示（可能有多个）
    for attempt in range(5):
        try:
            got_it_btn = page.locator('button:has-text("Got it")').or_(
                page.locator('button:has-text("知道了")')
            ).first
            if await got_it_btn.is_visible():
                await got_it_btn.click()
                console.print(f"[dim]跳过 Got it 提示 ({attempt + 1})[/dim]")
                await page.wait_for_timeout(1000)
            else:
                break
        except Exception:
            break

    random_name = random.choice(FIRST_NAMES)
    name_filled = False

    # 策略1：直接点击 "Give your Gem a name" 占位文本然后键盘输入
    try:
        placeholder_el = page.locator('text="Give your Gem a name"').first
        if await placeholder_el.is_visible(timeout=5000):
            await placeholder_el.click()
            await page.wait_for_timeout(500)
            await page.keyboard.type(random_name, delay=50)
            name_filled = True
            console.print(f"[dim]填入 Gem 名字 (点击占位文本): {random_name}[/dim]")
    except Exception:
        pass

    # 策略2：通过 placeholder / aria-label 定位 input 或 textarea
    if not name_filled:
        try:
            name_input = page.locator(
                'input[placeholder*="name" i], '
                'textarea[placeholder*="name" i], '
                'input[placeholder*="Gem" i], '
                'textarea[placeholder*="Gem" i], '
                'input[aria-label*="name" i], '
                'textarea[aria-label*="name" i], '
                'input[aria-label*="Gem" i], '
                'textarea[aria-label*="Gem" i], '
                '[contenteditable="true"][aria-label*="name" i], '
                '[contenteditable="true"][aria-label*="Gem" i]'
            ).first
            if await name_input.is_visible(timeout=3000):
                await name_input.click()
                await name_input.fill(random_name)
                name_filled = True
                console.print(f"[dim]填入 Gem 名字 (placeholder定位): {random_name}[/dim]")
        except Exception:
            pass

    # 策略3：JS 精确定位 name 输入框（排除 description/instructions）
    if not name_filled:
        try:
            found = await page.evaluate('''(name) => {
                const inputs = document.querySelectorAll('input, textarea, [contenteditable="true"]');
                for (const el of inputs) {
                    if (el.offsetParent === null || el.getBoundingClientRect().height <= 0) continue;
                    const ph = (el.placeholder || '').toLowerCase();
                    const label = (el.getAttribute('aria-label') || '').toLowerCase();
                    if (ph.includes('name') || ph.includes('gem') || label.includes('name') || label.includes('gem')) {
                        el.focus();
                        el.value = name;
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                        return 'matched: ' + (ph || label);
                    }
                }
                // 兜底：取页面上最靠上的可见 input（y 坐标最小的）
                let topEl = null, topY = Infinity;
                for (const el of inputs) {
                    const rect = el.getBoundingClientRect();
                    if (rect.height > 0 && el.offsetParent !== null && rect.top < topY) {
                        topY = rect.top;
                        topEl = el;
                    }
                }
                if (topEl) {
                    topEl.focus();
                    topEl.value = name;
                    topEl.dispatchEvent(new Event('input', { bubbles: true }));
                    topEl.dispatchEvent(new Event('change', { bubbles: true }));
                    return 'topmost: ' + topEl.tagName;
                }
                return '';
            }''', random_name)
            if found:
                name_filled = True
                console.print(f"[dim]填入 Gem 名字 (JS {found}): {random_name}[/dim]")
        except Exception as e:
            logger.debug("JS 注入失败: %s", e)

    if not name_filled:
        logger.warning("未能填入 Gem 名字")

    try:
        save_btn = page.locator('button:has-text("Save")').or_(
            page.locator('button:has-text("保存")')
        )
        await save_btn.first.wait_for(state="visible", timeout=5000)
        await save_btn.first.click()
        console.print("[dim]点击 Save 保存 Gem[/dim]")

        created_dialog = page.locator('text=has been created')
        try:
            await created_dialog.wait_for(state="visible", timeout=10000)
            console.print("[dim]检测到 Gem 创建成功弹窗[/dim]")

            dialog_start_chat = page.locator(
                '.cdk-overlay-container button:has-text("Start Chat"), '
                '.cdk-overlay-container button:has-text("Start chat"), '
                '.cdk-overlay-container button:has-text("开始对话")'
            ).first
            await dialog_start_chat.click(force=True)
            console.print("[dim]点击 Start Chat 关闭弹窗[/dim]")
            await wait_for_networkidle(page, timeout=5000)
        except Exception:
            console.print("[dim]无创建弹窗（账号可能已开通过），等待保存完成[/dim]")
            await wait_for_networkidle(page, timeout=10000)
    except Exception as e:
        logger.debug("Save 流程异常: %s", e)

    current_url = page.url

    if "gemini.google.com" in current_url:
        console.print("[green]Gemini 开通成功[/green]")
        return True

    logger.warning("Gemini 开通可能失败，当前页面: %s", current_url)
    return False
