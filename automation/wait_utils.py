import logging

from playwright.async_api import Page

logger = logging.getLogger(__name__)


async def wait_for_networkidle(page: Page, timeout=8000):
    """等待网络空闲，超时不抛异常"""
    try:
        await page.wait_for_load_state("networkidle", timeout=timeout)
    except TimeoutError:
        pass
    except Exception:
        logger.debug("wait_for_networkidle 异常", exc_info=True)


async def wait_for_url_change(page: Page, old_url: str, timeout=10000):
    """等待 URL 变化，变了立刻返回"""
    try:
        await page.wait_for_function(
            "(old) => window.location.href !== old",
            old_url,
            timeout=timeout,
        )
    except TimeoutError:
        pass
    except Exception:
        logger.debug("wait_for_url_change 异常", exc_info=True)


async def wait_for_element_hidden(page: Page, locator, timeout=5000):
    """等待元素消失/隐藏"""
    try:
        await locator.wait_for(state="hidden", timeout=timeout)
    except TimeoutError:
        pass
    except Exception:
        logger.debug("wait_for_element_hidden 异常", exc_info=True)


async def click_and_wait_hidden(page: Page, locator, timeout=5000):
    """点击元素后等待它消失（适用于弹窗关闭场景）"""
    await locator.click()
    await wait_for_element_hidden(page, locator, timeout)


async def click_and_wait_nav(page: Page, locator, timeout=10000):
    """点击元素后等待页面导航"""
    old_url = page.url
    await locator.click()
    await wait_for_url_change(page, old_url, timeout)
