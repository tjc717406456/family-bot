import random
from playwright.async_api import Page
from rich.console import Console
from config import GEMINI_URL, NAVIGATION_TIMEOUT

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
    await page.wait_for_timeout(5000)

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
                await page.wait_for_timeout(3000)
        except Exception:
            continue

    # 跳过 "Got it" 提示
    try:
        got_it_btn = page.locator('button:has-text("Got it")').or_(
            page.locator('button:has-text("知道了")')
        )
        await got_it_btn.wait_for(state="visible", timeout=5000)
        await got_it_btn.click()
        console.print("[dim]跳过 Got it 提示[/dim]")
        await page.wait_for_timeout(2000)
    except Exception:
        pass

    # 填写 Gem Name 输入框（随机英文名）
    try:
        name_input = page.locator('input[placeholder="Give your Gem a name"]').or_(
            page.locator('input[aria-label="Name"]').or_(
                page.locator('input[aria-label="Gem name"]')
            )
        )
        await name_input.first.wait_for(state="visible", timeout=10000)
        random_name = random.choice(FIRST_NAMES)
        await name_input.first.fill(random_name)
        console.print(f"[dim]填入 Gem 名字: {random_name}[/dim]")
        await page.wait_for_timeout(1000)
    except Exception as e:
        console.print(f"[dim]未找到 Name 输入框: {e}[/dim]")

    # 点击 Save 按钮
    try:
        save_btn = page.locator('button:has-text("Save")').or_(
            page.locator('button:has-text("保存")')
        )
        await save_btn.first.wait_for(state="visible", timeout=5000)
        await save_btn.first.click()
        console.print("[dim]点击 Save 保存 Gem[/dim]")
        await page.wait_for_timeout(5000)
    except Exception as e:
        console.print(f"[dim]未找到 Save 按钮: {e}[/dim]")

    # 点击 "Start Chat" 关闭创建成功弹窗
    try:
        start_chat_btn = page.locator('button:has-text("Start Chat")').or_(
            page.locator('button:has-text("Start chat")').or_(
                page.locator('button:has-text("开始对话")')
            )
        )
        await start_chat_btn.first.wait_for(state="visible", timeout=5000)
        await start_chat_btn.first.click()
        console.print("[dim]点击 Start Chat 关闭弹窗[/dim]")
        await page.wait_for_timeout(3000)
    except Exception:
        pass

    # 检查页面是否加载成功（Gems 创建界面）
    await page.wait_for_timeout(3000)
    current_url = page.url

    if "gemini.google.com" in current_url:
        console.print("[green]Gemini 开通成功[/green]")
        return True

    console.print(f"[red]Gemini 开通可能失败，当前页面: {current_url}[/red]")
    return False
