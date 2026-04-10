from typing import Tuple

from TTS.doubao import DoubaoTTS
from TTS.engine_wrapper import TTSEngine


def save_text_to_mp3(reddit_obj) -> Tuple[int, int]:
    """Saves text to MP3 files.

    Args:
        reddit_obj (): Reddit object received from reddit API in reddit/subreddit.py

    Returns:
        tuple[int,int]: (total length of the audio, the number of comments audio was generated for)
    """

    text_to_mp3 = TTSEngine(DoubaoTTS, reddit_obj)
    return text_to_mp3.run()
