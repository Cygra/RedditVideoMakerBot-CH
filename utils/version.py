import requests

from utils.console import print_step


def checkversion(__VERSION__: str):
    response = requests.get(
        "https://api.github.com/repos/elebumm/RedditVideoMakerBot/releases/latest"
    )
    latestversion = response.json()["tag_name"]
    if __VERSION__ == latestversion:
        print_step(f"您正在使用最新版本 ({__VERSION__})")
        return True
    elif __VERSION__ < latestversion:
        print_step(
            f"您正在使用旧版本 ({__VERSION__})。请从 https://github.com/elebumm/RedditVideoMakerBot/releases/latest 下载最新版本 ({latestversion})"
        )
    else:
        print_step(
            f"欢迎使用测试版本 ({__VERSION__})，感谢参与测试，如发现 Bug 请随时反馈。"
        )
