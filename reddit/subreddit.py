import re

import requests

from utils import settings
from utils.ai_methods import sort_by_similarity
from utils.console import print_step, print_substep
from utils.posttextparser import posttextparser
from utils.subreddit import _contains_blocked_words, get_subreddit_undone
from utils.translator import translate_reddit_object
from utils.videos import check_done
from utils.voice import sanitize_text

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36",
}


def _fetch_subreddit_posts(subreddit_name: str, sort: str = "hot", limit: int = 25, time_filter: str = None) -> list:
    """Fetch posts from a subreddit using the public JSON API.

    Args:
        subreddit_name: Name of the subreddit (without r/ prefix).
        sort: Sort order ('hot', 'top', 'new').
        limit: Maximum number of posts to return.
        time_filter: Time filter for 'top' sort ('day', 'week', 'month', 'year', 'all').

    Returns:
        List of post data dicts.
    """
    url = f"https://www.reddit.com/r/{subreddit_name}/{sort}.json"
    params = {"limit": limit}
    if sort == "top" and time_filter:
        params["t"] = time_filter
    resp = requests.get(url, headers=_HEADERS, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return [child["data"] for child in data["data"]["children"]]


def _fetch_post_and_comments(post_id: str, comment_limit: int = 100) -> tuple:
    """Fetch a single post and its comments using the public JSON API.

    Args:
        post_id: Reddit post ID (e.g. '1sg3sdt').
        comment_limit: Maximum number of comments to return.

    Returns:
        Tuple of (post_dict, list_of_comment_dicts).
    """
    url = f"https://www.reddit.com/comments/{post_id}.json"
    params = {"limit": comment_limit}
    resp = requests.get(url, headers=_HEADERS, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    post = data[0]["data"]["children"][0]["data"]

    comments = []
    for child in data[1]["data"]["children"]:
        if child["kind"] == "t1":
            comments.append(child["data"])
    return post, comments


def get_subreddit_threads(POST_ID: str):
    """
    Returns a list of threads from the AskReddit subreddit.
    """

    content = {}
    comments = None

    # Ask user for subreddit input
    print_step("Getting subreddit threads...")
    similarity_score = 0
    if not settings.config["reddit"]["thread"][
        "subreddit"
    ]:  # note to user. you can have multiple subreddits via '+' separated names
        try:
            subreddit_name = re.sub(r"r\/", "", input("What subreddit would you like to pull from? "))
        except ValueError:
            subreddit_name = "askreddit"
            print_substep("Subreddit not defined. Using AskReddit.")
    else:
        sub = settings.config["reddit"]["thread"]["subreddit"]
        print_substep(f"Using subreddit: r/{sub} from TOML config")
        subreddit_name = sub
        if str(subreddit_name).casefold().startswith("r/"):  # removes the r/ from the input
            subreddit_name = subreddit_name[2:]

    if POST_ID:  # would only be called if there are multiple queued posts
        submission, comments = _fetch_post_and_comments(POST_ID)

    elif (
        settings.config["reddit"]["thread"]["post_id"]
        and len(str(settings.config["reddit"]["thread"]["post_id"]).split("+")) == 1
    ):
        submission, comments = _fetch_post_and_comments(
            settings.config["reddit"]["thread"]["post_id"]
        )
    elif settings.config["ai"]["ai_similarity_enabled"]:  # ai sorting based on comparison
        threads = _fetch_subreddit_posts(subreddit_name, sort="hot", limit=50)
        keywords = settings.config["ai"]["ai_similarity_keywords"].split(",")
        keywords = [keyword.strip() for keyword in keywords]
        # Reformat the keywords for printing
        keywords_print = ", ".join(keywords)
        print(f"Sorting threads by similarity to the given keywords: {keywords_print}")
        threads, similarity_scores = sort_by_similarity(threads, keywords)
        submission, similarity_score = get_subreddit_undone(
            threads, subreddit_name, similarity_scores=similarity_scores
        )
    else:
        threads = _fetch_subreddit_posts(subreddit_name, sort="hot", limit=25)
        submission = get_subreddit_undone(threads, subreddit_name)

    if submission is None:
        return get_subreddit_threads(POST_ID)  # submission already done. rerun

    elif not submission["num_comments"] and settings.config["settings"]["storymode"] == "false":
        print_substep("No comments found. Skipping.")
        exit()

    submission = check_done(submission)  # double-checking

    upvotes = submission["score"]
    ratio = submission["upvote_ratio"] * 100
    num_comments = submission["num_comments"]
    threadurl = f"https://new.reddit.com{submission['permalink']}"

    print_substep(f"Video will be: {submission['title']} :thumbsup:", style="bold green")
    print_substep(f"Thread url is: {threadurl} :thumbsup:", style="bold green")
    print_substep(f"Thread has {upvotes} upvotes", style="bold blue")
    print_substep(f"Thread has a upvote ratio of {ratio}%", style="bold blue")
    print_substep(f"Thread has {num_comments} comments", style="bold blue")
    if similarity_score:
        print_substep(
            f"Thread has a similarity score up to {round(similarity_score * 100)}%",
            style="bold blue",
        )

    content["thread_url"] = threadurl
    content["thread_title"] = submission["title"]
    content["thread_id"] = submission["id"]
    content["is_nsfw"] = submission["over_18"]
    content["comments"] = []
    if settings.config["settings"]["storymode"]:
        if settings.config["settings"]["storymodemethod"] == 1:
            content["thread_post"] = posttextparser(submission["selftext"])
        else:
            content["thread_post"] = submission["selftext"]
    else:
        # If we already have comments from _fetch_post_and_comments, use them;
        # otherwise fetch them now.
        if comments is None:
            _, comments = _fetch_post_and_comments(submission["id"])

        for top_level_comment in comments:
            body = top_level_comment.get("body", "")

            if body in ["[removed]", "[deleted]"]:
                continue  # see https://github.com/JasonLovesDoggo/RedditVideoMakerBot/issues/78
            if _contains_blocked_words(body):
                continue
            if top_level_comment.get("stickied", False):
                continue
            sanitised = sanitize_text(body)
            if not sanitised or sanitised == " ":
                continue
            if len(body) <= int(
                settings.config["reddit"]["thread"]["max_comment_length"]
            ):
                if len(body) >= int(
                    settings.config["reddit"]["thread"]["min_comment_length"]
                ):
                    if (
                        top_level_comment.get("author") is not None
                        and sanitize_text(body) is not None
                    ):  # if errors occur with this change to if not.
                        content["comments"].append(
                            {
                                "comment_body": body,
                                "comment_url": top_level_comment["permalink"],
                                "comment_id": top_level_comment["id"],
                            }
                        )

    print_substep("Received subreddit threads Successfully.", style="bold green")

    # Translate content to Chinese using LLM
    content = translate_reddit_object(content)

    return content
