"""数据库模型单元测试"""

from db.models import Parent, Member


class TestParentModel:
    def test_create_parent(self, db_session):
        p = Parent(email="parent@test.com", nickname="Test", max_members=5)
        db_session.add(p)
        db_session.commit()

        result = db_session.query(Parent).first()
        assert result.email == "parent@test.com"
        assert result.nickname == "Test"
        assert result.max_members == 5
        assert result.created_at is not None

    def test_parent_unique_email(self, db_session):
        p1 = Parent(email="dup@test.com")
        db_session.add(p1)
        db_session.commit()

        p2 = Parent(email="dup@test.com")
        db_session.add(p2)
        import sqlalchemy
        try:
            db_session.commit()
            assert False, "Should have raised IntegrityError"
        except sqlalchemy.exc.IntegrityError:
            db_session.rollback()

    def test_cascade_delete(self, db_session):
        p = Parent(email="parent@test.com")
        db_session.add(p)
        db_session.commit()

        m = Member(parent_id=p.id, email="child@test.com", password="pw", totp_secret="totp")
        db_session.add(m)
        db_session.commit()

        db_session.delete(p)
        db_session.commit()

        assert db_session.query(Member).count() == 0


class TestMemberModel:
    def test_create_member(self, db_session):
        p = Parent(email="parent@test.com")
        db_session.add(p)
        db_session.commit()

        m = Member(
            parent_id=p.id,
            email="member@test.com",
            password="secret",
            totp_secret="ABCDEF",
            status="pending",
        )
        db_session.add(m)
        db_session.commit()

        result = db_session.query(Member).first()
        assert result.email == "member@test.com"
        assert result.password == "secret"
        assert result.status == "pending"
        assert result.parent.email == "parent@test.com"

    def test_default_status(self, db_session):
        p = Parent(email="parent@test.com")
        db_session.add(p)
        db_session.commit()

        m = Member(parent_id=p.id, email="m@test.com", password="pw")
        db_session.add(m)
        db_session.commit()

        assert m.status == "pending"
