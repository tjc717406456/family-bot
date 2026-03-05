import logging
import sys

from config import setup_logging, WEB_DEBUG, WEB_HOST, WEB_PORT

setup_logging()
logger = logging.getLogger(__name__)

try:
    from db.database import init_db
    from web import create_app

    if __name__ == "__main__":
        init_db()
        app = create_app()
        logger.info("启动 Web 服务: http://%s:%d", WEB_HOST, WEB_PORT)
        app.run(host=WEB_HOST, port=WEB_PORT, debug=WEB_DEBUG)
except Exception:
    logger.exception("Web 服务启动失败")
    sys.exit(1)
