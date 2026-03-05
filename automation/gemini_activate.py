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

    try:
        got_it_btn = page.locator('button:has-text("Got it")').or_(
            page.locator('button:has-text("知道了")')
        )
        await got_it_btn.wait_for(state="visible", timeout=3000)
        await click_and_wait_hidden(page, got_it_btn, timeout=3000)
        console.print("[dim]跳过 Got it 提示[/dim]")
    except Exception:
        pass

    random_name = random.choice(FIRST_NAMES)
    name_filled = False

    # 策略1：点击 label 聚焦
    try:
        label = page.locator('text="Give your Gem a name"').first
        if await label.is_visible():
            await label.click()
            await page.wait_for_timeout(500)
            await page.keyboard.type(random_name)
            name_filled = True
            console.print(f"[dim]填入 Gem 名字 (点击label): {random_name}[/dim]")
    except Exception:
        pass

    # 策略2：textbox role
    if not name_filled:
        try:
            first_textbox = page.get_by_role("textbox").first
            await first_textbox.wait_for(state="visible", timeout=5000)
            await first_textbox.fill(random_name)
            name_filled = True
            console.print(f"[dim]填入 Gem 名字 (首个textbox): {random_name}[/dim]")
        except Exception:
            pass

    # 策略3：JS 注入
    if not name_filled:
        try:
            found = await page.evaluate('''(name) => {
                const els = document.querySelectorAll('input, textarea, [contenteditable="true"]');
                for (const el of els) {
                    if (el.offsetParent !== null && el.getBoundingClientRect().height > 0) {
                        el.focus();
                        const nativeSetter = Object.getOwnPropertyDescriptor(
                            window.HTMLInputElement.prototype, 'value'
                        )?.set || Object.getOwnPropertyDescriptor(
                            window.HTMLTextAreaElement.prototype, 'value'
                        )?.set;
                        if (nativeSetter) {
                            nativeSetter.call(el, name);
                        } else {
                            el.value = name;
                        }
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                        return el.tagName + '.' + (el.className || '').substring(0, 60);
                    }
                }
                return '';
            }''', random_name)
            if found:
                name_filled = True
                console.print(f"[dim]填入 Gem 名字 (JS注入 {found}): {random_name}[/dim]")
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
