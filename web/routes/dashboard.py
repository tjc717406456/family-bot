import logging

from flask import Blueprint, render_template
from sqlalchemy import func, case
from db.database import get_session
from db.models import Parent, Member

bp = Blueprint("dashboard", __name__)
logger = logging.getLogger(__name__)

STATUSES = ("pending", "gemini_done", "joined", "failed")


@bp.route("/")
def index():
    with get_session() as session:
        # 聚合查询代替 N+1 遍历
        rows = (
            session.query(
                Parent.id,
                Parent.email,
                Parent.nickname,
                Parent.max_members,
                *[
                    func.count(case((Member.status == s, 1))).label(s)
                    for s in STATUSES
                ],
            )
            .outerjoin(Member)
            .group_by(Parent.id)
            .all()
        )

        total_counts = {s: 0 for s in STATUSES}
        parent_stats = []
        for row in rows:
            counts = {s: getattr(row, s) for s in STATUSES}
            for s in STATUSES:
                total_counts[s] += counts[s]
            parent_stats.append({
                "id": row.id,
                "email": row.email,
                "nickname": row.nickname or "-",
                "max_members": row.max_members,
                "counts": counts,
                "total": sum(counts.values()),
            })

        return render_template(
            "dashboard.html",
            total=total_counts,
            parents=parent_stats,
        )
