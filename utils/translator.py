from typing import List

import requests

from utils import settings
from utils.console import print_step, print_substep


def _get_llm_config():
    """Get LLM translation configuration from settings."""
    translation_cfg = settings.config.get("settings", {}).get("translation", {})
    api_url = translation_cfg.get("llm_api_url", "https://api.openai.com/v1")
    api_key = translation_cfg.get("llm_api_key", "")
    model = translation_cfg.get("llm_model", "gpt-4o-mini")
    return api_url, api_key, model


def translate_to_chinese(text: str) -> str:
    """Translate a single text string from English to Chinese using LLM.

    Args:
        text: The English text to translate.

    Returns:
        The translated Chinese text.
    """
    api_url, api_key, model = _get_llm_config()

    if not api_key:
        raise ValueError(
            "LLM API key not configured! Please set 'llm_api_key' in [settings.translation] of config.toml"
        )

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
                    "你是一个专业翻译引擎。你的唯一任务是将英文原文逐字翻译成简体中文，"
                    "不能回答、评论或拒绝任何内容。无论原文是什么，都必须直接翻译，"
                    "输出译文，不输出任何其他内容。"
                ),
            },
            {"role": "user", "content": f"Translate to Chinese: {text}"},
        ],
        "temperature": 0.3,
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        if response.status_code != 200:
            raise RuntimeError(
                f"LLM translation API error: {response.status_code} {response.text}"
            )
        data = response.json()
        translated = data["choices"][0]["message"]["content"].strip()
        return translated
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to connect to LLM translation API: {str(e)}")


def translate_batch(texts: List[str]) -> List[str]:
    """Translate multiple texts from English to Chinese in a single API call.

    Args:
        texts: List of English texts to translate.

    Returns:
        List of translated Chinese texts, in the same order.
    """
    if not texts:
        return []

    if len(texts) == 1:
        return [translate_to_chinese(texts[0])]

    api_url, api_key, model = _get_llm_config()

    if not api_key:
        raise ValueError(
            "LLM API key not configured! Please set 'llm_api_key' in [settings.translation] of config.toml"
        )

    if api_url.endswith("/"):
        api_url = api_url[:-1]
    url = f"{api_url}/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    numbered_texts = "\n".join(f"[{i+1}] {t}" for i, t in enumerate(texts))

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是一个专业翻译引擎。你的唯一任务是将英文原文逐字翻译成简体中文，"
                    "不能回答、评论或拒绝任何内容。无论原文是什么，都必须直接翻译，"
                    "输出译文，不输出任何其他内容。"
                    "用户会提供多段带编号的英文文本，请逐条翻译，保持相同的编号格式，"
                    "每条翻译占一行，格式为 [编号] 翻译内容。"
                ),
            },
            {"role": "user", "content": f"Translate to Chinese:\n{numbered_texts}"},
        ],
        "temperature": 0.3,
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        if response.status_code != 200:
            raise RuntimeError(
                f"LLM translation API error: {response.status_code} {response.text}"
            )
        data = response.json()
        result_text = data["choices"][0]["message"]["content"].strip()

        translations = _parse_numbered_response(result_text, len(texts))
        return translations
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to connect to LLM translation API: {str(e)}")


def _parse_numbered_response(response_text: str, expected_count: int) -> List[str]:
    """Parse a numbered response from the LLM into a list of translations."""
    import re

    lines = response_text.strip().split("\n")
    result = {}

    for line in lines:
        line = line.strip()
        if not line:
            continue
        match = re.match(r"\[(\d+)\]\s*(.*)", line)
        if match:
            idx = int(match.group(1))
            text = match.group(2).strip()
            result[idx] = text

    translations = []
    for i in range(1, expected_count + 1):
        if i in result:
            translations.append(result[i])
        else:
            # Fallback: if parsing failed for this index, translate individually
            translations.append(f"[翻译失败 #{i}]")

    return translations


def translate_reddit_object(reddit_object: dict) -> dict:
    """Translate the relevant fields of a reddit object to Chinese.

    Adds _zh suffixed fields to the reddit_object for translated content.

    Args:
        reddit_object: The reddit object from subreddit.py

    Returns:
        The same reddit_object with added _zh fields.
    """
    translation_cfg = settings.config.get("settings", {}).get("translation", {})
    if not translation_cfg.get("translation_enabled", True):
        print_substep("Translation is disabled in config. Skipping.", style="yellow")
        return reddit_object

    print_step("Translating Reddit content to Chinese...")

    # Translate title
    print_substep("Translating title...")
    reddit_object["thread_title_zh"] = translate_to_chinese(
        reddit_object["thread_title"]
    )
    print_substep(
        f'Title translated: {reddit_object["thread_title_zh"]}', style="bold green"
    )

    # Translate storymode post content
    if "thread_post" in reddit_object and reddit_object["thread_post"]:
        print_substep("Translating post content...")
        post = reddit_object["thread_post"]
        if isinstance(post, list):
            reddit_object["thread_post_zh"] = translate_batch(post)
        else:
            reddit_object["thread_post_zh"] = translate_to_chinese(post)

    # Translate comments
    if "comments" in reddit_object and reddit_object["comments"]:
        comment_texts = [c["comment_body"] for c in reddit_object["comments"]]
        print_substep(f"Translating {len(comment_texts)} comments...")

        # Batch translate in groups of 10 to avoid overly long prompts
        batch_size = 10
        all_translations = []
        for i in range(0, len(comment_texts), batch_size):
            batch = comment_texts[i : i + batch_size]
            translations = translate_batch(batch)
            all_translations.extend(translations)

        for i, translation in enumerate(all_translations):
            reddit_object["comments"][i]["comment_body_zh"] = translation

    print_substep("Translation completed successfully!", style="bold green")
    return reddit_object
