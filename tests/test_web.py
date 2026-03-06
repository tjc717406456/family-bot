"""Web 路由集成测试"""


class TestDashboard:
    def test_index_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Family Bot" in resp.data.decode()


class TestParentRoutes:
    def test_list_parents_empty(self, client):
        resp = client.get("/parent/")
        assert resp.status_code == 200

    def test_add_parent(self, client):
        resp = client.post("/parent/add", data={
            "email": "parent@gmail.com",
            "nickname": "TestParent",
            "max_members": "5",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert "parent@gmail.com" in resp.data.decode()

    def test_add_duplicate_parent(self, client):
        client.post("/parent/add", data={"email": "dup@gmail.com", "max_members": "5"})
        resp = client.post("/parent/add", data={"email": "dup@gmail.com", "max_members": "5"}, follow_redirects=True)
        assert resp.status_code == 200
        assert "已存在" in resp.data.decode()

    def test_add_parent_empty_email(self, client):
        resp = client.post("/parent/add", data={"email": "", "max_members": "5"}, follow_redirects=True)
        assert resp.status_code == 200
        assert "不能为空" in resp.data.decode()

    def test_delete_parent(self, client):
        client.post("/parent/add", data={"email": "del@gmail.com", "max_members": "5"})
        resp = client.post("/parent/delete/1", follow_redirects=True)
        assert resp.status_code == 200
        assert "已删除" in resp.data.decode()


class TestMemberRoutes:
    def _add_parent(self, client):
        client.post("/parent/add", data={
            "email": "parent@gmail.com", "max_members": "5"
        })

    def test_list_members_empty(self, client):
        resp = client.get("/member/")
        assert resp.status_code == 200

    def test_add_member(self, client):
        self._add_parent(client)
        resp = client.post("/member/add", data={
            "parent_id": "1",
            "email": "member@gmail.com",
            "password": "secret123",
            "totp_secret": "ABCDEF123456",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert "member@gmail.com" in resp.data.decode()
        assert "添加成功" in resp.data.decode()

    def test_password_not_in_page_source(self, client):
        """密码不应出现在 HTML 页面源码中"""
        self._add_parent(client)
        client.post("/member/add", data={
            "parent_id": "1",
            "email": "member@gmail.com",
            "password": "secret123",
            "totp_secret": "ABCDEF123456",
        })
        resp = client.get("/member/")
        html = resp.data.decode()
        assert "secret123" not in html
        assert "ABCDEF123456" not in html

    def test_secret_api_returns_decrypted(self, client):
        """/member/secret/<id> 应返回解密后的密码"""
        self._add_parent(client)
        client.post("/member/add", data={
            "parent_id": "1",
            "email": "member@gmail.com",
            "password": "mypassword",
            "totp_secret": "TOTP123",
        })
        resp = client.get("/member/secret/1")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["password"] == "mypassword"
        assert data["totp_secret"] == "TOTP123"

    def test_add_member_missing_fields(self, client):
        self._add_parent(client)
        resp = client.post("/member/add", data={
            "parent_id": "1",
            "email": "m@gmail.com",
            "password": "",
            "totp_secret": "",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert "必填项" in resp.data.decode()

    def test_reset_member(self, client):
        self._add_parent(client)
        client.post("/member/add", data={
            "parent_id": "1",
            "email": "m@gmail.com",
            "password": "pw",
            "totp_secret": "totp",
        })
        resp = client.post("/member/reset/1", follow_redirects=True)
        assert resp.status_code == 200

    def test_export_members(self, client):
        self._add_parent(client)
        client.post("/member/add", data={
            "parent_id": "1",
            "email": "m@gmail.com",
            "password": "exportpw",
            "totp_secret": "exporttotp",
        })
        resp = client.get("/member/export")
        assert resp.status_code == 200
        content = resp.data.decode()
        assert "m@gmail.com" in content
        assert "exportpw" in content
        assert "exporttotp" in content

    def test_batch_import(self, client):
        self._add_parent(client)
        data = "user1@gmail.com----pass1----totp1\nuser2@gmail.com----pass2----totp2"
        resp = client.post("/member/batch_import", data={
            "parent_id": "1",
            "members_data": data,
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert "导入完成" in resp.data.decode()


class TestTaskRoutes:
    def test_list_tasks(self, client):
        resp = client.get("/task/")
        assert resp.status_code == 200

    def test_status_api(self, client):
        resp = client.get("/task/status/all")
        assert resp.status_code == 200
        assert resp.get_json() == {}
