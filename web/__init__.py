from flask import Flask


def create_app():
    app = Flask(__name__)
    app.secret_key = "google-family-bot-web-secret"

    from web.routes.dashboard import bp as dashboard_bp
    from web.routes.parent import bp as parent_bp
    from web.routes.member import bp as member_bp
    from web.routes.task import bp as task_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(parent_bp, url_prefix="/parent")
    app.register_blueprint(member_bp, url_prefix="/member")
    app.register_blueprint(task_bp, url_prefix="/task")

    return app
