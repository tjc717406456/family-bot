import random
from playwright.async_api import Page
from rich.console import Console
from config import GEMINI_URL, NAVIGATION_TIMEOUT
from automation.wait_utils import (
    wait_for_networkidle, click_and_wait_hidden,
)

console = Console()

# 随机英文名池
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
    console.print(f"[cyan]开始开通 Gemini[/cyan]")
    console.print(f"[dim]请求地址: {GEMINI_URL}[/dim]")

    await page.goto(GEMINI_URL, wait_until="domcontentloaded", timeout=60000)
    await wait_for_networkidle(page, timeout=10000)

    # 处理可能弹出的同意条款页面
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

    # 跳过 "Got it" 提示
    try:
        got_it_btn = page.locator('button:has-text("Got it")').or_(
            page.locator('button:has-text("知道了")')
        )
        await got_it_btn.wait_for(state="visible", timeout=3000)
        await click_and_wait_hidden(page, got_it_btn, timeout=3000)
        console.print("[dim]跳过 Got it 提示[/dim]")
    except Exception:
        pass

    # 填写 Gem Name 输入框（随机英文名）
    random_name = random.choice(FIRST_NAMES)
    name_filled = False

    # 策略1：点击 "Give your Gem a name" 文字区域聚焦，再用键盘输入
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

    # 策略2：第一个 textbox role 元素
    if not name_filled:
        try:
            first_textbox = page.get_by_role("textbox").first
            await first_textbox.wait_for(state="visible", timeout=5000)
            await first_textbox.fill(random_name)
            name_filled = True
            console.print(f"[dim]填入 Gem 名字 (首个textbox): {random_name}[/dim]")
        except Exception:
            pass

    # 策略3：用 JS 直接找页面中第一个可编辑元素
    if not name_filled:
        try:
            found = await page.evaluate('''(name) => {
                // 找所有 input/textarea，取第一个可见的
                const els = document.querySelectorAll('input, textarea, [contenteditable="true"]');
                for (const el of els) {
                    if (el.offsetParent !== null && el.getBoundingClientRect().height > 0) {
                        el.focus();
                        // 用 input 事件以兼容 Angular
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
            console.print(f"[dim]JS 注入失败: {e}[/dim]")

    if not name_filled:
        console.print("[yellow]警告: 未能填入 Gem 名字[/yellow]")

    # 点击 Save 按钮
    try:
        save_btn = page.locator('button:has-text("Save")').or_(
            page.locator('button:has-text("保存")')
        )
        await save_btn.first.wait_for(state="visible", timeout=5000)
        await save_btn.first.click()
        console.print("[dim]点击 Save 保存 Gem[/dim]")

        # 等待 "has been created" 对话框出现（新开通账号会弹出）
        created_dialog = page.locator('text=has been created')
        try:
            await created_dialog.wait_for(state="visible", timeout=10000)
            console.print("[dim]检测到 Gem 创建成功弹窗[/dim]")

            # 点击对话框里的 Start Chat（用 force 绕过遮罩层拦截）
            dialog_start_chat = page.locator(
                '.cdk-overlay-container button:has-text("Start Chat"), '
                '.cdk-overlay-container button:has-text("Start chat"), '
                '.cdk-overlay-container button:has-text("开始对话")'
            ).first
            await dialog_start_chat.click(force=True)
            console.print("[dim]点击 Start Chat 关闭弹窗[/dim]")
            await wait_for_networkidle(page, timeout=5000)
        except Exception:
            # 已开通账号不会弹此对话框，等保存完成即可
            console.print("[dim]无创建弹窗（账号可能已开通过），等待保存完成[/dim]")
            await wait_for_networkidle(page, timeout=10000)
    except Exception as e:
        console.print(f"[dim]Save 流程异常: {e}[/dim]")

    current_url = page.url

    if "gemini.google.com" in current_url:
        console.print("[green]Gemini 开通成功[/green]")
        return True

    console.print(f"[red]Gemini 开通可能失败，当前页面: {current_url}[/red]")
    return False
