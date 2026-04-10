import re
from pathlib import Path
from typing import Final

from playwright.sync_api import ViewportSize
from rich.progress import track

from utils import settings
from utils.console import print_step, print_substep
from utils.videos import save_data

__all__ = ["get_screenshots_of_reddit_posts"]

# ── Selector constants for the current Reddit redesign (shreddit) ─────────
_SEL_POST = "shreddit-post"
_SEL_TITLE = 'h1[slot="title"]'
_SEL_COMMENT = 'shreddit-comment[thingid="t1_{cid}"]'
_SEL_COMMENT_BODY = "#t1_{cid}-comment-rtjson-content"


def get_screenshots_of_reddit_posts(reddit_object: dict, screenshot_num: int, page):
    """Downloads screenshots of reddit posts as seen on the web. Downloads to assets/temp/png

    Args:
        reddit_object (Dict): Reddit object received from reddit/subreddit.py
        screenshot_num (int): Number of screenshots to download
        page: Authenticated Playwright Page created by utils.playwright.create_reddit_session.
              The caller is responsible for opening/closing the browser.
    """
    # settings values
    W: Final[int] = int(settings.config["settings"]["resolution_w"])
    H: Final[int] = int(settings.config["settings"]["resolution_h"])
    storymode: Final[bool] = settings.config["settings"]["storymode"]

    translation_cfg = settings.config.get("settings", {}).get("translation", {})
    chinese_overlay: Final[bool] = translation_cfg.get("screenshot_chinese_overlay", True)

    print_step("正在下载 Reddit 帖子截图...")
    reddit_id = re.sub(r"[^\w\s-]", "", reddit_object["thread_id"])
    # ! Make sure the reddit screenshots folder exists
    Path(f"assets/temp/{reddit_id}/png").mkdir(parents=True, exist_ok=True)

    # Get the thread screenshot
    page.goto(reddit_object["thread_url"], timeout=0)
    page.set_viewport_size(ViewportSize(width=W, height=H))
    page.wait_for_load_state()
    page.wait_for_timeout(5000)

    # Dismiss any NSFW interstitial overlay
    try:
        nsfw_btn = page.locator("button:has-text('Yes')", has=page.locator("text=Are you sure"))
        if nsfw_btn.first.is_visible(timeout=2000):
            print_substep("检测到 NSFW 帖子，你口味不错...")
            nsfw_btn.first.click()
            page.wait_for_load_state()
    except Exception:
        pass

    # Dismiss any popup / overlay that might block the content
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)
    except Exception:
        pass

    # Append Chinese translation below the original title text
    if chinese_overlay:
        title_zh = reddit_object.get("thread_title_zh")
        if title_zh:
            print_substep("正在为标题追加中文翻译...")
            page.evaluate(
                """tl_content => {
                    const el = document.querySelector('h1[slot="title"]');
                    if (el) {
                        const original = el.textContent;
                        el.innerHTML =
                            '<div>' + original + '</div>' +
                            '<div style="margin-top:8px;font-size:0.9em">' + tl_content + '</div>';
                    }
                }""",
                title_zh,
            )

    postcontentpath = f"assets/temp/{reddit_id}/png/title.png"
    try:
        if settings.config["settings"]["zoom"] != 1:
            zoom = settings.config["settings"]["zoom"]
            page.evaluate("document.body.style.zoom=" + str(zoom))
            location = page.locator(_SEL_POST).bounding_box()
            for i in location:
                location[i] = float("{:.2f}".format(location[i] * zoom))
            page.screenshot(clip=location, path=postcontentpath)
        else:
            page.locator(_SEL_POST).screenshot(path=postcontentpath)
    except Exception as e:
        print_substep("截图过程中出现问题！", style="red")
        resp = input(
            "Something went wrong with making the screenshots! Do you want to skip the post? (y/n) "
        )

        if resp.casefold().startswith("y"):
            save_data("", "", "skipped", reddit_id, "")
            print_substep(
                "该帖子已成功跳过！重新启动程序后将自动跳过此帖。",
                "green",
            )

        resp = input("Do you want the error traceback for debugging purposes? (y/n)")
        if not resp.casefold().startswith("y"):
            exit()

        raise e

    if storymode:
        # In the new design, post body text lives inside shreddit-post
        page.locator(f'{_SEL_POST} div[slot="text-body"]').first.screenshot(
            path=f"assets/temp/{reddit_id}/png/story_content.png"
        )
    else:
        for idx, comment in enumerate(
            track(
                reddit_object["comments"][:screenshot_num],
                "Downloading screenshots...",
            )
        ):
            # Stop if we have reached the screenshot_num
            if idx >= screenshot_num:
                break

            comment_url = comment["comment_url"]
            page.goto(f"https://www.reddit.com{comment_url}", timeout=0)
            page.wait_for_load_state()
            page.wait_for_timeout(3000)

            cid = comment["comment_id"]
            comment_sel = _SEL_COMMENT.format(cid=cid)
            comment_body_sel = _SEL_COMMENT_BODY.format(cid=cid)

            # Append Chinese translation below the original comment text
            if chinese_overlay:
                comment_zh = comment.get("comment_body_zh")
                if comment_zh:
                    page.evaluate(
                        """([tl_content, bodySelector]) => {
                            const el = document.querySelector(bodySelector);
                            if (el) {
                                const zhDiv = document.createElement('div');
                                zhDiv.style.marginTop = '6px';
                                zhDiv.style.fontSize = '0.95em';
                                zhDiv.textContent = tl_content;
                                el.appendChild(zhDiv);
                            }
                        }""",
                        [comment_zh, comment_body_sel],
                    )

            # Hide nested replies before screenshotting
            page.evaluate(
                """cid => {
                    const el = document.querySelector(`shreddit-comment[thingid="t1_${cid}"]`);
                    if (el) {
                        el.querySelectorAll('shreddit-comment').forEach(r => r.style.display = 'none');
                    }
                }""",
                cid,
            )

            try:
                if settings.config["settings"]["zoom"] != 1:
                    zoom = settings.config["settings"]["zoom"]
                    page.evaluate("document.body.style.zoom=" + str(zoom))
                    page.locator(comment_sel).scroll_into_view_if_needed()
                    location = page.locator(comment_sel).bounding_box()
                    for i in location:
                        location[i] = float("{:.2f}".format(location[i] * zoom))
                    page.screenshot(
                        clip=location,
                        path=f"assets/temp/{reddit_id}/png/comment_{idx}.png",
                    )
                else:
                    page.locator(comment_sel).screenshot(
                        path=f"assets/temp/{reddit_id}/png/comment_{idx}.png"
                    )
            except TimeoutError:
                del reddit_object["comments"]
                screenshot_num += 1
                print("TimeoutError: Skipping screenshot...")
                # Restore nested replies before continuing
                page.evaluate(
                    """cid => {
                        const el = document.querySelector(`shreddit-comment[thingid="t1_${cid}"]`);
                        if (el) {
                            el.querySelectorAll('shreddit-comment').forEach(r => r.style.display = '');
                        }
                    }""",
                    cid,
                )
                continue

            # Restore nested replies
            page.evaluate(
                """cid => {
                    const el = document.querySelector(`shreddit-comment[thingid="t1_${cid}"]`);
                    if (el) {
                        el.querySelectorAll('shreddit-comment').forEach(r => r.style.display = '');
                    }
                }""",
                cid,
            )

    print_substep("截图下载完成。", style="bold green")
