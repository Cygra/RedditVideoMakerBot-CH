import json
import os

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, ViewportSize

# Persistent file where we store Playwright's browser state (cookies, localStorage, etc.)
# so that subsequent runs can skip the Reddit login flow.
_SESSION_STATE_PATH = "./video_creation/data/reddit_session_state.json"


def clear_cookie_by_name(context, cookie_cleared_name):
    cookies = context.cookies()
    filtered_cookies = [cookie for cookie in cookies if cookie["name"] != cookie_cleared_name]
    context.clear_cookies()
    context.add_cookies(filtered_cookies)


def _confirm_in_terminal(prompt: str) -> bool:
    """Show *prompt* and return True if the user presses Enter (or 'y'), False if 'n'."""
    try:
        answer = input(prompt).strip().lower()
        return answer != "n"
    except (EOFError, KeyboardInterrupt):
        return False


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

    The browser runs in **headed (visible) mode** so the user can visually confirm
    the login state and intervene if Reddit requires a CAPTCHA, email/phone
    verification, or any other manual step.

    If a saved session state exists from a previous run, it will be restored and
    the user is asked to confirm it is still valid.  If not, the function falls
    back to an automatic login attempt followed by another user confirmation.

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

    proxy_url = settings.config["settings"].get("proxy", "").strip()
    launch_kwargs = {"headless": False}
    if proxy_url:
        launch_kwargs["proxy"] = {"server": proxy_url}

    # Run in headed mode so the user can see and interact with the browser when needed.
    browser: Browser = playwright.chromium.launch(**launch_kwargs)
    dsf = (W // 600) + 1

    def _make_context(**extra) -> BrowserContext:
        return browser.new_context(
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
            **extra,
        )

    # ── Try to restore a saved session first ──────────────────────────────
    if os.path.exists(_SESSION_STATE_PATH):
        print_substep("发现已保存的登录会话，正在加载...")
        try:
            context = _make_context(storage_state=_SESSION_STATE_PATH)
            page: Page = context.new_page()
            page.goto("https://www.reddit.com/", timeout=0)
            page.wait_for_load_state()

            print_substep(
                "✅ 已在浏览器中打开 Reddit。\n"
                "请查看浏览器窗口，确认是否已正常登录。\n"
                "  → 已登录：直接按 Enter 继续\n"
                "  → 未登录 / 需重新登录：输入 n 后按 Enter",
                style="yellow",
            )
            if _confirm_in_terminal("已登录？[Enter / n]: "):
                print_substep("Reddit 会话复用成功 ✓", style="bold green")
                return browser, context, page

            # User said no — discard this context and fall through to fresh login.
            print_substep("将重新执行登录流程...", style="yellow")
            page.close()
            context.close()
        except Exception as e:
            print_substep(f"恢复会话失败: {e}，将重新登录...", style="yellow")

    # ── Fresh login ───────────────────────────────────────────────────────
    context = _make_context()

    with open(cookie_path, encoding="utf-8") as f:
        context.add_cookies(json.load(f))

    print_substep("正在尝试自动登录 Reddit...")
    page = context.new_page()
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

    page.wait_for_load_state()
    if page.locator("#redesign-beta-optin-btn").is_visible():
        clear_cookie_by_name(context, "redesign_optout")
        page.reload()

    print_substep(
        "⚠️  程序已尝试自动登录。\n"
        "请查看浏览器窗口，确认登录状态（如遇验证码、邮箱验证等，请手动完成后再回来）。\n"
        "  → 已成功登录：直接按 Enter 继续\n"
        "  → 要退出程序：按 Ctrl+C",
        style="yellow",
    )
    try:
        input("已登录？按 Enter 继续: ")
    except KeyboardInterrupt:
        print_substep("用户中止，程序退出。", style="red")
        browser.close()
        exit()

    # Save session state for future runs
    _save_session(context)

    print_substep("Reddit 登录成功 ✓", style="bold green")
    return browser, context, page

