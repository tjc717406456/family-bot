import logging
import os
from datetime import datetime

from config import SCREENSHOT_DIR

logger = logging.getLogger(__name__)


async def take_screenshot(page, member, tag: str):
    """截图保存（公共方法）"""
    filename = f"{member.id}_{member.email}_{tag}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    path = os.path.join(SCREENSHOT_DIR, filename)
    try:
        await page.screenshot(path=path)
        logger.info("截图已保存: %s", path)
    except Exception:
        logger.debug("截图保存失败", exc_info=True)


def mark_failed(session, member, reason: str):
    """标记成员失败并提交"""
    member.status = "failed"
    member.error_msg = reason
    member.updated_at = datetime.now()
    session.commit()
    logger.error("失败: %s - %s", member.email, reason)


def mark_error(session, member, reason: str):
    """仅记录错误信息（不改变 status）"""
    member.error_msg = reason
    member.updated_at = datetime.now()
    session.commit()
    logger.error("错误: %s - %s", member.email, reason)
