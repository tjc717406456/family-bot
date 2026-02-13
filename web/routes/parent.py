from flask import Blueprint, render_template, request, redirect, url_for, flash
from db.database import get_session
from db.models import Parent

bp = Blueprint("parent", __name__)


@bp.route("/")
def list_parents():
    session = get_session()
    try:
        parents = session.query(Parent).all()
        data = []
        for p in parents:
            data.append({
                "id": p.id,
                "email": p.email,
                "nickname": p.nickname or "-",
                "max_members": p.max_members,
                "member_count": len(p.members),
                "created_at": p.created_at.strftime("%Y-%m-%d %H:%M") if p.created_at else "-",
            })
        return render_template("parent/list.html", parents=data)
    finally:
        session.close()


@bp.route("/add", methods=["POST"])
def add_parent():
    email = request.form.get("email", "").strip()
    nickname = request.form.get("nickname", "").strip()
    max_members = request.form.get("max_members", "5").strip()

    if not email:
        flash("邮箱不能为空", "danger")
        return redirect(url_for("parent.list_parents"))

    session = get_session()
    try:
        exists = session.query(Parent).filter_by(email=email).first()
        if exists:
            flash(f"家长 {email} 已存在", "warning")
            return redirect(url_for("parent.list_parents"))

        p = Parent(
            email=email,
            nickname=nickname or None,
            max_members=int(max_members) if max_members else 5,
        )
        session.add(p)
        session.commit()
        flash(f"家长 {email} 添加成功", "success")
    finally:
        session.close()
    return redirect(url_for("parent.list_parents"))


@bp.route("/delete/<int:parent_id>", methods=["POST"])
def delete_parent(parent_id):
    session = get_session()
    try:
        p = session.query(Parent).get(parent_id)
        if not p:
            flash("家长不存在", "danger")
        else:
            email = p.email
            session.delete(p)
            session.commit()
            flash(f"家长 {email} 已删除", "success")
    finally:
        session.close()
    return redirect(url_for("parent.list_parents"))
