from flask import Blueprint, render_template
from db.database import get_session
from db.models import Parent, Member

bp = Blueprint("dashboard", __name__)


@bp.route("/")
def index():
    session = get_session()
    try:
        parents = session.query(Parent).all()
        # 统计各状态总数
        total_counts = {"pending": 0, "gemini_done": 0, "joined": 0, "failed": 0}
        parent_stats = []
        for p in parents:
            counts = {"pending": 0, "gemini_done": 0, "joined": 0, "failed": 0}
            for m in p.members:
                if m.status in counts:
                    counts[m.status] += 1
            for k in total_counts:
                total_counts[k] += counts[k]
            parent_stats.append({
                "id": p.id,
                "email": p.email,
                "nickname": p.nickname or "-",
                "max_members": p.max_members,
                "counts": counts,
                "total": sum(counts.values()),
            })
        return render_template(
            "dashboard.html",
            total=total_counts,
            parents=parent_stats,
        )
    finally:
        session.close()
