import os

from flask import Flask, request, Response


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


def _check_auth(username, password):
    from config import WEB_AUTH_USERNAME, WEB_AUTH_PASSWORD
    return username == WEB_AUTH_USERNAME and password == WEB_AUTH_PASSWORD


def _require_auth():
    return Response(
        "需要登录才能访问", 401,
        {"WWW-Authenticate": 'Basic realm="Google Family Bot"'},
    )


def create_app():
    app = Flask(__name__)
    app.secret_key = _get_secret_key()

    from config import WEB_AUTH_PASSWORD

    if WEB_AUTH_PASSWORD:
        @app.before_request
        def auth_check():
            # 静态文件不需要认证
            if request.path.startswith("/static/"):
                return None
            auth = request.authorization
            if not auth or not _check_auth(auth.username, auth.password):
                return _require_auth()

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

    @app.errorhandler(404)
    def not_found(e):
        return "页面不存在", 404

    @app.errorhandler(500)
    def server_error(e):
        return "服务器内部错误", 500

    return app
