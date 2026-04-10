import re
import time

import requests

from utils import settings
from utils.console import print_step, print_substep
from utils.subreddit import _contains_blocked_words, get_subreddit_undone
from utils.translator import translate_reddit_object
from utils.videos import check_done
from utils.voice import sanitize_text

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36",
}


def _fetch_subreddit_posts(subreddit_name: str, sort: str = "hot", limit: int = 25, time_filter: str = None, page=None) -> list:
    """Fetch posts from a subreddit using the public JSON API.

    Args:
        subreddit_name: Name of the subreddit (without r/ prefix).
        sort: Sort order ('hot', 'top', 'new').
        limit: Maximum number of posts to return.
        time_filter: Time filter for 'top' sort ('day', 'week', 'month', 'year', 'all').
        page: Optional Playwright ``Page`` whose context is already logged in to Reddit.

    Returns:
        List of post data dicts.
    """
    url = f"https://www.reddit.com/r/{subreddit_name}/{sort}.json"
    params = {"limit": str(limit)}
    if sort == "top" and time_filter:
        params["t"] = time_filter
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        if page is not None:
            response = page.request.get(url, params=params)
            if response.status == 403:
                if attempt < max_retries:
                    print_substep(f"收到 Reddit 403 错误，10s 后重试（第 {attempt}/{max_retries} 次）...", style="yellow")
                    time.sleep(10)
                    continue
                print_substep("收到 Reddit 403 错误，已达最大重试次数。", style="red")
                raise RuntimeError(f"Reddit 返回 403，请求 URL: {url}")
            data = response.json()
        else:
            resp = requests.get(url, headers=_HEADERS, params=params, timeout=30)
            if resp.status_code == 403:
                if attempt < max_retries:
                    print_substep(f"收到 Reddit 403 错误，10s 后重试（第 {attempt}/{max_retries} 次）...", style="yellow")
                    time.sleep(10)
                    continue
                print_substep("收到 Reddit 403 错误，已达最大重试次数。", style="red")
            resp.raise_for_status()
            data = resp.json()
        return [child["data"] for child in data["data"]["children"]]
    return []


def _fetch_post_and_comments(post_id: str, comment_limit: int = 100, page=None) -> tuple:
    """Fetch a single post and its comments.

    Uses the provided Playwright page's authenticated context when available
    (to avoid 403 responses from Reddit), otherwise falls back to a plain
    unauthenticated HTTP request.

    Args:
        post_id: Reddit post ID (e.g. '1sg3sdt').
        comment_limit: Maximum number of comments to return.
        page: Optional Playwright ``Page`` whose context is already logged in
              to Reddit.  When supplied, the request reuses the browser's
              session cookies so Reddit does not block it with a 403.

    Returns:
        Tuple of (post_dict, list_of_comment_dicts).
    """
    url = f"https://www.reddit.com/comments/{post_id}.json"
    params = {"limit": str(comment_limit)}
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        if page is not None:
            response = page.request.get(url, params=params)
            if response.status == 403:
                if attempt < max_retries:
                    print_substep(f"收到 Reddit 403 错误，10s 后重试（第 {attempt}/{max_retries} 次）...", style="yellow")
                    time.sleep(10)
                    continue
                print_substep("收到 Reddit 403 错误，已达最大重试次数。", style="red")
                raise RuntimeError(f"Reddit 返回 403，请求 URL: {url}")
            data = response.json()
        else:
            resp = requests.get(url, headers=_HEADERS, params={"limit": comment_limit}, timeout=30)
            if resp.status_code == 403:
                if attempt < max_retries:
                    print_substep(f"收到 Reddit 403 错误，10s 后重试（第 {attempt}/{max_retries} 次）...", style="yellow")
                    time.sleep(10)
                    continue
                print_substep("收到 Reddit 403 错误，已达最大重试次数。", style="red")
            resp.raise_for_status()
            data = resp.json()

        post = data[0]["data"]["children"][0]["data"]
        comments = []
        for child in data[1]["data"]["children"]:
            if child["kind"] == "t1":
                comments.append(child["data"])
        return post, comments
    return None, []


