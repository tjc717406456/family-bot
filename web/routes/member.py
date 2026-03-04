import os
import shutil

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from db.database import get_session
from db.models import Parent, Member
from config import BROWSER_USER_DATA_DIR
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
                "password": m.password or "",
                "totp_secret": m.totp_secret or "",
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
    finally:
        session.close()


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


@bp.route("/batch_import", methods=["POST"])
def batch_import():
    parent_id = request.form.get("parent_id", type=int)
    members_data = request.form.get("members_data", "").strip()

    if not parent_id or not members_data:
        flash("请选择家长并填写成员数据", "danger")
        return redirect(url_for("member.list_members"))

    session = get_session()
    try:
        # 解析成员数据
        lines = members_data.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        
        added_count = 0
        skipped_count = 0
        error_count = 0
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
            
            # 移除结尾的分号（中英文）
            line = line.rstrip(";；")
            
            # 按 ---- 分割
            parts = line.split("----")
            
            # 至少需要 3 个字段：邮箱、密码、2FA
            # 如果有 4 个字段：邮箱、密码、辅助邮箱、2FA（跳过辅助邮箱）
            if len(parts) < 3:
                flash(f"第 {line_num} 行格式错误，已跳过: {line[:50]}", "warning")
                error_count += 1
                continue
            
            email = parts[0].strip()
            password = parts[1].strip()
            
            # 判断是否有辅助邮箱
            if len(parts) >= 4:
                # 有辅助邮箱，跳过第3个字段，取第4个作为2FA
                totp_secret = parts[3].strip()
            else:
                # 没有辅助邮箱，第3个字段就是2FA
                totp_secret = parts[2].strip()
            
            if not email or not password or not totp_secret:
                flash(f"第 {line_num} 行数据不完整，已跳过", "warning")
                error_count += 1
                continue
            
            # 检查是否已存在
            exists = session.query(Member).filter_by(email=email).first()
            if exists:
                skipped_count += 1
                continue
            
            # 添加成员
            try:
                m = Member(
                    parent_id=parent_id,
                    email=email,
                    password=password,
                    totp_secret=totp_secret,
                )
                session.add(m)
                added_count += 1
            except Exception as e:
                flash(f"添加 {email} 失败: {e}", "danger")
                error_count += 1
        
        session.commit()
        
        # 显示导入结果
        result_msg = f"导入完成：成功 {added_count} 个"
        if skipped_count > 0:
            result_msg += f"，跳过 {skipped_count} 个（已存在）"
        if error_count > 0:
            result_msg += f"，失败 {error_count} 个"
        
        flash(result_msg, "success" if error_count == 0 else "warning")
    except Exception as e:
        session.rollback()
        flash(f"批量导入失败: {e}", "danger")
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
            mid = m.id
            session.delete(m)
            session.commit()

            # 删除浏览器登录信息
            profile_dir = os.path.join(BROWSER_USER_DATA_DIR, f"member_{mid}")
            if os.path.exists(profile_dir):
                try:
                    shutil.rmtree(profile_dir)
                    flash(f"成员 {email} 及其登录信息已删除", "success")
                except Exception as e:
                    flash(f"成员 {email} 已删除，但清除登录信息失败: {e}", "warning")
            else:
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


@bp.route("/save_remark2/<int:member_id>", methods=["POST"])
def save_remark2(member_id):
    remark2 = request.form.get("remark2", "").strip()
    session = get_session()
    try:
        m = session.query(Member).get(member_id)
        if m:
            m.remark2 = remark2 or None
            session.commit()
    finally:
        session.close()
    return redirect(url_for("member.list_members"))


@bp.route("/clear_remark2/<int:member_id>", methods=["POST"])
def clear_remark2(member_id):
    session = get_session()
    try:
        m = session.query(Member).get(member_id)
        if m:
            m.remark2 = None
            session.commit()
    finally:
        session.close()
    return redirect(url_for("member.list_members"))


@bp.route("/open_browser/<int:member_id>", methods=["POST"])
def open_browser(member_id):
    session = get_session()
    try:
        member = session.query(Member).get(member_id)
        if not member:
            flash("成员不存在", "danger")
            return redirect(url_for("member.list_members"))
        task_id = task_manager.run_open_browser(member.id, member.email)
        flash(f"已启动成员 {member.email} 的浏览器 (任务ID: {task_id})", "info")
    finally:
        session.close()
    return redirect(url_for("member.list_members"))


@bp.route("/antigravity/<int:member_id>", methods=["POST"])
def antigravity(member_id):
    from automation.oauth_utils import generate_oauth_url

    session = get_session()
    try:
        member = session.query(Member).get(member_id)
        if not member:
            flash("成员不存在", "danger")
            return redirect(url_for("member.list_members"))

        oauth_url = generate_oauth_url()
        task_id = task_manager.run_antigravity(member.id, member.email, oauth_url)
        flash(f"Antigravity 任务已启动: {member.email} (任务ID: {task_id})", "info")
    finally:
        session.close()
    return redirect(url_for("member.list_members"))
