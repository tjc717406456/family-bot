import json
import os
from flask import Blueprint, render_template, request, redirect, url_for, flash

bp = Blueprint("config", __name__)

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "antigravity_config.json")


def _load_config():
    """加载配置文件"""
    if not os.path.exists(CONFIG_PATH):
        return {
            "antigravity_api_url": "",
            "antigravity_api_key": "",
        }
    
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


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
    
    # 更新可编辑的配置项
    config["antigravity_api_url"] = request.form.get("antigravity_api_url", "").strip()
    config["antigravity_api_key"] = request.form.get("antigravity_api_key", "").strip()
    
    try:
        _save_config(config)
        from automation.oauth_utils import reload_config
        reload_config()
        flash("配置已保存", "success")
    except Exception as e:
        flash(f"保存失败: {e}", "danger")
    
    return redirect(url_for("config.index"))
