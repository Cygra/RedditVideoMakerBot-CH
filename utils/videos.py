import json
import time

from utils import settings
from utils.console import print_step


def check_done(
    redditobj: dict,
) -> dict:
    # don't set this to be run anyplace that isn't subreddit.py bc of inspect stack
    """Checks if the chosen post has already been generated

    Args:
        redditobj (dict): Reddit post dict gotten from reddit/subreddit.py

    Returns:
        dict|None: Reddit post dict in args
    """
    with open("./video_creation/data/videos.json", "r", encoding="utf-8") as done_vids_raw:
        done_videos = json.load(done_vids_raw)
    for video in done_videos:
        if video["id"] == redditobj["id"]:
            if settings.config["reddit"]["thread"]["post_id"]:
                print_step(
                    "该视频之前已生成过，但由于在配置文件中明确指定了帖子 ID，程序将继续处理"
                )
                return redditobj
            print_step("当前帖子已处理过，正在获取新帖子")
            return None
    return redditobj


def save_data(subreddit: str, filename: str, reddit_title: str, reddit_id: str, credit: str):
    """Saves the videos that have already been generated to a JSON file in video_creation/data/videos.json

    Args:
        filename (str): The finished video title name
        @param subreddit:
        @param filename:
        @param reddit_id:
        @param reddit_title:
    """
    with open("./video_creation/data/videos.json", "r+", encoding="utf-8") as raw_vids:
        done_vids = json.load(raw_vids)
        if reddit_id in [video["id"] for video in done_vids]:
            return  # video already done but was specified to continue anyway in the config file
        payload = {
            "subreddit": subreddit,
            "id": reddit_id,
            "time": str(int(time.time())),
            "background_credit": credit,
            "reddit_title": reddit_title,
            "filename": filename,
        }
        done_vids.append(payload)
        raw_vids.seek(0)
        json.dump(done_vids, raw_vids, ensure_ascii=False, indent=4)
