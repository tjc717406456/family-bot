import json
import logging
import os

from flask import Blueprint, render_template, request, redirect, url_for, flash
from config import BASE_DIR

bp = Blueprint("config", __name__)
logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(BASE_DIR, "antigravity_config.json")

_DEFAULT_CONFIG = {
    "service_type": "antigravity_manager",
    "antigravity_api_url": "",
    "antigravity_api_key": "",
    "gcli2api_url": "",
    "gcli2api_api_key": "",
    "haozhuma_api_url": "https://api.haozhuma.com/sms/",
    "haozhuma_api_user": "",
    "haozhuma_api_pass": "",
    "haozhuma_project": "",
}


def _load_config():
    """加载配置文件"""
    if not os.path.exists(CONFIG_PATH):
        return dict(_DEFAULT_CONFIG)

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning("配置文件读取失败，使用默认值: %s", e)
        return dict(_DEFAULT_CONFIG)


def _save_config(config):
    """保存配置文件"""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)


@bp.route("/")
def index():
    config = _load_config()
    return render_template("config/index.html", config=config)


@bp.route("/save", methods=["POST"])
def save():
    config = _load_config()

    config["service_type"] = request.form.get("service_type", "antigravity_manager").strip()
    config["antigravity_api_url"] = request.form.get("antigravity_api_url", "").strip()
    config["antigravity_api_key"] = request.form.get("antigravity_api_key", "").strip()
    config["gcli2api_url"] = request.form.get("gcli2api_url", "").strip()
    config["gcli2api_api_key"] = request.form.get("gcli2api_api_key", "").strip()
    config["haozhuma_api_url"] = request.form.get("haozhuma_api_url", "").strip() or "https://api.haozhuma.com/sms/"
    config["haozhuma_api_user"] = request.form.get("haozhuma_api_user", "").strip()
    config["haozhuma_api_pass"] = request.form.get("haozhuma_api_pass", "").strip()
    config["haozhuma_project"] = request.form.get("haozhuma_project", "").strip()

    try:
        _save_config(config)
        from automation.oauth_utils import reload_config
        reload_config()
        flash("配置已保存", "success")
    except Exception as e:
        logger.exception("保存配置失败")
        flash(f"保存失败: {e}", "danger")

    return redirect(url_for("config.index"))
