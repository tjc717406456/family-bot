from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from config import DATABASE_URL
from db.models import Base


engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)


def init_db():
    """初始化数据库，建表"""
    Base.metadata.create_all(engine)


def get_session() -> Session:
    return SessionLocal()
