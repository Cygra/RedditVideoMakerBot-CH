import re
from pathlib import Path
from typing import Final

from playwright.sync_api import ViewportSize
from rich.progress import track

from utils import settings
from utils.console import print_step, print_substep
from utils.videos import save_data

__all__ = ["get_screenshots_of_reddit_posts"]


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

    print_step("Downloading screenshots of reddit posts...")
    reddit_id = re.sub(r"[^\w\s-]", "", reddit_object["thread_id"])
    # ! Make sure the reddit screenshots folder exists
    Path(f"assets/temp/{reddit_id}/png").mkdir(parents=True, exist_ok=True)

    # Get the thread screenshot
    page.goto(reddit_object["thread_url"], timeout=0)
    page.set_viewport_size(ViewportSize(width=W, height=H))
    page.wait_for_load_state()
    page.wait_for_timeout(5000)

    if page.locator(
        "#t3_12hmbug > div > div._3xX726aBn29LDbsDtzr_6E._1Ap4F5maDtT1E1YuCiaO0r.D3IL3FD0RFy_mkKLPwL4 > div > div > button"
    ).is_visible():
        # This means the post is NSFW and requires to click the proceed button.

        print_substep("Post is NSFW. You are spicy...")
        page.locator(
            "#t3_12hmbug > div > div._3xX726aBn29LDbsDtzr_6E._1Ap4F5maDtT1E1YuCiaO0r.D3IL3FD0RFy_mkKLPwL4 > div > div > button"
        ).click()
        page.wait_for_load_state()  # Wait for page to fully load

        # translate code
    if page.locator(
        "#SHORTCUT_FOCUSABLE_DIV > div:nth-child(7) > div > div > div > header > div > div._1m0iFpls1wkPZJVo38-LSh > button > i"
    ).is_visible():
        page.locator(
            "#SHORTCUT_FOCUSABLE_DIV > div:nth-child(7) > div > div > div > header > div > div._1m0iFpls1wkPZJVo38-LSh > button > i"
        ).click()  # Interest popup is showing, this code will close it

    # Append Chinese translation below the original title text
    title_zh = reddit_object.get("thread_title_zh")
    if title_zh:
        print_substep("Appending Chinese translation to title...")
        page.evaluate(
            """tl_content => {
                const el = document.querySelector('[data-adclicklocation="title"] > div > div > h1');
                if (el) {
                    el.appendChild(document.createElement('br'));
                    el.appendChild(document.createTextNode(tl_content));
                }
            }""",
            title_zh,
        )

    postcontentpath = f"assets/temp/{reddit_id}/png/title.png"
    try:
        if settings.config["settings"]["zoom"] != 1:
            # store zoom settings
            zoom = settings.config["settings"]["zoom"]
            # zoom the body of the page
            page.evaluate("document.body.style.zoom=" + str(zoom))
            # as zooming the body doesn't change the properties of the divs, we need to adjust for the zoom
            location = page.locator('[data-test-id="post-content"]').bounding_box()
            for i in location:
                location[i] = float("{:.2f}".format(location[i] * zoom))
            page.screenshot(clip=location, path=postcontentpath)
        else:
            page.locator('[data-test-id="post-content"]').screenshot(path=postcontentpath)
    except Exception as e:
        print_substep("Something went wrong!", style="red")
        resp = input(
            "Something went wrong with making the screenshots! Do you want to skip the post? (y/n) "
        )

        if resp.casefold().startswith("y"):
            save_data("", "", "skipped", reddit_id, "")
            print_substep(
                "The post is successfully skipped! You can now restart the program and this post will skipped.",
                "green",
            )

        resp = input("Do you want the error traceback for debugging purposes? (y/n)")
        if not resp.casefold().startswith("y"):
            exit()

        raise e

    if storymode:
        page.locator('[data-click-id="text"]').first.screenshot(
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

            if page.locator('[data-testid="content-gate"]').is_visible():
                page.locator('[data-testid="content-gate"] button').click()

            page.goto(f"https://new.reddit.com/{comment['comment_url']}")

            # Append Chinese translation below the original comment text
            comment_zh = comment.get("comment_body_zh")
            if comment_zh:
                page.evaluate(
                    """([tl_content, tl_id]) => {
                        const el = document.querySelector('#t1_' + tl_id + ' > div:nth-child(2) > div > div[data-testid="comment"] > div');
                        if (el) {
                            el.appendChild(document.createElement('br'));
                            el.appendChild(document.createTextNode(tl_content));
                        }
                    }""",
                    [comment_zh, comment["comment_id"]],
                )
            try:
                if settings.config["settings"]["zoom"] != 1:
                    # store zoom settings
                    zoom = settings.config["settings"]["zoom"]
                    # zoom the body of the page
                    page.evaluate("document.body.style.zoom=" + str(zoom))
                    # scroll comment into view
                    page.locator(f"#t1_{comment['comment_id']}").scroll_into_view_if_needed()
                    # as zooming the body doesn't change the properties of the divs, we need to adjust for the zoom
                    location = page.locator(f"#t1_{comment['comment_id']}").bounding_box()
                    for i in location:
                        location[i] = float("{:.2f}".format(location[i] * zoom))
                    page.screenshot(
                        clip=location,
                        path=f"assets/temp/{reddit_id}/png/comment_{idx}.png",
                    )
                else:
                    page.locator(f"#t1_{comment['comment_id']}").screenshot(
                        path=f"assets/temp/{reddit_id}/png/comment_{idx}.png"
                    )
            except TimeoutError:
                del reddit_object["comments"]
                screenshot_num += 1
                print("TimeoutError: Skipping screenshot...")
                continue

    print_substep("Screenshots downloaded Successfully.", style="bold green")
