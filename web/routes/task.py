from flask import Blueprint, render_template, jsonify, flash, redirect, url_for
from db.database import get_session
from db.models import Parent, Member
from web.task_manager import task_manager

bp = Blueprint("task", __name__)


@bp.route("/")
def list_tasks():
    session = get_session()
    try:
        parents = session.query(Parent).all()
        parent_list = []
        for p in parents:
            pending = [m for m in p.members if m.status in ("pending", "gemini_done")]
            parent_list.append({
                "id": p.id,
                "email": p.email,
                "pending_count": len(pending),
            })
        members = session.query(Member).filter(
            Member.status.in_(["pending", "gemini_done"])
        ).all()
        member_list = [{"id": m.id, "email": m.email, "status": m.status, "parent_email": m.parent.email} for m in members]
        total_pending = len(member_list)
    finally:
        session.close()

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
    session = get_session()
    try:
        m = session.query(Member).get(member_id)
        if not m:
            flash("成员不存在", "danger")
            return redirect(url_for("task.list_tasks"))
        task_id = task_manager.run_member(m.id, m.email)
        flash(f"已启动任务：{m.email}", "success")
    finally:
        session.close()
    return redirect(url_for("task.list_tasks"))


@bp.route("/run/parent/<int:parent_id>", methods=["POST"])
def run_parent(parent_id):
    session = get_session()
    try:
        p = session.query(Parent).get(parent_id)
        if not p:
            flash("家长不存在", "danger")
            return redirect(url_for("task.list_tasks"))
        task_id = task_manager.run_parent(p.id, p.email)
        if task_id is None:
            flash(f"家长 {p.email} 下没有待处理成员", "warning")
        else:
            flash(f"已启动任务：{p.email} 下所有待处理成员", "success")
    finally:
        session.close()
    return redirect(url_for("task.list_tasks"))


@bp.route("/run/all", methods=["POST"])
def run_all():
    task_id = task_manager.run_all()
    if task_id is None:
        flash("没有待处理的成员", "warning")
    else:
        flash("已启动全量执行任务", "success")
    return redirect(url_for("task.list_tasks"))


@bp.route("/status/all")
def status_all():
    return jsonify(task_manager.get_all_tasks())
