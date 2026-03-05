import logging

from flask import Blueprint, render_template, jsonify, flash, redirect, url_for
from sqlalchemy.orm import joinedload
from db.database import get_session
from db.models import Parent, Member
from web.task_manager import task_manager

bp = Blueprint("task", __name__)
logger = logging.getLogger(__name__)


@bp.route("/")
def list_tasks():
    with get_session() as session:
        # eager load members 避免 N+1
        parents = session.query(Parent).options(joinedload(Parent.members)).all()
        parent_list = []
        for p in parents:
            pending = [m for m in p.members if m.status in ("pending", "gemini_done")]
            parent_list.append({
                "id": p.id,
                "email": p.email,
                "pending_count": len(pending),
            })
        members = session.query(Member).options(
            joinedload(Member.parent)
        ).filter(
            Member.status.in_(["pending", "gemini_done"])
        ).all()
        member_list = [{"id": m.id, "email": m.email, "status": m.status, "parent_email": m.parent.email} for m in members]
        total_pending = len(member_list)

    tasks = task_manager.get_all_tasks()
    return render_template(
        "task/list.html",
        parents=parent_list,
        members=member_list,
        total_pending=total_pending,
        tasks=tasks,
    )


@bp.route("/run/member/<int:member_id>", methods=["POST"])
def run_member(member_id):
    with get_session() as session:
        m = session.get(Member, member_id)
        if not m:
            flash("成员不存在", "danger")
            return redirect(url_for("task.list_tasks"))
        task_id = task_manager.run_member(m.id, m.email)
        flash(f"已启动任务：{m.email}", "success")
    return redirect(url_for("task.list_tasks"))


@bp.route("/run/parent/<int:parent_id>", methods=["POST"])
def run_parent(parent_id):
    with get_session() as session:
        p = session.get(Parent, parent_id)
        if not p:
            flash("家长不存在", "danger")
            return redirect(url_for("task.list_tasks"))
        task_ids = task_manager.run_parent(p.id, p.email)
        if not task_ids:
            flash(f"家长 {p.email} 下没有待处理成员", "warning")
        else:
            flash(f"已启动 {len(task_ids)} 个并行任务：{p.email} 下所有待处理成员", "success")
    return redirect(url_for("task.list_tasks"))


@bp.route("/run/all", methods=["POST"])
def run_all():
    task_ids = task_manager.run_all()
    if not task_ids:
        flash("没有待处理的成员", "warning")
    else:
        flash(f"已启动 {len(task_ids)} 个并行任务", "success")
    return redirect(url_for("task.list_tasks"))


@bp.route("/status/all")
def status_all():
    return jsonify(task_manager.get_all_tasks())


@bp.route("/clear", methods=["POST"])
def clear_tasks():
    count = task_manager.clear_finished_tasks()
    flash(f"已清理 {count} 个已完成任务", "success") if count else flash("没有可清理的任务", "info")
    return redirect(url_for("task.list_tasks"))
