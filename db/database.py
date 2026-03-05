from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URL
from db.models import Base

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)


def init_db():
    """初始化数据库，建表"""
    Base.metadata.create_all(engine)


@contextmanager
def get_session():
    """获取数据库 session（context manager，自动关闭）"""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
