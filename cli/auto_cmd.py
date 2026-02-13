import asyncio
import os
from datetime import datetime

import click
from playwright.async_api import async_playwright
from rich.console import Console

from config import BROWSER_HEADLESS, BROWSER_SLOW_MO, BROWSER_CHANNEL, BROWSER_USER_DATA_DIR, SCREENSHOT_DIR
from db.database import get_session
from db.models import Member

from automation.google_login import google_login
from automation.gemini_activate import activate_gemini
from automation.family_accept import accept_family_invite

console = Console()


async def run_member_flow(member_id: int):
    """对单个成员执行全流程"""
    session = get_session()
    try:
        member = session.query(Member).get(member_id)
        if not member:
            console.print(f"[red]成员 ID {member_id} 不存在[/red]")
            return
        if member.status == "joined":
            console.print(f"[yellow]{member.email} 已加入家庭组，跳过[/yellow]")
            return

        console.print(f"\n[bold cyan]===== 开始处理: {member.email} =====[/bold cyan]")

        async with async_playwright() as p:
            # 每个成员独立 Chrome profile，互不干扰
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
                # Step 1: 登录
                login_ok = await google_login(
                    page, member.email, member.password, member.totp_secret or ""
                )
                if not login_ok:
                    _fail(session, member, "Google 登录失败")
                    await _screenshot(page, member, "login_failed")
                    return

                # Step 2: 开通 Gemini（pending 状态才执行）
                if member.status == "pending":
                    gemini_ok = await activate_gemini(page)
                    if not gemini_ok:
                        _fail(session, member, "Gemini 开通失败")
                        await _screenshot(page, member, "gemini_failed")
                        return
                    member.status = "gemini_done"
                    member.updated_at = datetime.now()
                    session.commit()
                    console.print(f"[blue]状态更新: gemini_done[/blue]")

                # Step 3: 接受家庭组邀请
                accept_ok = await accept_family_invite(page)
                if not accept_ok:
                    _fail(session, member, "接受家庭组邀请失败")
                    await _screenshot(page, member, "accept_failed")
                    return

                member.status = "joined"
                member.error_msg = None
                member.updated_at = datetime.now()
                session.commit()
                console.print(f"[bold green]===== {member.email} 全流程完成 =====[/bold green]\n")

            except Exception as e:
                _fail(session, member, str(e))
                await _screenshot(page, member, "exception")
                console.print(f"[red]异常: {e}[/red]")
            finally:
                await context.close()
    finally:
        session.close()


def _fail(session, member: Member, reason: str):
    """标记成员失败"""
    member.status = "failed"
    member.error_msg = reason
    member.updated_at = datetime.now()
    session.commit()
    console.print(f"[red]失败: {member.email} - {reason}[/red]")


async def _screenshot(page, member: Member, tag: str):
    """截图保存"""
    filename = f"{member.id}_{member.email}_{tag}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    path = os.path.join(SCREENSHOT_DIR, filename)
    try:
        await page.screenshot(path=path)
        console.print(f"[dim]截图已保存: {path}[/dim]")
    except Exception:
        pass


@click.command("run")
@click.option("--member-id", type=int, default=None, help="指定成员 ID")
@click.option("--parent-id", type=int, default=None, help="指定家长 ID，处理其下所有 pending 成员")
@click.option("--all", "run_all", is_flag=True, default=False, help="处理所有 pending 成员")
def run_cli(member_id, parent_id, run_all):
    """执行自动化流程"""
    if member_id:
        asyncio.run(run_member_flow(member_id))
    elif parent_id:
        session = get_session()
        try:
            members = session.query(Member).filter(
                Member.parent_id == parent_id,
                Member.status.in_(["pending", "gemini_done"])
            ).all()
            if not members:
                console.print("[yellow]该家长下没有待处理的成员[/yellow]")
                return
            console.print(f"[cyan]找到 {len(members)} 个待处理成员[/cyan]")
            ids = [m.id for m in members]
        finally:
            session.close()
        for mid in ids:
            asyncio.run(run_member_flow(mid))
    elif run_all:
        session = get_session()
        try:
            members = session.query(Member).filter(
                Member.status.in_(["pending", "gemini_done"])
            ).all()
            if not members:
                console.print("[yellow]没有待处理的成员[/yellow]")
                return
            console.print(f"[cyan]找到 {len(members)} 个待处理成员[/cyan]")
            ids = [m.id for m in members]
        finally:
            session.close()
        for mid in ids:
            asyncio.run(run_member_flow(mid))
    else:
        console.print("[red]请指定 --member-id、--parent-id 或 --all[/red]")


@click.command("status")
def status_cli():
    """查看各家长下成员状态汇总"""
    from rich.table import Table
    from db.models import Parent

    session = get_session()
    try:
        parents = session.query(Parent).all()
        if not parents:
            console.print("[yellow]暂无数据[/yellow]")
            return

        table = Table(title="家庭组状态汇总")
        table.add_column("家长", style="cyan")
        table.add_column("昵称")
        table.add_column("pending", style="yellow")
        table.add_column("gemini_done", style="blue")
        table.add_column("joined", style="green")
        table.add_column("failed", style="red")
        table.add_column("总计")

        for p in parents:
            counts = {"pending": 0, "gemini_done": 0, "joined": 0, "failed": 0}
            for m in p.members:
                if m.status in counts:
                    counts[m.status] += 1
            total = sum(counts.values())
            table.add_row(
                p.email, p.nickname or "-",
                str(counts["pending"]), str(counts["gemini_done"]),
                str(counts["joined"]), str(counts["failed"]),
                str(total)
            )
        console.print(table)
    finally:
        session.close()
