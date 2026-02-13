import click
from rich.console import Console
from rich.table import Table
from db.database import get_session
from db.models import Parent

console = Console()


@click.group("parent")
def parent_cli():
    """家长账号管理"""
    pass


@parent_cli.command("add")
@click.option("--email", required=True, help="家长 Google 邮箱")
@click.option("--nickname", default="", help="家长昵称")
@click.option("--max-members", default=5, help="最大成员数")
def add_parent(email, nickname, max_members):
    """添加家长账号"""
    session = get_session()
    try:
        existing = session.query(Parent).filter_by(email=email).first()
        if existing:
            console.print(f"[red]邮箱 {email} 已存在[/red]")
            return
        parent = Parent(email=email, nickname=nickname, max_members=max_members)
        session.add(parent)
        session.commit()
        console.print(f"[green]家长添加成功: {email} (ID: {parent.id})[/green]")
    finally:
        session.close()


@parent_cli.command("list")
def list_parents():
    """列出所有家长"""
    session = get_session()
    try:
        parents = session.query(Parent).all()
        if not parents:
            console.print("[yellow]暂无家长数据[/yellow]")
            return
        table = Table(title="家长列表")
        table.add_column("ID", style="cyan")
        table.add_column("邮箱", style="green")
        table.add_column("昵称")
        table.add_column("最大成员数")
        table.add_column("当前成员数")
        table.add_column("创建时间")
        for p in parents:
            table.add_row(
                str(p.id), p.email, p.nickname or "-",
                str(p.max_members), str(len(p.members)),
                p.created_at.strftime("%Y-%m-%d %H:%M") if p.created_at else "-"
            )
        console.print(table)
    finally:
        session.close()


@parent_cli.command("delete")
@click.option("--id", "parent_id", required=True, type=int, help="家长 ID")
@click.confirmation_option(prompt="确认删除该家长及其所有成员？")
def delete_parent(parent_id):
    """删除家长（级联删除成员）"""
    session = get_session()
    try:
        parent = session.query(Parent).get(parent_id)
        if not parent:
            console.print(f"[red]家长 ID {parent_id} 不存在[/red]")
            return
        email = parent.email
        session.delete(parent)
        session.commit()
        console.print(f"[green]已删除家长: {email}[/green]")
    finally:
        session.close()
