import os
from flask import Flask


def _get_secret_key():
    """从文件加载或自动生成 secret_key，持久化到 data/.flask_secret"""
    from config import DATA_DIR
    secret_file = os.path.join(DATA_DIR, ".flask_secret")
    if os.path.exists(secret_file):
        with open(secret_file, "r") as f:
            return f.read().strip()
    key = os.urandom(32).hex()
    with open(secret_file, "w") as f:
        f.write(key)
    return key


def create_app():
    app = Flask(__name__)
    app.secret_key = _get_secret_key()

    from web.routes.dashboard import bp as dashboard_bp
    from web.routes.parent import bp as parent_bp
    from web.routes.member import bp as member_bp
    from web.routes.task import bp as task_bp
    from web.routes.config import bp as config_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(parent_bp, url_prefix="/parent")
    app.register_blueprint(member_bp, url_prefix="/member")
    app.register_blueprint(task_bp, url_prefix="/task")
    app.register_blueprint(config_bp, url_prefix="/config")

    return app
