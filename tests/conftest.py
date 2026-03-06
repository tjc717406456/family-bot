import os
import sys

import pytest  # noqa: F401

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.models import Base  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402


@pytest.fixture()
def db_session(tmp_path):
    """每条测试用例使用独立的内存 SQLite 数据库"""
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def app(tmp_path, monkeypatch):
    """创建测试用 Flask app，使用临时数据库"""
    db_path = tmp_path / "test.db"
    monkeypatch.setattr("config.DB_PATH", str(db_path))
    monkeypatch.setattr("config.DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setattr("config.DATA_DIR", str(tmp_path))

    import db.database as db_mod
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    db_mod.engine = engine
    db_mod.SessionLocal = sessionmaker(bind=engine)

    from db.models import Base
    Base.metadata.create_all(engine)

    from web import create_app
    application = create_app()
    application.config["TESTING"] = True
    yield application

    engine.dispose()


@pytest.fixture()
def client(app):
    """Flask 测试客户端"""
    return app.test_client()
