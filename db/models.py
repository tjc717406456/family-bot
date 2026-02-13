from datetime import datetime
from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Parent(Base):
    __tablename__ = "parents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(Text, unique=True, nullable=False)
    nickname = Column(Text)
    max_members = Column(Integer, default=5)
    created_at = Column(DateTime, default=datetime.now)

    members = relationship("Member", back_populates="parent", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Parent {self.id} {self.email}>"


class Member(Base):
    __tablename__ = "members"

    id = Column(Integer, primary_key=True, autoincrement=True)
    parent_id = Column(Integer, ForeignKey("parents.id"), nullable=False)
    email = Column(Text, unique=True, nullable=False)
    password = Column(Text, nullable=False)
    totp_secret = Column(Text)
    remark = Column(Text)
    status = Column(Text, default="pending")  # pending / gemini_done / joined / failed
    error_msg = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    parent = relationship("Parent", back_populates="members")

    def __repr__(self):
        return f"<Member {self.id} {self.email} [{self.status}]>"
