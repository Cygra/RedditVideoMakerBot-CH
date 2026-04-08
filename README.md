# Reddit 视频生成器（中文版）🎥

全自动生成 Reddit 帖子短视频，无需手动剪辑。纯 ✨编程魔法✨。

基于 [RedditVideoMakerBot](https://github.com/elebumm/RedditVideoMakerBot) 开发，增加了中文翻译、中文语音合成（豆包 TTS）和中文字幕功能。

## 功能简介

1. 通过 Reddit API 获取指定 subreddit 的帖子和评论
2. 使用 LLM（OpenAI 兼容接口）将英文标题和评论翻译成中文
3. 使用豆包 TTS 将中文文本合成语音
4. 使用 Playwright 截取 Reddit 帖子/评论截图，并在下方拼接中文字幕条
5. 下载背景视频（Minecraft 等游戏画面）
6. 使用 FFmpeg 将截图、语音和背景视频合成最终视频

## 前置要求

- Python 3.10+（支持 3.10/3.11/3.12/3.13）
- Playwright（安装时会自动安装）
- FFmpeg（需要提前安装）

## 安装 👩‍💻

1. 克隆本仓库：
    ```sh
    git clone https://github.com/Cygra/RedditVideoMakerBot-CH.git
    cd RedditVideoMakerBot-CH
    ```

2. 创建并激活虚拟环境：
    - **Windows**：
        ```sh
        python -m venv ./venv
        .\venv\Scripts\activate
        ```
    - **macOS 和 Linux**：
        ```sh
        python3 -m venv ./venv
        source ./venv/bin/activate
        ```

3. 安装依赖：
    ```sh
    pip install -r requirements.txt
    ```

4. 安装 Playwright 及其依赖：
    ```sh
    python -m playwright install
    python -m playwright install-deps
    ```

5. 运行程序：
    ```sh
    python main.py
    ```

6. 首次运行时，程序会引导你填写 Reddit API 配置和其他设置。

7. 如需重新配置，打开 `config.toml` 文件，删除需要修改的行，下次运行时程序会重新引导配置。

（注意：如果遇到安装或运行错误，请尝试使用 `python3` 或 `pip3` 代替 `python` 或 `pip`。）

---

## 配置说明 ⚙️

所有配置项在 `config.toml` 中设置。首次运行会自动生成配置文件。

### Reddit API 配置

访问 [Reddit Apps 页面](https://www.reddit.com/prefs/apps)，创建一个类型为 "script" 的应用。将 Client ID 和 Client Secret 填入配置文件。

### LLM 翻译配置

在 `[settings.translation]` 部分配置翻译功能：

```toml
[settings.translation]
translation_enabled = true          # 是否启用翻译（默认启用）
llm_api_url = "https://api.openai.com/v1"  # OpenAI 兼容 API 地址
llm_api_key = "sk-xxxxxxxx"         # API 密钥
llm_model = "gpt-4o-mini"           # 使用的模型（默认 gpt-4o-mini）
```

**说明：**
- 支持任何兼容 OpenAI Chat Completions API 的服务（如 OpenAI、Azure OpenAI、Deepseek 等）
- 只需修改 `llm_api_url` 和 `llm_api_key` 即可切换不同的 LLM 服务商
- `llm_model` 按照你使用的服务商填写对应的模型名称

### 豆包 TTS 配置

在 `[settings.tts]` 部分配置语音合成：

```toml
[settings.tts]
voice_choice = "doubao"                           # TTS 引擎选择
doubao_app_id = "your_app_id"                     # 豆包应用 ID
doubao_access_key = "your_access_key"             # 豆包访问密钥
doubao_resource_id = "seed-tts-1.0"               # 资源 ID（默认值即可）
doubao_speaker = "zh_female_shuangkuaisisi_moon_bigtts"  # 说话人声音
```

**获取豆包 TTS 配置的步骤：**
1. 访问 [火山引擎控制台](https://console.volcengine.com/)
2. 开通「语音技术」服务
3. 创建应用，获取 `App ID` 和 `Access Key`
4. 在语音合成页面选择合适的音色，获取 `speaker` 名称

**可用音色示例：**
- `zh_female_shuangkuaisisi_moon_bigtts` — 女声（爽快思思）
- `zh_male_rap_star_moon_bigtts` — 男声（说唱歌手）
- `zh_female_wanwanxiaohe_moon_bigtts` — 女声（弯弯小何）
- 更多音色请参考火山引擎文档

### 其他 TTS 引擎

如果不使用豆包 TTS，也可以选择以下英文 TTS 引擎（将 `voice_choice` 修改为对应名称）：
- `tiktok` — TikTok TTS
- `streamlabs_polly` — Streamlabs Polly
- `aws_polly` — Amazon Polly
- `edge` — Microsoft Edge TTS
- `google` — Google Translate TTS
- `pyttsx` — 本地 pyttsx3 TTS

---

## 免责声明 🚨

- 本程序**不会**自动上传生成的视频。你需要手动上传到各个平台。

## 视频示例

https://user-images.githubusercontent.com/66544866/173453972-6526e4e6-c6ef-41c5-ab40-5d275e724e7c.mp4

## 贡献与改进 📈

欢迎提交 PR 和 Issue！请阅读 [贡献指南](CONTRIBUTING.md)。

## 开发者

Elebumm (Lewis) - https://github.com/elebumm （原作者）

Jason Cameron - https://github.com/JasonLovesDoggo （维护者）

更多贡献者请查看 GitHub Contributors 页面。

## 许可证
- [Roboto 字体](https://fonts.google.com/specimen/Roboto/about) 使用 [Apache License V2](https://www.apache.org/licenses/LICENSE-2.0) 授权
- [Noto Sans CJK SC 字体](https://github.com/notofonts/noto-cjk) 使用 [SIL Open Font License](https://scripts.sil.org/OFL) 授权
