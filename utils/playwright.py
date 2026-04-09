import json
import os
import time

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, ViewportSize

# Persistent file where we store Playwright's browser state (cookies, localStorage, etc.)
# so that subsequent runs can skip the Reddit login flow.
_SESSION_STATE_PATH = "./video_creation/data/reddit_session_state.json"


def clear_cookie_by_name(context, cookie_cleared_name):
    cookies = context.cookies()
    filtered_cookies = [cookie for cookie in cookies if cookie["name"] != cookie_cleared_name]
    context.clear_cookies()
    context.add_cookies(filtered_cookies)


def _is_logged_in(page: Page) -> bool:
    """Return True if the browser has navigated away from the Reddit login page."""
    return "/login" not in page.url


def _is_session_valid(page: Page) -> bool:
    """Navigate to Reddit and check if the saved session is still authenticated."""
    page.goto("https://www.reddit.com/", timeout=30000)
    page.wait_for_load_state()
    page.wait_for_timeout(3000)
    # If Reddit redirects to a login gate or shows a login button prominently,
    # the session is expired.  A logged-in page has no "/login" in its URL.
    try:
        logged_in = page.evaluate(
            "!!document.querySelector('faceplate-tracker[source=\"nav\"][noun=\"user_menu\"]')"
        )
        return logged_in
    except Exception:
        return False


def _wait_for_login(page: Page, browser: Browser, poll_interval: float = 3.0) -> None:
    """Block until the user is logged in, polling every *poll_interval* seconds.

    The browser window stays open so the user can complete any manual step
    (CAPTCHA, email verification, 2FA, …).  Press Ctrl+C in the terminal to abort.
    """
    from utils.console import print_substep

    print_substep(
        "⚠️  Reddit 登录未完成（可能需要验证码、邮箱验证或手动操作）。\n"
        "请在浏览器窗口中完成登录，程序每 3 秒自动检测状态，无需按 Enter。\n"
        "若要中止程序，请按 Ctrl+C。",
        style="yellow",
    )
    try:
        while not _is_logged_in(page):
            time.sleep(poll_interval)
            # Evaluate a no-op to keep the connection alive and pick up URL changes.
            try:
                page.evaluate("undefined")
            except Exception:
                pass
    except KeyboardInterrupt:
        print_substep("用户中止，程序退出。", style="red")
        browser.close()
        exit()


def _save_session(context: BrowserContext) -> None:
    """Persist the browser context state so the next run can skip login."""
    from utils.console import print_substep

    try:
        context.storage_state(path=_SESSION_STATE_PATH)
        print_substep("浏览器会话已保存，下次启动将自动复用登录状态 ✓", style="bold green")
    except Exception as e:
        print_substep(f"保存会话状态失败: {e}", style="yellow")


def create_reddit_session(playwright: Playwright, W: int, H: int, theme: str):
    """Launch a headed Chromium browser, load Reddit theme cookies, and log in to Reddit.

    The browser runs in **headed (visible) mode** so the user can intervene if Reddit
    requires a CAPTCHA, email/phone verification, or any other manual step.

    If a saved session state exists from a previous run, it will be restored
    automatically.  The function verifies the session is still valid; if not,
    it falls back to the normal login flow.

    This creates a single authenticated session that is shared between the post/comment
    fetching step (reddit/subreddit.py) and the screenshot step
    (video_creation/screenshot_downloader.py), so Reddit login happens only once.

    Args:
        playwright: The sync Playwright instance (from ``sync_playwright()``).
        W: Video/viewport width in pixels.
        H: Video/viewport height in pixels.
        theme: Reddit theme (``'dark'``, ``'light'``, or ``'transparent'``).

    Returns:
        Tuple of ``(browser, context, page)`` – all authenticated and ready to use.
    """
    from utils import settings
    from utils.console import print_substep

    cookie_path = (
        "./video_creation/data/cookie-dark-mode.json"
        if theme in ("dark", "transparent")
        else "./video_creation/data/cookie-light-mode.json"
    )

    # Run in headed mode so the user can see and interact with the browser when needed.
    browser: Browser = playwright.chromium.launch(headless=False)
    dsf = (W // 600) + 1

    # ── Try to restore a saved session first ──────────────────────────────
    if os.path.exists(_SESSION_STATE_PATH):
        print_substep("发现已保存的登录会话，正在验证...")
        try:
            context = browser.new_context(
                locale="en-CA,en;q=0.9",
                color_scheme="dark",
                viewport=ViewportSize(width=W, height=H),
                device_scale_factor=dsf,
                user_agent=(
                    f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    f"(KHTML, like Gecko) Chrome/{browser.version}.0.0.0 Safari/537.36"
                ),
                extra_http_headers={
                    "Dnt": "1",
                    "Sec-Ch-Ua": '"Not A(Brand";v="8", "Chromium";v="132", "Google Chrome";v="132"',
                },
                storage_state=_SESSION_STATE_PATH,
            )
            page = context.new_page()
            if _is_session_valid(page):
                print_substep("Reddit 会话复用成功 ✓", style="bold green")
                return browser, context, page
            # Session expired — close this context and fall through to fresh login.
            print_substep("保存的会话已过期，将重新登录...", style="yellow")
            page.close()
            context.close()
        except Exception as e:
            print_substep(f"恢复会话失败: {e}，将重新登录...", style="yellow")

    # ── Fresh login ───────────────────────────────────────────────────────
    context = browser.new_context(
        locale="en-CA,en;q=0.9",
        color_scheme="dark",
        viewport=ViewportSize(width=W, height=H),
        device_scale_factor=dsf,
        user_agent=(
            f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            f"(KHTML, like Gecko) Chrome/{browser.version}.0.0.0 Safari/537.36"
        ),
        extra_http_headers={
            "Dnt": "1",
            "Sec-Ch-Ua": '"Not A(Brand";v="8", "Chromium";v="132", "Google Chrome";v="132"',
        },
    )

    with open(cookie_path, encoding="utf-8") as f:
        context.add_cookies(json.load(f))

    print_substep("Logging in to Reddit...")
    page: Page = context.new_page()
    page.goto("https://www.reddit.com/login", timeout=0)
    page.set_viewport_size(ViewportSize(width=1920, height=1080))
    page.wait_for_load_state()

    page.locator('input[name="username"]').fill(
        settings.config["reddit"]["creds"]["username"]
    )
    page.locator('input[name="password"]').fill(
        settings.config["reddit"]["creds"]["password"]
    )
    page.get_by_role("button", name="Log In").click()
    page.wait_for_timeout(5000)

    # If still on the login page (CAPTCHA, wrong credentials, verification, etc.),
    # keep polling until the user completes login or presses Ctrl+C.
    if not _is_logged_in(page):
        _wait_for_login(page, browser)

    page.wait_for_load_state()
    if page.locator("#redesign-beta-optin-btn").is_visible():
        clear_cookie_by_name(context, "redesign_optout")
        page.reload()

    # Save session state for future runs
    _save_session(context)

    print_substep("Reddit 登录成功 ✓", style="bold green")
    return browser, context, page
