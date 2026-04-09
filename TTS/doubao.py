import base64
import json
import random
import uuid

import requests

from utils import settings


# Chinese and English TTS voices for Doubao
DOUBAO_VOICES = (
    "saturn_zh_female_cancan_tob",        # 知性灿灿（角色扮演）
    "saturn_zh_female_keainvsheng_tob",   # 可爱女生（角色扮演）
    "saturn_zh_female_tiaopigongzhu_tob", # 调皮公主（角色扮演）
    "saturn_zh_male_shuanglangshaonian_tob", # 爽朗少年（角色扮演）
    "saturn_zh_male_tiancaitongzhuo_tob", # 天才同桌（角色扮演）
    "zh_female_xiaohe_uranus_bigtts",     # 小何（通用场景）
    "zh_male_m191_uranus_bigtts",         # 云舟（通用场景）
    "zh_male_taocheng_uranus_bigtts",     # 小天（通用场景）
    "en_male_tim_uranus_bigtts",          # Tim（通用场景，英文）
)


class DoubaoTTS:
    """Doubao (豆包) Text-to-Speech engine using the HTTP Chunked API.

    Uses the unidirectional HTTP Chunked endpoint at:
    https://openspeech.bytedance.com/api/v3/tts/unidirectional

    Configuration required in config.toml under [settings.tts]:
        - doubao_app_id: App ID from Volcengine console
        - doubao_access_token: Access token from Volcengine console
        - doubao_resource_id: Resource ID (default: seed-tts-2.0)
        - doubao_speaker: Speaker voice name
    """

    def __init__(self):
        self.max_chars = 2000

        tts_config = settings.config["settings"]["tts"]
        self.app_id = tts_config.get("doubao_app_id", "")
        self.access_token = tts_config.get("doubao_access_token", "")
        self.resource_id = tts_config.get("doubao_resource_id", "seed-tts-2.0")
        self.speaker = tts_config.get(
            "doubao_speaker", "zh_female_xiaohe_uranus_bigtts"
        )

        if not self.app_id:
            raise ValueError(
                "Doubao TTS requires 'doubao_app_id'. "
                "Please configure it in [settings.tts] of config.toml. "
                "Get it from: https://console.volcengine.com/speech/app"
            )
        if not self.access_token:
            raise ValueError(
                "Doubao TTS requires 'doubao_access_token'. "
                "Please configure it in [settings.tts] of config.toml. "
                "Get it from: https://console.volcengine.com/speech/app"
            )

        self.api_url = (
            "https://openspeech.bytedance.com/api/v3/tts/unidirectional"
        )
        self._session = requests.Session()

    def run(self, text: str, filepath: str, random_voice: bool = False):
        """Convert text to speech and save as mp3.

        Args:
            text: The Chinese text to synthesize.
            filepath: Path to save the mp3 file.
            random_voice: If True, use a random Chinese voice.
        """
        speaker = self.randomvoice() if random_voice else self.speaker

        headers = {
            "X-Api-App-Id": self.app_id,
            "X-Api-Access-Key": self.access_token,
            "X-Api-Resource-Id": self.resource_id,
            "X-Api-Request-Id": str(uuid.uuid4()),
            "Content-Type": "application/json",
        }

        payload = {
            "user": {"uid": "reddit-video-maker"},
            "req_params": {
                "text": text,
                "speaker": speaker,
                "audio_params": {
                    "format": "mp3",
                    "sample_rate": 24000,
                },
            },
        }

        try:
            response = self._session.post(
                self.api_url,
                headers=headers,
                json=payload,
                stream=True,
                timeout=120,
            )

            if response.status_code != 200:
                raise RuntimeError(
                    f"Doubao TTS API error: {response.status_code} {response.text}"
                )

            audio_data = bytearray()
            for line in response.iter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line.decode("utf-8"))
                except json.JSONDecodeError:
                    continue

                code = chunk.get("code", -1)

                if code == 20000000:
                    # Session finished successfully
                    break
                elif code != 0:
                    msg = chunk.get("message", "Unknown error")
                    raise RuntimeError(f"Doubao TTS error (code {code}): {msg}")

                data = chunk.get("data")
                if data:
                    audio_data.extend(base64.b64decode(data))

            if not audio_data:
                raise RuntimeError(
                    "Doubao TTS returned no audio data. "
                    "Check your app_id, access_token, and speaker configuration."
                )

            with open(filepath, "wb") as f:
                f.write(audio_data)

        except requests.RequestException as e:
            raise RuntimeError(f"Failed to connect to Doubao TTS API: {str(e)}")

    @staticmethod
    def randomvoice() -> str:
        """Select a random Chinese voice."""
        return random.choice(DOUBAO_VOICES)
