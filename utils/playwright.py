import json

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, ViewportSize


def clear_cookie_by_name(context, cookie_cleared_name):
    cookies = context.cookies()
    filtered_cookies = [cookie for cookie in cookies if cookie["name"] != cookie_cleared_name]
    context.clear_cookies()
    context.add_cookies(filtered_cookies)


def create_reddit_session(playwright: Playwright, W: int, H: int, theme: str):
    """Launch a Chromium browser, load Reddit theme cookies, and log in to Reddit.

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

    browser: Browser = playwright.chromium.launch(headless=True)
    dsf = (W // 600) + 1
    context: BrowserContext = browser.new_context(
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

    if page.locator(".AnimatedForm__errorMessage").first.is_visible():
        print_substep(
            "Your reddit credentials are incorrect! Please modify them accordingly in the config.toml file.",
            style="red",
        )
        exit()

    page.wait_for_load_state()
    if page.locator("#redesign-beta-optin-btn").is_visible():
        clear_cookie_by_name(context, "redesign_optout")
        page.reload()

    return browser, context, page
