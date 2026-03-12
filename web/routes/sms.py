import logging

from flask import Blueprint, jsonify, render_template, request

from automation.sms_provider import HaozhumaProvider
from web.routes.config import _load_config

bp = Blueprint("sms", __name__)
logger = logging.getLogger(__name__)


@bp.route("/")
def index():
    config = _load_config()
    return render_template("sms/index.html", config=config)


@bp.route("/get_phone", methods=["POST"])
def get_phone():
    """第一步：登录 + 获取号码，立即返回"""
    config = _load_config()
    project = request.json.get("project", "").strip() or config.get("haozhuma_project", "")

    if not config.get("haozhuma_api_user") or not config.get("haozhuma_api_pass"):
        return jsonify(ok=False, error="请先在配置页面填写豪猪 API 账号和密码")

    if not project:
        return jsonify(ok=False, error="请先配置豪猪项目 ID")

    try:
        provider = HaozhumaProvider()
        if not provider.login():
            return jsonify(ok=False, error="豪猪登录失败，请检查 API 配置")

        phone = provider.get_phone(project=project)
        if not phone:
            return jsonify(ok=False, error="获取手机号失败")

        return jsonify(ok=True, phone=phone, token=provider.token, project=project)
    except Exception as e:
        logger.exception("获取号码失败")
        return jsonify(ok=False, error=str(e))


@bp.route("/poll_code", methods=["POST"])
def poll_code():
    """第二步：查询一次验证码（前端定时调用）"""
    token = request.json.get("token", "")
    phone = request.json.get("phone", "")
    project = request.json.get("project", "")

    if not token or not phone:
        return jsonify(ok=False, error="缺少参数")

    try:
        provider = HaozhumaProvider()
        provider.token = token

        data = provider._get({
            "api": "getMessage",
            "token": token,
            "sid": project,
            "phone": phone,
        })
        logger.info("查询验证码 [%s]: code=%s, msg=%s", phone, data.get("code"), data.get("msg", ""))
        if data.get("code") == 0:
            sms_text = data.get("sms") or data.get("msg", "")
            code = HaozhumaProvider.extract_code(sms_text)
            # 收到码后释放号码
            provider.release_phone(phone, project=project)
            return jsonify(ok=True, sms_text=sms_text, code=code)

        return jsonify(ok=False, waiting=True, msg=data.get("msg", "等待中"))
    except Exception as e:
        logger.exception("查询验证码失败")
        return jsonify(ok=False, error=str(e))


@bp.route("/release", methods=["POST"])
def release():
    """释放或拉黑号码"""
    token = request.json.get("token", "")
    phone = request.json.get("phone", "")
    project = request.json.get("project", "")
    action = request.json.get("action", "release")

    if not token or not phone:
        return jsonify(ok=False, error="缺少参数")

    try:
        provider = HaozhumaProvider()
        provider.token = token
        if action == "black":
            provider.blacklist_phone(phone, project=project)
            return jsonify(ok=True, msg=f"已拉黑号码 {phone}")
        else:
            provider.release_phone(phone, project=project)
            return jsonify(ok=True, msg=f"已释放号码 {phone}")
    except Exception as e:
        return jsonify(ok=False, error=str(e))
