import asyncio
import logging
import os
from datetime import datetime

import click
from playwright.async_api import async_playwright
from rich.console import Console

from config import BROWSER_HEADLESS, BROWSER_SLOW_MO, BROWSER_CHANNEL, BROWSER_USER_DATA_DIR
from db.database import get_session
from db.models import Member

from automation.google_login import google_login
from automation.gemini_activate import activate_gemini
from automation.family_accept import accept_family_invite
from automation.utils import take_screenshot, mark_failed

console = Console()
logger = logging.getLogger(__name__)


async def run_member_flow(member_id: int):
    """对单个成员执行全流程"""
    with get_session() as session:
        member = session.get(Member, member_id)
        if not member:
            console.print(f"[red]成员 ID {member_id} 不存在[/red]")
            return
        if member.status == "joined":
            console.print(f"[yellow]{member.email} 已加入家庭组，跳过[/yellow]")
            return

        console.print(f"\n[bold cyan]===== 开始处理: {member.email} =====[/bold cyan]")

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
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                    "--no-first-run",
                ],
            )
            page = context.pages[0] if context.pages else await context.new_page()

            try:
                login_ok = await google_login(
                    page, member.email, member.password, member.totp_secret or ""
                )
                if not login_ok:
                    mark_failed(session, member, "Google 登录失败")
                    await take_screenshot(page, member, "login_failed")
                    return

                if member.status == "pending":
                    gemini_ok = await activate_gemini(page)
                    if not gemini_ok:
                        mark_failed(session, member, "Gemini 开通失败")
                        await take_screenshot(page, member, "gemini_failed")
                        return
                    member.status = "gemini_done"
                    member.updated_at = datetime.now()
                    session.commit()
                    console.print("[blue]状态更新: gemini_done[/blue]")

                accept_ok = await accept_family_invite(page)
                if not accept_ok:
                    mark_failed(session, member, "接受家庭组邀请失败")
                    await take_screenshot(page, member, "accept_failed")
                    return

                member.status = "joined"
                member.error_msg = None
                member.updated_at = datetime.now()
                session.commit()
                console.print(f"[bold green]===== {member.email} 全流程完成 =====[/bold green]\n")

            except Exception as e:
                mark_failed(session, member, str(e))
                await take_screenshot(page, member, "exception")
                logger.exception("成员流程异常: %s", member.email)
            finally:
                await context.close()


@click.command("run")
@click.option("--member-id", type=int, default=None, help="指定成员 ID")
@click.option("--parent-id", type=int, default=None, help="指定家长 ID，处理其下所有 pending 成员")
@click.option("--all", "run_all", is_flag=True, default=False, help="处理所有 pending 成员")
def run_cli(member_id, parent_id, run_all):
    """执行自动化流程"""
    if member_id:
        asyncio.run(run_member_flow(member_id))
    elif parent_id:
        with get_session() as session:
            members = session.query(Member).filter(
                Member.parent_id == parent_id,
                Member.status.in_(["pending", "gemini_done"])
            ).all()
            if not members:
                console.print("[yellow]该家长下没有待处理的成员[/yellow]")
                return
            console.print(f"[cyan]找到 {len(members)} 个待处理成员[/cyan]")
            ids = [m.id for m in members]
        for mid in ids:
            asyncio.run(run_member_flow(mid))
    elif run_all:
        with get_session() as session:
            members = session.query(Member).filter(
                Member.status.in_(["pending", "gemini_done"])
            ).all()
            if not members:
                console.print("[yellow]没有待处理的成员[/yellow]")
                return
            console.print(f"[cyan]找到 {len(members)} 个待处理成员[/cyan]")
            ids = [m.id for m in members]
        for mid in ids:
            asyncio.run(run_member_flow(mid))
    else:
        console.print("[red]请指定 --member-id、--parent-id 或 --all[/red]")


@click.command("status")
def status_cli():
    """查看各家长下成员状态汇总"""
    from rich.table import Table
    from db.models import Parent

    with get_session() as session:
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
