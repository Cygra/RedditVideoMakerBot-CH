import json
import random
import re
from pathlib import Path
from random import randrange
from typing import Any, Dict, Tuple

import yt_dlp
from moviepy import AudioFileClip, VideoFileClip
from moviepy.video.io.ffmpeg_tools import ffmpeg_extract_subclip

from utils import settings
from utils.console import print_step, print_substep


def load_background_options():
    _background_options = {}
    # Load background videos
    with open("./utils/background_videos.json") as json_file:
        _background_options["video"] = json.load(json_file)

    # Load background audios
    with open("./utils/background_audios.json") as json_file:
        _background_options["audio"] = json.load(json_file)

    # Remove "__comment" from backgrounds
    del _background_options["video"]["__comment"]
    del _background_options["audio"]["__comment"]

    for name in list(_background_options["video"].keys()):
        pos = _background_options["video"][name][3]

        if pos != "center":
            _background_options["video"][name][3] = lambda t: ("center", pos + t)

    return _background_options


def get_start_and_end_times(video_length: int, length_of_clip: int) -> Tuple[int, int]:
    """Generates a random interval of time to be used as the background of the video.

    Args:
        video_length (int): Length of the video
        length_of_clip (int): Length of the video to be used as the background

    Returns:
        tuple[int,int]: Start and end time of the randomized interval
    """
    initialValue = 180
    # Issue #1649 - Ensures that will be a valid interval in the video
    while int(length_of_clip) <= int(video_length + initialValue):
        if initialValue == initialValue // 2:
            raise Exception("Your background is too short for this video length")
        else:
            initialValue //= 2  # Divides the initial value by 2 until reach 0
    random_time = randrange(initialValue, int(length_of_clip) - int(video_length))
    return random_time, random_time + video_length


def get_background_config(mode: str):
    """Fetch the background/s configuration"""
    try:
        choice = str(settings.config["settings"]["background"][f"background_{mode}"]).casefold()
    except AttributeError:
        print_substep("未选择背景，将随机选取。")
        choice = None

    # Handle default / not supported background using default option.
    # Default : pick random from supported background.
    if not choice or choice not in background_options[mode]:
        choice = random.choice(list(background_options[mode].keys()))

    return background_options[mode][choice]


def download_background_video(background_config: Tuple[str, str, str, Any]):
    """Downloads the background/s video from YouTube."""
    Path("./assets/backgrounds/video/").mkdir(parents=True, exist_ok=True)
    # note: make sure the file name doesn't include an - in it
    uri, filename, credit, _ = background_config
    if Path(f"assets/backgrounds/video/{credit}-{filename}").is_file():
        return
    print_step(
        "需要下载背景视频，文件较大但只需下载一次。😎"
    )
    print_substep("正在下载背景视频，请耐心等待 🙏 ")
    print_substep(f"正在从 {uri} 下载 {filename}")
    ydl_opts = {
        "format": "bestvideo[height<=1080][ext=mp4]",
        "outtmpl": f"assets/backgrounds/video/{credit}-{filename}",
        "retries": 10,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download(uri)
    print_substep("背景视频下载完成！🎉", style="bold green")


def download_background_audio(background_config: Tuple[str, str, str]):
    """Downloads the background/s audio from YouTube."""
    Path("./assets/backgrounds/audio/").mkdir(parents=True, exist_ok=True)
    # note: make sure the file name doesn't include an - in it
    uri, filename, credit = background_config
    if Path(f"assets/backgrounds/audio/{credit}-{filename}").is_file():
        return
    print_step(
        "需要下载背景音乐，文件较大但只需下载一次。😎"
    )
    print_substep("正在下载背景音乐，请耐心等待 🙏 ")
    print_substep(f"正在从 {uri} 下载 {filename}")
    ydl_opts = {
        "outtmpl": f"./assets/backgrounds/audio/{credit}-{filename}",
        "format": "bestaudio/best",
        "extract_audio": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([uri])

    print_substep("背景音乐下载完成！🎉", style="bold green")


def chop_background(background_config: Dict[str, Tuple], video_length: int, reddit_object: dict):
    """Generates the background audio and footage to be used in the video and writes it to assets/temp/background.mp3 and assets/temp/background.mp4

    Args:
        reddit_object (Dict[str,str]) : Reddit object
        background_config (Dict[str,Tuple]]) : Current background configuration
        video_length (int): Length of the clip where the background footage is to be taken out of
    """
    thread_id = re.sub(r"[^\w\s-]", "", reddit_object["thread_id"])

    if settings.config["settings"]["background"]["background_audio_volume"] == 0:
        print_step("音量设为 0，跳过背景音乐创建...")
    else:
        print_step("正在从背景音乐中截取片段...✂️")
        audio_choice = f"{background_config['audio'][2]}-{background_config['audio'][1]}"
        background_audio = AudioFileClip(f"assets/backgrounds/audio/{audio_choice}")
        start_time_audio, end_time_audio = get_start_and_end_times(
            video_length, background_audio.duration
        )
        background_audio = background_audio.subclipped(start_time_audio, end_time_audio)
        background_audio.write_audiofile(f"assets/temp/{thread_id}/background.mp3")

    print_step("正在从背景视频中截取片段...✂️")
    video_choice = f"{background_config['video'][2]}-{background_config['video'][1]}"
    background_video = VideoFileClip(f"assets/backgrounds/video/{video_choice}")
    start_time_video, end_time_video = get_start_and_end_times(
        video_length, background_video.duration
    )
    # Extract video subclip
    try:
        with VideoFileClip(f"assets/backgrounds/video/{video_choice}") as video:
            new = video.subclipped(start_time_video, end_time_video)
            new.write_videofile(f"assets/temp/{thread_id}/background.mp4")

    except (OSError, IOError):  # ffmpeg issue see #348
        print_substep("FFmpeg 出现问题，正在重试...")
        ffmpeg_extract_subclip(
            f"assets/backgrounds/video/{video_choice}",
            start_time_video,
            end_time_video,
            outputfile=f"assets/temp/{thread_id}/background.mp4",
        )
    print_substep("背景视频截取完成！", style="bold green")
    return background_config["video"][2]


# Create a tuple for downloads background (background_audio_options, background_video_options)
background_options = load_background_options()
