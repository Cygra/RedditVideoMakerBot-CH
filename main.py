#!/usr/bin/env python
import math
import sys
from os import name
from pathlib import Path
from subprocess import Popen
from typing import Dict, NoReturn

from reddit.subreddit import get_subreddit_threads
from utils import settings
from utils.cleanup import cleanup
from utils.console import print_markdown, print_step, print_substep
from utils.ffmpeg_install import ffmpeg_install
from utils.id import extract_id
from utils.playwright import create_reddit_session
from utils.version import checkversion
from video_creation.background import (
    chop_background,
    download_background_audio,
    download_background_video,
    get_background_config,
)
from video_creation.final_video import make_final_video
from video_creation.screenshot_downloader import get_screenshots_of_reddit_posts
from video_creation.voices import save_text_to_mp3
from playwright.sync_api import sync_playwright

__VERSION__ = "3.4.0"

print(
    """
██████╗ ███████╗██████╗ ██████╗ ██╗████████╗    ██╗   ██╗██╗██████╗ ███████╗ ██████╗     ███╗   ███╗ █████╗ ██╗  ██╗███████╗██████╗
██╔══██╗██╔════╝██╔══██╗██╔══██╗██║╚══██╔══╝    ██║   ██║██║██╔══██╗██╔════╝██╔═══██╗    ████╗ ████║██╔══██╗██║ ██╔╝██╔════╝██╔══██╗
██████╔╝█████╗  ██║  ██║██║  ██║██║   ██║       ██║   ██║██║██║  ██║█████╗  ██║   ██║    ██╔████╔██║███████║█████╔╝ █████╗  ██████╔╝
██╔══██╗██╔══╝  ██║  ██║██║  ██║██║   ██║       ╚██╗ ██╔╝██║██║  ██║██╔══╝  ██║   ██║    ██║╚██╔╝██║██╔══██║██╔═██╗ ██╔══╝  ██╔══██╗
██║  ██║███████╗██████╔╝██████╔╝██║   ██║        ╚████╔╝ ██║██████╔╝███████╗╚██████╔╝    ██║ ╚═╝ ██║██║  ██║██║  ██╗███████╗██║  ██║
╚═╝  ╚═╝╚══════╝╚═════╝ ╚═════╝ ╚═╝   ╚═╝         ╚═══╝  ╚═╝╚═════╝ ╚══════╝ ╚═════╝     ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝
"""
)
print_markdown(
    "### 感谢使用 Reddit 视频生成器（中文版）！如有问题，请在 GitHub 上提交 Issue。"
)
checkversion(__VERSION__)

reddit_id: str
reddit_object: Dict[str, str | list]


def main(POST_ID=None, page=None, _owns_browser: bool = True, _browser=None) -> None:
    """Run the full pipeline for one video.

    Args:
        POST_ID: Optional specific Reddit post ID to process.
        page: An already-authenticated Playwright Page to reuse. When provided,
              the function will NOT close the browser when it finishes.
        _owns_browser: Internal flag — False when the caller manages the
                       browser lifecycle (e.g. run_many).
        _browser: Internal reference to the browser so we can close it when
                  this function owns it.
    """
    global reddit_id, reddit_object

    W = int(settings.config["settings"]["resolution_w"])
    H = int(settings.config["settings"]["resolution_h"])
    theme = settings.config["settings"]["theme"]

    if page is None:
        # Single-run mode: start and own a fresh browser session.
        _playwright_ctx = sync_playwright().start()
        _browser, _context, page = create_reddit_session(_playwright_ctx, W, H, theme)
        _owns_browser = True
    else:
        _playwright_ctx = None
        _owns_browser = False

    try:
        reddit_object = get_subreddit_threads(POST_ID, page=page)
        reddit_id = extract_id(reddit_object)
        print_substep(f"帖子 ID 为 {reddit_id}", style="bold blue")
        length, number_of_comments = save_text_to_mp3(reddit_object)
        length = math.ceil(length)
        get_screenshots_of_reddit_posts(reddit_object, number_of_comments, page=page)
    finally:
        if _owns_browser and _browser is not None:
            _browser.close()
        if _owns_browser and _playwright_ctx is not None:
            _playwright_ctx.stop()

    bg_config = {
        "video": get_background_config("video"),
        "audio": get_background_config("audio"),
    }
    download_background_video(bg_config["video"])
    download_background_audio(bg_config["audio"])
    chop_background(bg_config, length, reddit_object)
    make_final_video(number_of_comments, length, reddit_object, bg_config)


def run_many(times) -> None:
    W = int(settings.config["settings"]["resolution_w"])
    H = int(settings.config["settings"]["resolution_h"])
    theme = settings.config["settings"]["theme"]

    with sync_playwright() as p:
        browser, _context, page = create_reddit_session(p, W, H, theme)
        try:
            for x in range(1, times + 1):
                print_step(f'正在处理第 {x}/{times} 个视频')
                main(page=page, _owns_browser=False)
                Popen("cls" if name == "nt" else "clear", shell=True).wait()
        finally:
            browser.close()


def shutdown() -> NoReturn:
    if "reddit_id" in globals():
        print_markdown("## Clearing temp files")
        cleanup(reddit_id)

    print("Exiting...")
    sys.exit()


if __name__ == "__main__":
    if sys.version_info.major != 3 or sys.version_info.minor not in [10, 11, 12, 13, 14]:
        print(
            "该程序需要 Python 3.10 或更高版本（3.10/3.11/3.12/3.13/3.14）。请安装对应版本后重试。"
        )
        sys.exit()
    ffmpeg_install()
    directory = Path().absolute()
    config = settings.check_toml(
        f"{directory}/utils/.config.template.toml", f"{directory}/config.toml"
    )
    config is False and sys.exit()

    try:
        if config["reddit"]["thread"]["post_id"]:
            post_ids = config["reddit"]["thread"]["post_id"].split("+")
            W = int(config["settings"]["resolution_w"])
            H = int(config["settings"]["resolution_h"])
            theme = config["settings"]["theme"]
            with sync_playwright() as p:
                browser, _context, page = create_reddit_session(p, W, H, theme)
                try:
                    for index, post_id in enumerate(post_ids, start=1):
                        print_step(f'正在处理第 {index}/{len(post_ids)} 个帖子')
                        main(post_id, page=page, _owns_browser=False)
                        Popen("cls" if name == "nt" else "clear", shell=True).wait()
                finally:
                    browser.close()
        elif config["settings"]["times_to_run"]:
            run_many(config["settings"]["times_to_run"])
        else:
            main()
    except KeyboardInterrupt:
        shutdown()
    except Exception as err:
        print_step(
            f"抱歉，程序遇到了问题！请重试，如问题持续请在 GitHub 或 Discord 社区反馈。\n"
            f"版本: {__VERSION__} \n"
            f"错误: {err} \n"
        )
        raise err
