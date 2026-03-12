import asyncio
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from config import MAX_CONCURRENT_TASKS

logger = logging.getLogger(__name__)

MAX_FINISHED_TASKS = 100


class TaskManager:
    """后台任务管理器，线程池执行自动化任务"""

    _instance = None
    _init_lock = threading.Lock()

    def __new__(cls):
        with cls._init_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._tasks = {}
                cls._instance._lock = threading.Lock()
                cls._instance._counter = 0
                cls._instance._pool = ThreadPoolExecutor(
                    max_workers=MAX_CONCURRENT_TASKS,
                    thread_name_prefix="task",
                )
            return cls._instance

    def _gen_id(self):
        with self._lock:
            self._counter += 1
            return f"task_{int(time.time() * 1000)}_{self._counter}"

    def _cleanup_finished(self):
        """清理已完成的旧任务，保留最近 MAX_FINISHED_TASKS 个（调用方须持锁）"""
        finished = [
            (tid, t) for tid, t in self._tasks.items()
            if t["status"] in ("done", "failed")
        ]
        if len(finished) <= MAX_FINISHED_TASKS:
            return
        finished.sort(key=lambda x: x[1].get("finished_at", ""))
        for tid, _ in finished[:-MAX_FINISHED_TASKS]:
            del self._tasks[tid]

    def _finish_task(self, task_id, status, error=None):
        """统一结束任务的状态更新"""
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                task["status"] = status
                task["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if error:
                    task["error"] = str(error)
                self._cleanup_finished()

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

    def _create_task(self, task_type, member_id, email, **extra):
        task_id = self._gen_id()
        with self._lock:
            self._tasks[task_id] = {
                "type": task_type,
                "member_id": member_id,
                "email": email,
                "status": "running",
                "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "finished_at": None,
                "error": None,
                **extra,
            }
        return task_id

    def run_member(self, member_id: int, email: str):
        """执行单个成员"""
        task_id = self._create_task("member", member_id, email)
        self._pool.submit(self._exec, task_id, [member_id])
        return task_id

    def run_parent(self, parent_id: int, parent_email: str):
        """执行某家长下所有待处理成员（每个成员独立任务并行执行）"""
        from db.database import get_session
        from db.models import Member

        with get_session() as session:
            members = session.query(Member).filter(
                Member.parent_id == parent_id,
                Member.status.in_(["pending", "gemini_done"])
            ).all()
            member_info = [(m.id, m.email) for m in members]

        if not member_info:
            return []

        return [self.run_member(mid, email) for mid, email in member_info]

    def run_all(self):
        """执行所有待处理成员（每个成员独立任务并行执行）"""
        from db.database import get_session
        from db.models import Member

        with get_session() as session:
            members = session.query(Member).filter(
                Member.status.in_(["pending", "gemini_done"])
            ).all()
            member_info = [(m.id, m.email) for m in members]

        if not member_info:
            return []

        return [self.run_member(mid, email) for mid, email in member_info]

    def run_open_browser(self, member_id: int, email: str):
        """打开成员浏览器并自动登录"""
        task_id = self._create_task("open_browser", member_id, email)
        self._pool.submit(self._exec_open_browser, task_id, member_id)
        return task_id

    def _exec_open_browser(self, task_id: str, member_id: int):
        from automation.open_browser import open_browser_for_member
        try:
            asyncio.run(open_browser_for_member(member_id))
            self._finish_task(task_id, "done")
        except Exception as e:
            logger.exception("打开浏览器失败: member_id=%s", member_id)
            self._finish_task(task_id, "failed", error=e)

    def run_antigravity(self, member_id: int, email: str, oauth_url: str):
        """执行 Antigravity OAuth 登录"""
        task_id = self._create_task("antigravity", member_id, email, oauth_url=oauth_url)
        self._pool.submit(self._exec_antigravity, task_id, member_id, oauth_url)
        return task_id

    def _exec_antigravity(self, task_id: str, member_id: int, oauth_url: str):
        """线程内执行 Antigravity 登录"""
        from automation.antigravity_login import antigravity_login

        try:
            result = asyncio.run(antigravity_login(member_id, oauth_url))
            if result:
                self._finish_task(task_id, "done")
            else:
                self._finish_task(task_id, "failed", error="Antigravity 登录未成功")
        except Exception as e:
            logger.exception("Antigravity 登录失败: member_id=%s", member_id)
            self._finish_task(task_id, "failed", error=e)

    def run_appeal(self, member_id: int, email: str):
        """打开成员浏览器并访问申诉表单"""
        task_id = self._create_task("appeal", member_id, email)
        self._pool.submit(self._exec_appeal, task_id, member_id)
        return task_id

    def _exec_appeal(self, task_id: str, member_id: int):
        from automation.appeal_form import open_appeal_form
        try:
            asyncio.run(open_appeal_form(member_id))
            self._finish_task(task_id, "done")
        except Exception as e:
            logger.exception("认罪表单失败: member_id=%s", member_id)
            self._finish_task(task_id, "failed", error=e)

    def _exec(self, task_id: str, member_ids: list):
        """在线程内逐个执行成员流程"""
        from cli.auto_cmd import run_member_flow

        try:
            for i, mid in enumerate(member_ids):
                logger.info("_exec 开始执行成员: member_id=%s, task_id=%s", mid, task_id)
                asyncio.run(run_member_flow(mid))
                logger.info("_exec 成员执行完成: member_id=%s", mid)
                with self._lock:
                    self._tasks[task_id]["progress"] = i + 1
            self._finish_task(task_id, "done")
        except Exception as e:
            logger.exception("成员流程执行失败: task_id=%s", task_id)
            self._finish_task(task_id, "failed", error=e)


task_manager = TaskManager()
