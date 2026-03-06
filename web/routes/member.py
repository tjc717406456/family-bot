import logging
import os
import shutil

from flask import Blueprint, render_template, request, redirect, url_for, flash, Response, jsonify
from sqlalchemy.orm import joinedload
from db.database import get_session
from db.models import Parent, Member
from config import BROWSER_USER_DATA_DIR
from utils.crypto import encrypt, decrypt_safe
from web.task_manager import task_manager

bp = Blueprint("member", __name__)
logger = logging.getLogger(__name__)


def _update_member_field(member_id, field, value, success_msg, fail_msg="成员不存在"):
    """通用的单字段更新辅助方法"""
    with get_session() as session:
        m = session.get(Member, member_id)
        if not m:
            flash(fail_msg, "danger")
        else:
            setattr(m, field, value)
            session.commit()
            if success_msg:
                flash(success_msg.format(email=m.email), "success")
    return redirect(url_for("member.list_members"))


@bp.route("/")
def list_members():
    parent_id = request.args.get("parent_id", type=int)
    with get_session() as session:
        parents = session.query(Parent).all()
        parent_list = [{"id": p.id, "email": p.email} for p in parents]

        query = session.query(Member).options(joinedload(Member.parent))
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
                "remark2": m.remark2 or "",
                "created_at": m.created_at.strftime("%Y-%m-%d %H:%M") if m.created_at else "-",
                "updated_at": m.updated_at.strftime("%Y-%m-%d %H:%M") if m.updated_at else "-",
            })
        return render_template(
            "member/list.html",
            members=data,
            parents=parent_list,
            current_parent_id=parent_id,
        )


@bp.route("/add", methods=["POST"])
def add_member():
    parent_id = request.form.get("parent_id", type=int)
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "").strip()
    totp_secret = request.form.get("totp_secret", "").strip()
    remark = request.form.get("remark", "").strip()

    if not parent_id or not email or not password or not totp_secret:
        flash("家长、邮箱、密码、2FA密钥为必填项", "danger")
        return redirect(url_for("member.list_members"))

    with get_session() as session:
        exists = session.query(Member).filter_by(email=email).first()
        if exists:
            flash(f"成员 {email} 已存在", "warning")
            return redirect(url_for("member.list_members"))

        m = Member(
            parent_id=parent_id,
            email=email,
            password=encrypt(password),
            totp_secret=encrypt(totp_secret) if totp_secret else None,
            remark=remark or None,
        )
        session.add(m)
        session.commit()
        flash(f"成员 {email} 添加成功", "success")
    return redirect(url_for("member.list_members"))


@bp.route("/batch_import", methods=["POST"])
def batch_import():
    parent_id = request.form.get("parent_id", type=int)
    members_data = request.form.get("members_data", "").strip()

    if not parent_id or not members_data:
        flash("请选择家长并填写成员数据", "danger")
        return redirect(url_for("member.list_members"))

    with get_session() as session:
        lines = members_data.replace("\r\n", "\n").replace("\r", "\n").split("\n")

        added_count = 0
        skipped_count = 0
        error_count = 0

        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue

            line = line.rstrip(";；")
            parts = line.split("----")

            if len(parts) < 3:
                flash(f"第 {line_num} 行格式错误，已跳过: {line[:50]}", "warning")
                error_count += 1
                continue

            email = parts[0].strip()
            password = parts[1].strip()

            if len(parts) >= 4:
                totp_secret = parts[3].strip()
            else:
                totp_secret = parts[2].strip()

            if not email or not password or not totp_secret:
                flash(f"第 {line_num} 行数据不完整，已跳过", "warning")
                error_count += 1
                continue

            exists = session.query(Member).filter_by(email=email).first()
            if exists:
                skipped_count += 1
                continue

            try:
                m = Member(
                    parent_id=parent_id,
                    email=email,
                    password=encrypt(password),
                    totp_secret=encrypt(totp_secret) if totp_secret else None,
                )
                session.add(m)
                added_count += 1
            except Exception as e:
                logger.warning("添加成员 %s 失败: %s", email, e)
                flash(f"添加 {email} 失败: {e}", "danger")
                error_count += 1

        session.commit()

        result_msg = f"导入完成：成功 {added_count} 个"
        if skipped_count > 0:
            result_msg += f"，跳过 {skipped_count} 个（已存在）"
        if error_count > 0:
            result_msg += f"，失败 {error_count} 个"

        flash(result_msg, "success" if error_count == 0 else "warning")

    return redirect(url_for("member.list_members"))