def _select_best_thread_via_llm(threads: list, keywords: list, subreddit_name: str):
    """Use LLM (Chat Completion API) to pick the most relevant thread.

    Sends all thread titles as a numbered list to the LLM and asks it to return
    the index of the most relevant one.  Falls back to the first valid thread
    if the API call fails or returns an unexpected result.

    Args:
        threads: List of post dicts fetched from Reddit.
        keywords: List of keyword strings for relevance matching.
        subreddit_name: Name of the subreddit (used for fallback fetching).

    Returns:
        The chosen submission dict (already validated as undone / not blocked).
    """
    from utils.subreddit import get_subreddit_undone

    # Build a numbered title list for the prompt
    titles = [f"{i+1}. {t['title']}" for i, t in enumerate(threads)]
    titles_text = "\n".join(titles)
    keywords_text = ", ".join(keywords)

    translation_cfg = settings.config.get("settings", {}).get("translation", {})
    api_url = translation_cfg.get("llm_api_url", "https://api.openai.com/v1")
    api_key = translation_cfg.get("llm_api_key", "")
    model = translation_cfg.get("llm_model", "gpt-4o-mini")

    if not api_key:
        print_substep("未设置 LLM API Key — 使用默认排序。", style="yellow")
        return get_subreddit_undone(threads, subreddit_name)

    if api_url.endswith("/"):
        api_url = api_url[:-1]
    url = f"{api_url}/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是一个帖子相关性排序助手。用户会给你一组带编号的帖子标题和一组关键词。"
                    "请从中选出与关键词最相关的那条帖子，只返回该帖子的编号（一个整数），"
                    "不要输出其他任何内容。"
                ),
            },
            {
                "role": "user",
                "content": f"关键词：{keywords_text}\n\n帖子列表：\n{titles_text}",
            },
        ],
        "temperature": 0,
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(f"LLM API error: {resp.status_code}")
        data = resp.json()
        answer = data["choices"][0]["message"]["content"].strip()
        # Extract the first integer from the response
        match = re.search(r"\d+", answer)
        if match:
            idx = int(match.group()) - 1  # 1-indexed -> 0-indexed
            if 0 <= idx < len(threads):
                chosen = threads[idx]
                # Re-order: put chosen thread first, then the rest
                reordered = [chosen] + [t for i, t in enumerate(threads) if i != idx]
                return get_subreddit_undone(reordered, subreddit_name)
        # If parsing failed, fall back
        print_substep("LLM 返回了非预期结果 — 使用默认排序。", style="yellow")
    except Exception as e:
        print_substep(f"LLM 相似度选帖失败: {e} — 使用默认排序。", style="yellow")

    return get_subreddit_undone(threads, subreddit_name)


def get_subreddit_threads(POST_ID: str, page=None):
    """
    Returns a list of threads from the AskReddit subreddit.
    """

    content = {}
    comments = None

    # Ask user for subreddit input
    print_step("正在获取 subreddit 帖子...")
    if not settings.config["reddit"]["thread"][
        "subreddit"
    ]:  # note to user. you can have multiple subreddits via '+' separated names
        try:
            subreddit_name = re.sub(r"r\/", "", input("What subreddit would you like to pull from? "))
        except ValueError:
            subreddit_name = "askreddit"
            print_substep("未指定 subreddit，使用默认值 AskReddit。")
    else:
        sub = settings.config["reddit"]["thread"]["subreddit"]
        print_substep(f"使用 TOML 配置中的 subreddit: r/{sub}")
        subreddit_name = sub
        if str(subreddit_name).casefold().startswith("r/"):  # removes the r/ from the input
            subreddit_name = subreddit_name[2:]

    if POST_ID:  # would only be called if there are multiple queued posts
        submission, comments = _fetch_post_and_comments(POST_ID, page=page)

    elif (
        settings.config["reddit"]["thread"]["post_id"]
        and len(str(settings.config["reddit"]["thread"]["post_id"]).split("+")) == 1
    ):
        submission, comments = _fetch_post_and_comments(
            settings.config["reddit"]["thread"]["post_id"], page=page
        )
    elif settings.config["ai"]["ai_similarity_enabled"]:  # ai sorting via LLM
        threads = _fetch_subreddit_posts(subreddit_name, sort="hot", limit=50, page=page)
        keywords = settings.config["ai"]["ai_similarity_keywords"].split(",")
        keywords = [keyword.strip() for keyword in keywords]
        keywords_print = ", ".join(keywords)
        print(f"Sorting threads by similarity to the given keywords: {keywords_print}")
        submission = _select_best_thread_via_llm(threads, keywords, subreddit_name)
    else:
        threads = _fetch_subreddit_posts(subreddit_name, sort="hot", limit=25, page=page)
        submission = get_subreddit_undone(threads, subreddit_name)

    if submission is None:
        return get_subreddit_threads(POST_ID)  # submission already done. rerun

    elif not submission["num_comments"] and settings.config["settings"]["storymode"] == "false":
        print_substep("未找到评论，跳过该帖。")
        exit()

    submission = check_done(submission)  # double-checking

    upvotes = submission["score"]
    ratio = submission["upvote_ratio"] * 100
    num_comments = submission["num_comments"]
    threadurl = f"https://www.reddit.com{submission['permalink']}"

    print_substep(f"即将生成视频: {submission['title']} :thumbsup:", style="bold green")
    print_substep(f"帖子链接: {threadurl} :thumbsup:", style="bold green")
    print_substep(f"帖子获得 {upvotes} 个赞", style="bold blue")
    print_substep(f"帖子点赞率为 {ratio}%", style="bold blue")
    print_substep(f"帖子有 {num_comments} 条评论", style="bold blue")

    content["thread_url"] = threadurl
    content["thread_title"] = submission["title"]
    content["thread_id"] = submission["id"]
    content["is_nsfw"] = submission["over_18"]
    content["comments"] = []
    if settings.config["settings"]["storymode"]:
        content["thread_post"] = submission["selftext"]
    else:
        # If we already have comments from _fetch_post_and_comments, use them;
        # otherwise fetch them now.
        if comments is None:
            _, comments = _fetch_post_and_comments(submission["id"], page=page)

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

    print_substep("成功获取 subreddit 帖子。", style="bold green")

    # Translate content to Chinese using LLM
    content = translate_reddit_object(content)

    return content
