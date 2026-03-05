import logging

from flask import Blueprint, render_template, request, redirect, url_for, flash
from sqlalchemy import func
from db.database import get_session
from db.models import Parent, Member

bp = Blueprint("parent", __name__)
logger = logging.getLogger(__name__)


@bp.route("/")
def list_parents():
    with get_session() as session:
        # 子查询统计成员数，避免 N+1
        member_count_sq = (
            session.query(Member.parent_id, func.count(Member.id).label("cnt"))
            .group_by(Member.parent_id)
            .subquery()
        )
        rows = (
            session.query(Parent, func.coalesce(member_count_sq.c.cnt, 0).label("member_count"))
            .outerjoin(member_count_sq, Parent.id == member_count_sq.c.parent_id)
            .all()
        )

        data = []
        for p, member_count in rows:
            data.append({
                "id": p.id,
                "email": p.email,
                "nickname": p.nickname or "-",
                "max_members": p.max_members,
                "member_count": member_count,
                "created_at": p.created_at.strftime("%Y-%m-%d %H:%M") if p.created_at else "-",
            })
        return render_template("parent/list.html", parents=data)


@bp.route("/add", methods=["POST"])
def add_parent():
    email = request.form.get("email", "").strip()
    nickname = request.form.get("nickname", "").strip()
    max_members = request.form.get("max_members", "5").strip()

    if not email:
        flash("邮箱不能为空", "danger")
        return redirect(url_for("parent.list_parents"))

    try:
        max_members_int = int(max_members) if max_members else 5
    except ValueError:
        flash("最大成员数必须为数字", "danger")
        return redirect(url_for("parent.list_parents"))

    with get_session() as session:
        exists = session.query(Parent).filter_by(email=email).first()
        if exists:
            flash(f"家长 {email} 已存在", "warning")
            return redirect(url_for("parent.list_parents"))

        p = Parent(
            email=email,
            nickname=nickname or None,
            max_members=max_members_int,
        )
        session.add(p)
        session.commit()
        flash(f"家长 {email} 添加成功", "success")
    return redirect(url_for("parent.list_parents"))


@bp.route("/delete/<int:parent_id>", methods=["POST"])
def delete_parent(parent_id):
    with get_session() as session:
        p = session.get(Parent, parent_id)
        if not p:
            flash("家长不存在", "danger")
        else:
            email = p.email
            session.delete(p)
            session.commit()
            flash(f"家长 {email} 已删除", "success")
    return redirect(url_for("parent.list_parents"))