@bp.route("/delete/<int:member_id>", methods=["POST"])
def delete_member(member_id):
    with get_session() as session:
        m = session.get(Member, member_id)
        if not m:
            flash("成员不存在", "danger")
        else:
            email = m.email
            mid = m.id
            session.delete(m)
            session.commit()

            profile_dir = os.path.join(BROWSER_USER_DATA_DIR, f"member_{mid}")
            if os.path.exists(profile_dir):
                try:
                    shutil.rmtree(profile_dir)
                    flash(f"成员 {email} 及其登录信息已删除", "success")
                except Exception as e:
                    logger.warning("清除 Chrome Profile 失败: %s", e)
                    flash(f"成员 {email} 已删除，但清除登录信息失败: {e}", "warning")
            else:
                flash(f"成员 {email} 已删除", "success")
    return redirect(url_for("member.list_members"))


@bp.route("/reset/<int:member_id>", methods=["POST"])
def reset_member(member_id):
    with get_session() as session:
        m = session.get(Member, member_id)
        if not m:
            flash("成员不存在", "danger")
        else:
            m.status = "pending"
            m.error_msg = None
            session.commit()
            flash(f"成员 {m.email} 已重置为 pending", "success")
    return redirect(url_for("member.list_members"))


@bp.route("/clear_error/<int:member_id>", methods=["POST"])
def clear_error(member_id):
    return _update_member_field(member_id, "error_msg", None, "成员 {email} 错误信息已清空")


@bp.route("/clear_remark/<int:member_id>", methods=["POST"])
def clear_remark(member_id):
    return _update_member_field(member_id, "remark", None, "成员 {email} 备注已清空")


@bp.route("/save_remark2/<int:member_id>", methods=["POST"])
def save_remark2(member_id):
    remark2 = request.form.get("remark2", "").strip()
    return _update_member_field(member_id, "remark2", remark2 or None, None)


@bp.route("/clear_remark2/<int:member_id>", methods=["POST"])
def clear_remark2(member_id):
    return _update_member_field(member_id, "remark2", None, None)


@bp.route("/export")
def export_members():
    parent_id = request.args.get("parent_id", type=int)
    with get_session() as session:
        query = session.query(Member)
        if parent_id:
            query = query.filter(Member.parent_id == parent_id)
        members = query.all()

        lines = []
        for m in members:
            plain_pwd = decrypt_safe(m.password) if m.password else ""
            plain_totp = decrypt_safe(m.totp_secret) if m.totp_secret else ""
            lines.append(f"{m.email}----{plain_pwd}----{plain_totp}")

        content = "\n".join(lines)
        return Response(
            content,
            mimetype="text/plain; charset=utf-8",
            headers={
                "Content-Disposition": "attachment; filename*=UTF-8''%E6%88%91%E7%9A%84%E8%B4%A6%E5%8F%B7.txt"
            },
        )


@bp.route("/secret/<int:member_id>")
def get_secret(member_id):
    """按需返回成员的解密密码和 TOTP 密钥（不再嵌入 HTML 页面源码）"""
    with get_session() as session:
        m = session.get(Member, member_id)
        if not m:
            return jsonify({"error": "成员不存在"}), 404
        return jsonify({
            "password": decrypt_safe(m.password) if m.password else "",
            "totp_secret": decrypt_safe(m.totp_secret) if m.totp_secret else "",
        })


@bp.route("/change_parent/<int:member_id>", methods=["POST"])
def change_parent(member_id):
    new_parent_id = request.form.get("parent_id", type=int)
    if not new_parent_id:
        flash("请选择家长", "danger")
        return redirect(url_for("member.list_members"))

    with get_session() as session:
        m = session.get(Member, member_id)
        if not m:
            flash("成员不存在", "danger")
        else:
            parent = session.get(Parent, new_parent_id)
            if not parent:
                flash("家长不存在", "danger")
            elif m.parent_id != new_parent_id:
                m.parent_id = new_parent_id
                session.commit()
                flash(f"成员 {m.email} 已转移到家长 {parent.email}", "success")
    return redirect(url_for("member.list_members"))


@bp.route("/open_browser/<int:member_id>", methods=["POST"])
def open_browser(member_id):
    with get_session() as session:
        member = session.get(Member, member_id)
        if not member:
            flash("成员不存在", "danger")
            return redirect(url_for("member.list_members"))
        task_id = task_manager.run_open_browser(member.id, member.email)
        flash(f"已启动成员 {member.email} 的浏览器 (任务ID: {task_id})", "info")
    return redirect(url_for("member.list_members"))


@bp.route("/antigravity/<int:member_id>", methods=["POST"])
def antigravity(member_id):
    from automation.oauth_utils import generate_oauth_url

    with get_session() as session:
        member = session.get(Member, member_id)
        if not member:
            flash("成员不存在", "danger")
            return redirect(url_for("member.list_members"))

        oauth_url = generate_oauth_url()
        task_id = task_manager.run_antigravity(member.id, member.email, oauth_url)
        flash(f"Antigravity 任务已启动: {member.email} (任务ID: {task_id})", "info")
    return redirect(url_for("member.list_members"))
