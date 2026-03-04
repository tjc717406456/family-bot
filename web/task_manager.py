import asyncio
import threading
import time
from datetime import datetime

MAX_FINISHED_TASKS = 100


class TaskManager:
    """后台任务管理器，线程执行自动化任务"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tasks = {}
            cls._instance._lock = threading.Lock()
            cls._instance._counter = 0
        return cls._instance

    def _gen_id(self):
        with self._lock:
            self._counter += 1
            return f"task_{int(time.time() * 1000)}_{self._counter}"

    def _cleanup_finished(self):
        """清理已完成的旧任务，保留最近 MAX_FINISHED_TASKS 个"""
        finished = [
            (tid, t) for tid, t in self._tasks.items()
            if t["status"] in ("done", "failed")
        ]
        if len(finished) <= MAX_FINISHED_TASKS:
            return
        finished.sort(key=lambda x: x[1].get("finished_at", ""))
        for tid, _ in finished[:-MAX_FINISHED_TASKS]:
            del self._tasks[tid]

    def get_all_tasks(self):
        with self._lock:
            return dict(self._tasks)

    def clear_finished_tasks(self):
        """清理所有已完成/失败的任务"""
        with self._lock:
            to_del = [tid for tid, t in self._tasks.items() if t["status"] in ("done", "failed")]
            for tid in to_del:
                del self._tasks[tid]
            return len(to_del)

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
        """执行某家长下所有待处理成员（每个成员独立任务并行执行）"""
        from db.database import get_session
        from db.models import Member

        session = get_session()
        try:
            members = session.query(Member).filter(
                Member.parent_id == parent_id,
                Member.status.in_(["pending", "gemini_done"])
            ).all()
            member_info = [(m.id, m.email) for m in members]
        finally:
            session.close()

        if not member_info:
            return []

        task_ids = []
        for mid, email in member_info:
            task_id = self.run_member(mid, email)
            task_ids.append(task_id)
        return task_ids

    def run_all(self):
        """执行所有待处理成员（每个成员独立任务并行执行）"""
        from db.database import get_session
        from db.models import Member

        session = get_session()
        try:
            members = session.query(Member).filter(
                Member.status.in_(["pending", "gemini_done"])
            ).all()
            member_info = [(m.id, m.email) for m in members]
        finally:
            session.close()

        if not member_info:
            return []

        task_ids = []
        for mid, email in member_info:
            task_id = self.run_member(mid, email)
            task_ids.append(task_id)
        return task_ids

    def run_open_browser(self, member_id: int, email: str):
        """打开成员浏览器并自动登录"""
        task_id = self._gen_id()
        with self._lock:
            self._tasks[task_id] = {
                "type": "open_browser",
                "member_id": member_id,
                "email": email,
                "status": "running",
                "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "finished_at": None,
                "error": None,
            }
        t = threading.Thread(target=self._exec_open_browser, args=(task_id, member_id), daemon=True)
        t.start()
        return task_id

    def _exec_open_browser(self, task_id: str, member_id: int):
        from automation.open_browser import open_browser_for_member
        try:
            asyncio.run(open_browser_for_member(member_id))
            with self._lock:
                self._tasks[task_id]["status"] = "done"
                self._tasks[task_id]["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self._cleanup_finished()
        except Exception as e:
            with self._lock:
                self._tasks[task_id]["status"] = "failed"
                self._tasks[task_id]["error"] = str(e)
                self._tasks[task_id]["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self._cleanup_finished()

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
                self._cleanup_finished()
        except Exception as e:
            with self._lock:
                self._tasks[task_id]["status"] = "failed"
                self._tasks[task_id]["error"] = str(e)
                self._tasks[task_id]["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self._cleanup_finished()

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
                self._cleanup_finished()
        except Exception as e:
            with self._lock:
                self._tasks[task_id]["status"] = "failed"
                self._tasks[task_id]["error"] = str(e)
                self._tasks[task_id]["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self._cleanup_finished()


task_manager = TaskManager()
