import asyncio
import threading
import time
from datetime import datetime


class TaskManager:
    """后台任务管理器，线程执行自动化任务"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tasks = {}
            cls._instance._lock = threading.Lock()
        return cls._instance

    def _gen_id(self):
        return f"task_{int(time.time() * 1000)}"

    def get_all_tasks(self):
        with self._lock:
            return dict(self._tasks)

    def run_member(self, member_id: int, email: str):
        """执行单个成员"""
        task_id = self._gen_id()
        with self._lock:
            self._tasks[task_id] = {
                "type": "member",
                "member_id": member_id,
                "email": email,
                "status": "running",
                "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "finished_at": None,
                "error": None,
            }
        t = threading.Thread(target=self._exec, args=(task_id, [member_id]), daemon=True)
        t.start()
        return task_id

    def run_parent(self, parent_id: int, parent_email: str):
        """执行某家长下所有待处理成员"""
        from db.database import get_session
        from db.models import Member

        session = get_session()
        try:
            members = session.query(Member).filter(
                Member.parent_id == parent_id,
                Member.status.in_(["pending", "gemini_done"])
            ).all()
            ids = [m.id for m in members]
            emails = [m.email for m in members]
        finally:
            session.close()

        if not ids:
            return None

        task_id = self._gen_id()
        with self._lock:
            self._tasks[task_id] = {
                "type": "parent",
                "parent_id": parent_id,
                "parent_email": parent_email,
                "member_count": len(ids),
                "emails": emails,
                "status": "running",
                "progress": 0,
                "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "finished_at": None,
                "error": None,
            }
        t = threading.Thread(target=self._exec, args=(task_id, ids), daemon=True)
        t.start()
        return task_id

    def run_all(self):
        """执行所有待处理成员"""
        from db.database import get_session
        from db.models import Member

        session = get_session()
        try:
            members = session.query(Member).filter(
                Member.status.in_(["pending", "gemini_done"])
            ).all()
            ids = [m.id for m in members]
            emails = [m.email for m in members]
        finally:
            session.close()

        if not ids:
            return None

        task_id = self._gen_id()
        with self._lock:
            self._tasks[task_id] = {
                "type": "all",
                "member_count": len(ids),
                "emails": emails,
                "status": "running",
                "progress": 0,
                "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "finished_at": None,
                "error": None,
            }
        t = threading.Thread(target=self._exec, args=(task_id, ids), daemon=True)
        t.start()
        return task_id

    def run_antigravity(self, member_id: int, email: str, oauth_url: str):
        """执行 Antigravity OAuth 登录"""
        task_id = self._gen_id()
        with self._lock:
            self._tasks[task_id] = {
                "type": "antigravity",
                "member_id": member_id,
                "email": email,
                "oauth_url": oauth_url,
                "status": "running",
                "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "finished_at": None,
                "error": None,
            }
        t = threading.Thread(target=self._exec_antigravity, args=(task_id, member_id, oauth_url), daemon=True)
        t.start()
        return task_id

    def _exec_antigravity(self, task_id: str, member_id: int, oauth_url: str):
        """线程内执行 Antigravity 登录"""
        from automation.antigravity_login import antigravity_login

        try:
            result = asyncio.run(antigravity_login(member_id, oauth_url))
            with self._lock:
                self._tasks[task_id]["status"] = "done" if result else "failed"
                self._tasks[task_id]["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if not result:
                    self._tasks[task_id]["error"] = "Antigravity 登录未成功"
        except Exception as e:
            with self._lock:
                self._tasks[task_id]["status"] = "failed"
                self._tasks[task_id]["error"] = str(e)
                self._tasks[task_id]["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _exec(self, task_id: str, member_ids: list):
        """在线程内逐个执行成员流程"""
        from cli.auto_cmd import run_member_flow

        try:
            total = len(member_ids)
            for i, mid in enumerate(member_ids):
                asyncio.run(run_member_flow(mid))
                with self._lock:
                    self._tasks[task_id]["progress"] = i + 1
            with self._lock:
                self._tasks[task_id]["status"] = "done"
                self._tasks[task_id]["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            with self._lock:
                self._tasks[task_id]["status"] = "failed"
                self._tasks[task_id]["error"] = str(e)
                self._tasks[task_id]["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


task_manager = TaskManager()
