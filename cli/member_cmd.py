import click
from rich.console import Console
from rich.table import Table
from db.database import get_session
from db.models import Member, Parent

console = Console()

STATUS_STYLE = {
    "pending": "yellow",
    "gemini_done": "blue",
    "joined": "green",
    "failed": "red",
}


@click.group("member")
def member_cli():
    """成员账号管理"""
    pass


@member_cli.command("add")
@click.option("--parent-id", required=True, type=int, help="所属家长 ID")
@click.option("--email", required=True, help="成员 Google 邮箱")
@click.option("--password", required=True, help="成员密码")
@click.option("--totp-secret", default="", help="TOTP 密钥")
@click.option("--remark", default="", help="备注")
def add_member(parent_id, email, password, totp_secret, remark):
    """添加成员账号"""
    session = get_session()
    try:
        parent = session.query(Parent).get(parent_id)
        if not parent:
            console.print(f"[red]家长 ID {parent_id} 不存在[/red]")
            return
        if len(parent.members) >= parent.max_members:
            console.print(f"[red]家长 {parent.email} 已达最大成员数 {parent.max_members}[/red]")
            return
        existing = session.query(Member).filter_by(email=email).first()
        if existing:
            console.print(f"[red]成员邮箱 {email} 已存在[/red]")
            return
        member = Member(
            parent_id=parent_id, email=email, password=password,
            totp_secret=totp_secret, remark=remark
        )
        session.add(member)
        session.commit()
        console.print(f"[green]成员添加成功: {email} (ID: {member.id}), 归属家长: {parent.email}[/green]")
    finally:
        session.close()


@member_cli.command("list")
@click.option("--parent-id", type=int, default=None, help="按家长 ID 筛选")
def list_members(parent_id):
    """列出成员"""
    session = get_session()
    try:
        query = session.query(Member)
        if parent_id:
            query = query.filter_by(parent_id=parent_id)
        members = query.all()
        if not members:
            console.print("[yellow]暂无成员数据[/yellow]")
            return
        table = Table(title="成员列表")
        table.add_column("ID", style="cyan")
        table.add_column("家长", style="dim")
        table.add_column("邮箱", style="green")
        table.add_column("备注")
        table.add_column("状态")
        table.add_column("失败原因")
        table.add_column("更新时间")
        for m in members:
            style = STATUS_STYLE.get(m.status, "white")
            table.add_row(
                str(m.id),
                m.parent.email if m.parent else "-",
                m.email,
                m.remark or "-",
                f"[{style}]{m.status}[/{style}]",
                m.error_msg or "-",
                m.updated_at.strftime("%Y-%m-%d %H:%M") if m.updated_at else "-"
            )
        console.print(table)
    finally:
        session.close()


@member_cli.command("delete")
@click.option("--id", "member_id", required=True, type=int, help="成员 ID")
@click.confirmation_option(prompt="确认删除该成员？")
def delete_member(member_id):
    """删除成员"""
    session = get_session()
    try:
        member = session.query(Member).get(member_id)
        if not member:
            console.print(f"[red]成员 ID {member_id} 不存在[/red]")
            return
        email = member.email
        session.delete(member)
        session.commit()
        console.print(f"[green]已删除成员: {email}[/green]")
    finally:
        session.close()
