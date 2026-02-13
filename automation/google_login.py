import pyotp
from playwright.async_api import Page, BrowserContext
from rich.console import Console
from config import GOOGLE_SIGNIN_URL, LOGIN_TIMEOUT

console = Console()


async def google_login(page: Page, email: str, password: str, totp_secret: str = "") -> bool:
    """
    Google 账号登录，支持 TOTP 自动验证
    每个成员用独立 Chrome profile，不存在账号冲突
    """
    console.print(f"[cyan]开始登录: {email}[/cyan]")
    console.print(f"[dim]请求地址: {GOOGLE_SIGNIN_URL}[/dim]")

    await page.goto(GOOGLE_SIGNIN_URL, wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(3000)

    # 检测是否已登录（独立 profile 里只有这一个账号，session 还在就直接跳过）
    current_url = page.url
    if "accounts.google.com/signin" not in current_url and "accounts.google.com/v3/signin" not in current_url:
        console.print(f"[green]已有登录态，跳过登录: {email}[/green]")
        return True

    # 填入邮箱
    try:
        email_input = page.locator('input[type="email"]')
        await email_input.wait_for(state="visible", timeout=10000)
        await email_input.fill(email)
        console.print(f"[dim]已填入邮箱: {email}[/dim]")
    except Exception:
        # 邮箱输入框不存在，可能已登录
        console.print(f"[green]已有登录态，跳过登录: {email}[/green]")
        return True

    # 点击下一步
    await page.locator("#identifierNext").click()
    await page.wait_for_timeout(2000)

    # 填入密码
    password_input = page.locator('input[name="Passwd"]')
    await password_input.wait_for(state="visible", timeout=LOGIN_TIMEOUT)
    await password_input.fill(password)
    console.print("[dim]已填入密码[/dim]")

    # 点击下一步
    await page.locator("#passwordNext").click()
    await page.wait_for_timeout(3000)

    # 检测是否需要 2FA
    if totp_secret:
        try:
            totp_input = page.locator('input[type="tel"]')
            is_visible = await totp_input.is_visible()
            if is_visible:
                totp = pyotp.TOTP(totp_secret)
                code = totp.now()
                console.print(f"[dim]生成 TOTP 验证码: {code}[/dim]")
                await totp_input.fill(code)
                await page.locator("#totpNext").click()
                await page.wait_for_timeout(3000)
        except Exception:
            console.print("[dim]未检测到 2FA 页面，跳过[/dim]")

    # 跳过 Passkey 注册页面（"Sign in faster" / "Not now"）
    try:
        not_now_btn = page.locator('button:has-text("Not now")').or_(
            page.locator('button:has-text("以后再说")')
        )
        await not_now_btn.wait_for(state="visible", timeout=5000)
        await not_now_btn.click()
        console.print("[dim]跳过 Passkey 注册页面[/dim]")
        await page.wait_for_timeout(2000)
    except Exception:
        pass

    # 处理 Chrome "Turn on sync?" / "登录 Chrome" 弹窗
    try:
        sync_btn = page.locator('button:has-text("Continue")').or_(
            page.locator('button:has-text("继续")').or_(
                page.locator('button:has-text("Yes, I\'m in")').or_(
                    page.locator('button:has-text("Turn on")')
                )
            )
        )
        await sync_btn.first.wait_for(state="visible", timeout=5000)
        await sync_btn.first.click()
        console.print("[dim]确认 Chrome 同步账号[/dim]")
        await page.wait_for_timeout(2000)
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
        console.print(f"[red]登录可能失败，当前页面: {current_url}[/red]")
        return False
