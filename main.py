import click
from db.database import init_db
from cli.parent_cmd import parent_cli
from cli.member_cmd import member_cli
from cli.auto_cmd import run_cli, status_cli


@click.group()
def cli():
    """Google 家庭组自动化管理工具"""
    init_db()


cli.add_command(parent_cli)
cli.add_command(member_cli)
cli.add_command(run_cli)
cli.add_command(status_cli)


if __name__ == "__main__":
    cli()
