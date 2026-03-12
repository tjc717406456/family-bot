import logging
import sys
import traceback

from config import setup_logging, WEB_DEBUG, WEB_HOST, WEB_PORT

setup_logging()
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    try:
        from db.database import init_db
        from web import create_app

        init_db()
        app = create_app()
        logger.info("启动 Web 服务: http://%s:%d", WEB_HOST, WEB_PORT)
        app.run(host=WEB_HOST, port=WEB_PORT, debug=WEB_DEBUG)
    except Exception:
        traceback.print_exc()
        sys.exit(1)
