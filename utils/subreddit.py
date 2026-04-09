import json
from os.path import exists

import requests

from utils import settings
from utils.ai_methods import sort_by_similarity
from utils.console import print_substep

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36",
}


def _contains_blocked_words(text: str) -> bool:
    """Returns True if the text contains any blocked words from config."""
    blocked_raw = settings.config["reddit"]["thread"].get("blocked_words", "")
    if not blocked_raw:
        return False
    blocked = [w.strip().lower() for w in blocked_raw.split(",") if w.strip()]
    text_lower = text.lower()
    return any(word in text_lower for word in blocked)


def _fetch_top_posts(subreddit_name: str, time_filter: str = "day", limit: int = 50) -> list:
    """Fetch top posts from a subreddit using the public JSON API.

    Args:
        subreddit_name: Name of the subreddit (without r/ prefix).
        time_filter: Time filter ('day', 'hour', 'week', 'month', 'year', 'all').
        limit: Maximum number of posts to return.

    Returns:
        List of post data dicts.
    """
    url = f"https://www.reddit.com/r/{subreddit_name}/top.json"
    params = {"t": time_filter, "limit": limit}
    resp = requests.get(url, headers=_HEADERS, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return [child["data"] for child in data["data"]["children"]]


def get_subreddit_undone(submissions: list, subreddit_name: str, times_checked=0, similarity_scores=None):
    """Finds a submission from the list that hasn't been turned into a video yet.

    Args:
        submissions (list): List of post dicts that are going to potentially be generated into a video
        subreddit_name (str): Name of the chosen subreddit

    Returns:
        Any: The submission that has not been done
    """
    # Second try of getting a valid Submission
    if times_checked and settings.config["ai"]["ai_similarity_enabled"]:
        print("Sorting based on similarity for a different date filter and thread limit..")
        submissions = sort_by_similarity(
            submissions, keywords=settings.config["ai"]["ai_similarity_enabled"]
        )

    # recursively checks if the top submission in the list was already done.
    if not exists("./video_creation/data/videos.json"):
        with open("./video_creation/data/videos.json", "w+") as f:
            json.dump([], f)
    with open("./video_creation/data/videos.json", "r", encoding="utf-8") as done_vids_raw:
        done_videos = json.load(done_vids_raw)
    for i, submission in enumerate(submissions):
        if already_done(done_videos, submission):
            continue
        if submission["over_18"]:
            try:
                if not settings.config["settings"]["allow_nsfw"]:
                    print_substep("NSFW Post Detected. Skipping...")
                    continue
            except AttributeError:
                print_substep("NSFW settings not defined. Skipping NSFW post...")
        if submission["stickied"]:
            print_substep("This post was pinned by moderators. Skipping...")
            continue
        if _contains_blocked_words(submission["title"] + " " + (submission["selftext"] or "")):
            print_substep("Post contains a blocked word. Skipping...")
            continue
        if (
            submission["num_comments"] <= int(settings.config["reddit"]["thread"]["min_comments"])
            and not settings.config["settings"]["storymode"]
        ):
            print_substep(
                f'This post has under the specified minimum of comments ({settings.config["reddit"]["thread"]["min_comments"]}). Skipping...'
            )
            continue
        if settings.config["settings"]["storymode"]:
            if not submission["selftext"]:
                print_substep("You are trying to use story mode on post with no post text")
                continue
            else:
                # Check for the length of the post text
                if len(submission["selftext"]) > (
                    settings.config["settings"]["storymode_max_length"] or 2000
                ):
                    print_substep(
                        f"Post is too long ({len(submission['selftext'])}), try with a different post. ({settings.config['settings']['storymode_max_length']} character limit)"
                    )
                    continue
                elif len(submission["selftext"]) < 30:
                    continue
        if settings.config["settings"]["storymode"] and not submission["is_self"]:
            continue
        if similarity_scores is not None:
            return submission, similarity_scores[i].item()
        return submission
    print("all submissions have been done going by top submission order")
    VALID_TIME_FILTERS = [
        "day",
        "hour",
        "month",
        "week",
        "year",
        "all",
    ]  # set doesn't have __getitem__
    index = times_checked + 1
    if index == len(VALID_TIME_FILTERS):
        print("All submissions have been done.")

    return get_subreddit_undone(
        _fetch_top_posts(
            subreddit_name,
            time_filter=VALID_TIME_FILTERS[index],
            limit=(50 if int(index) == 0 else index + 1 * 50),
        ),
        subreddit_name,
        times_checked=index,
    )  # all the videos in hot have already been done


def already_done(done_videos: list, submission: dict) -> bool:
    """Checks to see if the given submission is in the list of videos

    Args:
        done_videos (list): Finished videos
        submission (dict): The submission dict

    Returns:
        Boolean: Whether the video was found in the list
    """

    for video in done_videos:
        if video["id"] == submission["id"]:
            return True
    return False
