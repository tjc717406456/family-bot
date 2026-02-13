from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from db.database import get_session
from db.models import Parent, Member
from web.task_manager import task_manager

bp = Blueprint("member", __name__)


@bp.route("/")
def list_members():
    parent_id = request.args.get("parent_id", type=int)
    session = get_session()
    try:
        parents = session.query(Parent).all()
        parent_list = [{"id": p.id, "email": p.email} for p in parents]

        query = session.query(Member)
        if parent_id:
            query = query.filter(Member.parent_id == parent_id)
        members = query.all()

        data = []
        for m in members:
            data.append({
                "id": m.id,
                "email": m.email,
                "parent_email": m.parent.email if m.parent else "-",
                "parent_id": m.parent_id,
                "status": m.status,
                "error_msg": m.error_msg or "",
                "remark": m.remark or "",
                "created_at": m.created_at.strftime("%Y-%m-%d %H:%M") if m.created_at else "-",
                "updated_at": m.updated_at.strftime("%Y-%m-%d %H:%M") if m.updated_at else "-",
            })
        return render_template(
            "member/list.html",
            members=data,
            parents=parent_list,
            current_parent_id=parent_id,
        )
    finally:
        session.close()


@bp.route("/add", methods=["POST"])
def add_member():
    parent_id = request.form.get("parent_id", type=int)
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "").strip()
    totp_secret = request.form.get("totp_secret", "").strip()
    remark = request.form.get("remark", "").strip()

    if not parent_id or not email or not password:
        flash("家长、邮箱、密码为必填项", "danger")
        return redirect(url_for("member.list_members"))

    session = get_session()
    try:
        exists = session.query(Member).filter_by(email=email).first()
        if exists:
            flash(f"成员 {email} 已存在", "warning")
            return redirect(url_for("member.list_members"))

        m = Member(
            parent_id=parent_id,
            email=email,
            password=password,
            totp_secret=totp_secret or None,
            remark=remark or None,
        )
        session.add(m)
        session.commit()
        flash(f"成员 {email} 添加成功", "success")
    finally:
        session.close()
    return redirect(url_for("member.list_members"))


@bp.route("/delete/<int:member_id>", methods=["POST"])
def delete_member(member_id):
    session = get_session()
    try:
        m = session.query(Member).get(member_id)
        if not m:
            flash("成员不存在", "danger")
        else:
            email = m.email
            session.delete(m)
            session.commit()
            flash(f"成员 {email} 已删除", "success")
    finally:
        session.close()
    return redirect(url_for("member.list_members"))


@bp.route("/reset/<int:member_id>", methods=["POST"])
def reset_member(member_id):
    session = get_session()
    try:
        m = session.query(Member).get(member_id)
        if not m:
            flash("成员不存在", "danger")
        else:
            m.status = "pending"
            m.error_msg = None
            session.commit()
            flash(f"成员 {m.email} 已重置为 pending", "success")
    finally:
        session.close()
    return redirect(url_for("member.list_members"))


@bp.route("/clear_error/<int:member_id>", methods=["POST"])
def clear_error(member_id):
    session = get_session()
    try:
        m = session.query(Member).get(member_id)
        if m:
            m.error_msg = None
            session.commit()
            flash(f"成员 {m.email} 错误信息已清空", "success")
        else:
            flash("成员不存在", "danger")
    finally:
        session.close()
    return redirect(url_for("member.list_members"))


@bp.route("/clear_remark/<int:member_id>", methods=["POST"])
def clear_remark(member_id):
    session = get_session()
    try:
        m = session.query(Member).get(member_id)
        if m:
            m.remark = None
            session.commit()
            flash(f"成员 {m.email} 备注已清空", "success")
        else:
            flash("成员不存在", "danger")
    finally:
        session.close()
    return redirect(url_for("member.list_members"))


@bp.route("/antigravity/<int:member_id>", methods=["POST"])
def antigravity(member_id):
    oauth_url = request.form.get("oauth_url", "").strip()
    if not oauth_url:
        flash("请先填入 OAuth 链接", "danger")
        return redirect(url_for("member.list_members"))

    session = get_session()
    try:
        member = session.query(Member).get(member_id)
        if not member:
            flash("成员不存在", "danger")
            return redirect(url_for("member.list_members"))

        task_id = task_manager.run_antigravity(member.id, member.email, oauth_url)
        flash(f"Antigravity 任务已启动: {member.email} (任务ID: {task_id})", "info")
    finally:
        session.close()
    return redirect(url_for("member.list_members"))
