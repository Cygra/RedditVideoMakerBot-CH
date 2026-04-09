# Reddit 视频生成器（中文版）🎥

全自动生成 Reddit 帖子短视频，无需手动剪辑。纯 ✨编程魔法✨。

基于 [RedditVideoMakerBot](https://github.com/elebumm/RedditVideoMakerBot) 开发，增加了中文翻译和中文语音合成（豆包 TTS）功能。

## 功能简介

1. 通过 Reddit 公开 JSON API 获取指定 subreddit 的帖子和评论，**无需注册 Reddit API 应用**
2. 使用 LLM（兼容 OpenAI Chat Completions 接口）将英文内容翻译成中文
3. 使用豆包 TTS 将中文文本合成自然语音
4. 使用 Playwright 登录 Reddit 网页，将中文翻译追加在原文下方，然后截图
5. 从 YouTube 下载背景视频（Minecraft、GTA 等游戏画面）和背景音乐
6. 使用 FFmpeg 将截图、语音、背景视频和背景音乐合成最终竖版视频

---

## 前置要求

- Python 3.10、3.11、3.12 或 3.13
- FFmpeg（需提前安装并加入系统 PATH）
- 能访问 Reddit 和 YouTube 的网络环境（用于抓取帖子、下载背景素材）

---

## 安装 👩‍💻

**1. 克隆本仓库**

```sh
git clone https://github.com/Cygra/RedditVideoMakerBot-CH.git
cd RedditVideoMakerBot-CH
```

**2. 创建并激活虚拟环境**

- Windows：
    ```sh
    python -m venv ./venv
    .\venv\Scripts\activate
    ```
- macOS / Linux：
    ```sh
    python3 -m venv ./venv
    source ./venv/bin/activate
    ```

**3. 安装 Python 依赖**

```sh
pip install -r requirements.txt
```

**4. 安装 Playwright 浏览器**

```sh
python -m playwright install chromium
python -m playwright install-deps
```

**5. 首次运行**

```sh
python main.py
```

首次运行时，程序会逐项引导你填写所有必要配置（Reddit 账号、LLM API、豆包 TTS 等），并生成 `config.toml`。

> 如遇命令不存在，请将 `python` / `pip` 替换为 `python3` / `pip3`。

---

## 工作流程

每次运行 `python main.py`，程序会按以下顺序自动执行：

1. **获取帖子** — 从指定 subreddit 抓取热门帖子，按配置选择一条未处理过的帖子及其评论
2. **LLM 翻译** — 将标题和评论批量翻译成中文（每批最多 10 条，减少 API 调用次数）
3. **语音合成** — 用豆包 TTS 将中文文案逐条合成 MP3
4. **截图** — 用 Playwright 登录 Reddit，在原文下方追加中文翻译后截图
5. **下载背景** — 首次使用某个背景时自动从 YouTube 下载（后续直接复用缓存）
6. **合成视频** — 用 FFmpeg 将截图序列、TTS 音频、背景视频、背景音乐合成最终 MP4，输出到 `results/<subreddit>/` 目录

---

## 使用模式

### 模式一：评论模式（默认）

**效果：** 视频依次展示帖子标题截图和每条评论截图，每张截图配合对应的中文语音朗读。适合问答类、讨论类 subreddit（如 AskReddit、AITA 等）。

```toml
[settings]
storymode = false   # 默认值，可省略
```

**截图顺序：**
1. 帖子标题（含中文翻译）
2. 评论 1（含中文翻译）
3. 评论 2（含中文翻译）
4. ……

**帖子选取规则：** 从 subreddit 热门帖中筛选出满足最少评论数要求、未曾生成过视频、且不含屏蔽词的帖子。

---

### 模式二：故事模式（storymode）

**效果：** 仅读取帖子标题和正文（不读评论），适合故事类 subreddit（如 r/tifu、r/nosleep、r/AmItheAsshole 的长文帖等）。

```toml
[settings]
storymode = true
storymode_max_length = 1000   # 正文最大字符数，超出部分截断；200字符约50秒
```

**截图内容：**
1. 帖子标题（含中文翻译）
2. 帖子正文（截图整体）

> **提示：** 故事模式支持 `theme = "transparent"` 透明背景，截图会以纯文字叠加在背景视频上，视觉效果更简洁。

---

### 帖子选取方式

#### 方式 A：自动抓取热门帖（默认）

从指定 subreddit 的 Hot 列表中自动选择一条符合条件的帖子。

```toml
[reddit.thread]
subreddit = "AskReddit"   # 单个 subreddit
# 或多个（用 + 连接，无空格）：
subreddit = "AskReddit+tifu+AmItheAsshole"
```

#### 方式 B：指定帖子 ID

直接指定一个或多个帖子 ID，程序会按顺序逐一处理。

```toml
[reddit.thread]
post_id = "urdtfx"              # 单个帖子
post_id = "urdtfx+abc123+xyz"  # 多个帖子，依次生成视频
```

帖子 ID 是 Reddit 帖子 URL 中的短码，例如：
`https://www.reddit.com/r/AskReddit/comments/urdtfx/...` 中的 `urdtfx`。

#### 方式 C：AI 相似度选帖

让 LLM 从热门帖列表中挑选出与指定关键词最相关的帖子，适合专注于特定话题的频道。

```toml
[ai]
ai_similarity_enabled = true
ai_similarity_keywords = "Elon Musk, Twitter, AI"   # 关键词，逗号分隔
```

启用后，程序会抓取 50 条热门帖，发给 LLM 打分选优，LLM 不可用时自动降级为热门顺序。

---

### 批量运行

设置 `times_to_run` 可连续自动生成多个视频（每次从 subreddit 取一条新帖子）：

```toml
[settings]
times_to_run = 5   # 连续生成 5 个视频
```

---

## 配置说明 ⚙️

所有配置均在 `config.toml` 中设置。首次运行会自动生成，也可手动编辑。

### Reddit 账号

```toml
[reddit.creds]
username = "你的Reddit用户名"
password = "你的Reddit密码"
```

账号仅用于 Playwright 登录 Reddit 网页截图，不用于 API 鉴权。

---

### 帖子与评论筛选

```toml
[reddit.thread]
subreddit = "AskReddit"        # 目标 subreddit（必填）
post_id = ""                   # 指定帖子 ID（可选，留空则自动选取）
max_comment_length = 500       # 评论最大字符数（超出的评论跳过）
min_comment_length = 1         # 评论最小字符数
min_comments = 20              # 帖子至少需要有多少条评论才入选
blocked_words = "nsfw,spoiler" # 屏蔽词（逗号分隔），含这些词的帖子和评论会被跳过
```

---

### 视频与截图参数

```toml
[settings]
theme = "dark"          # 截图主题：dark（深色）/ light（浅色）/ transparent（透明，仅故事模式）
resolution_w = 1080     # 视频宽度（像素）
resolution_h = 1920     # 视频高度（像素），默认竖版 9:16
opacity = 0.9           # 截图叠加在背景上的透明度（0.0～1.0）
zoom = 1.0              # 浏览器缩放比例（0.1～2.0），调大可让截图文字更大
allow_nsfw = false      # 是否允许 NSFW 帖子
channel_name = "Reddit Tales"  # 频道名称，会显示在视频水印处
times_to_run = 1        # 连续运行次数
```

**主题说明：**

| 主题 | 效果 |
|------|------|
| `dark` | Reddit 深色模式截图，白字黑底 |
| `light` | Reddit 浅色模式截图，黑字白底 |
| `transparent` | 仅故事模式可用；截图背景透明，文字浮现在背景视频上 |

---

### 背景视频

```toml
[settings.background]
background_video = "minecraft"   # 背景视频游戏名称
```

**可选背景视频：**

| 配置值 | 内容 |
|--------|------|
| `minecraft` | Minecraft 跑酷 |
| `minecraft-2` | Minecraft 跑酷（第二版）|
| `gta` | GTA 特技赛车 |
| `motor-gta` | GTA 摩托跑酷 |
| `rocket-league` | Rocket League |
| `csgo-surf` | CS:GO Surf 模式 |
| `cluster-truck` | Cluster Truck |
| `multiversus` | MultiVersus |
| `fall-guys` | Fall Guys |
| `steep` | Steep 极限运动 |
| `""`（空字符串）| 随机选取 |

> 背景视频首次使用时会从 YouTube 自动下载（仅下载一次，存入 `assets/backgrounds/video/`）。

---

### 背景音乐

```toml
[settings.background]
background_audio = "lofi"              # 背景音乐风格
background_audio_volume = 0.15        # 背景音乐音量（0.0 = 无背景音乐，1.0 = 最大）
enable_extra_audio = false            # 是否额外导出一个无背景音乐版本（存入 OnlyTTS/ 子目录）
```

**可选背景音乐：**

| 配置值 | 内容 |
|--------|------|
| `lofi` | Lofi 放松音乐 |
| `lofi-2` | Lofi 放松音乐（第二版）|
| `chill-summer` | 轻松夏日氛围音乐 |
| `""`（空字符串）| 随机选取 |

---

### 封面图（缩略图）

```toml
[settings.background]
background_thumbnail = false                      # 是否生成封面图
background_thumbnail_font_family = "arial"       # 封面文字字体（系统字体名，不含 .ttf 后缀）
background_thumbnail_font_size = 96              # 封面文字大小（像素）
background_thumbnail_font_color = "255,255,255" # 封面文字颜色（RGB）
```

启用后需在 `assets/backgrounds/` 目录放置一张 `thumbnail.png` 作为封面背景，程序会在上面叠加帖子标题，生成封面图并保存到 `assets/temp/<id>/thumbnail.png`。

---

### LLM 翻译

```toml
[settings.translation]
translation_enabled = true                        # 是否启用翻译（关闭则截图和 TTS 均使用英文原文）
llm_api_url = "https://api.openai.com/v1"        # OpenAI 兼容 API 地址
llm_api_key = "sk-xxxxxxxx"                      # API 密钥
llm_model = "gpt-4o-mini"                        # 使用的模型
```

**说明：**
- 支持任何兼容 OpenAI Chat Completions API 的服务，例如：
  - OpenAI：`llm_api_url = "https://api.openai.com/v1"`
  - DeepSeek：`llm_api_url = "https://api.deepseek.com/v1"`
  - 本地 Ollama：`llm_api_url = "http://localhost:11434/v1"`
- 翻译的中文文案同时用于截图中的文字叠加和豆包 TTS 语音合成，两者完全一致
- 评论按每批 10 条批量翻译，减少 API 请求次数

---

### 豆包 TTS（语音合成）

```toml
[settings.tts]
doubao_app_id = "123456789"                              # 豆包应用 ID
doubao_access_token = "your-access-token"                 # 豆包访问令牌
doubao_resource_id = "seed-tts-2.0"                     # 资源 ID
doubao_speaker = "zh_female_xiaohe_uranus_bigtts"        # 说话人音色
random_voice = false                                     # 是否每条评论随机切换音色
silence_duration = 0.3                                   # 每段语音之间的静音时长（秒）
no_emojis = false                                        # 是否去除文本中的 emoji
```

**获取豆包 TTS 配置：**
1. 登录 [火山引擎控制台](https://console.volcengine.com/speech/app)
2. 开通「语音技术」→「语音合成」服务
3. 创建应用，获取 `App ID` 和 `Access Key`
4. 在音色列表中选择音色，复制 `Speaker` 名称

**可用资源 ID（doubao_resource_id）：**

| 资源 ID | 说明 |
|---------|------|
| `seed-tts-1.0` | 字符版（按字符计费）|
| `seed-tts-1.0-concurr` | 并发版 |
| `seed-tts-2.0` | 最新版（默认推荐）|

**内置随机音色池（seed-tts-2.0，启用 random_voice 时随机选取）：**

| 音色名称 | 说话人 | 场景 |
|----------|--------|------|
| `saturn_zh_female_cancan_tob` | 知性灿灿 | 角色扮演 |
| `saturn_zh_female_keainvsheng_tob` | 可爱女生 | 角色扮演 |
| `saturn_zh_female_tiaopigongzhu_tob` | 调皮公主 | 角色扮演 |
| `saturn_zh_male_shuanglangshaonian_tob` | 爽朗少年 | 角色扮演 |
| `saturn_zh_male_tiancaitongzhuo_tob` | 天才同桌 | 角色扮演 |
| `zh_female_xiaohe_uranus_bigtts` | 小何 | 通用场景 |
| `zh_male_m191_uranus_bigtts` | 云舟 | 通用场景 |
| `zh_male_taocheng_uranus_bigtts` | 小天 | 通用场景 |
| `en_male_tim_uranus_bigtts` | Tim | 通用场景（英文）|

更多音色请参考 [火山引擎音色列表](https://www.volcengine.com/docs/6561/1257544)。

---

### AI 相似度选帖

```toml
[ai]
ai_similarity_enabled = false                       # 是否启用 AI 选帖
ai_similarity_keywords = "Elon Musk, AI, startup"  # 关键词（逗号分隔）
```

启用后复用 `[settings.translation]` 中的 LLM 配置进行选帖，无需单独配置。

---

## 输出结果

- **最终视频：** `results/<subreddit>/<帖子标题>.mp4`
- **无背景音乐版（可选）：** `results/<subreddit>/OnlyTTS/<帖子标题>.mp4`
- **封面图（可选）：** `assets/temp/<id>/thumbnail.png`
- **临时文件：** `assets/temp/<id>/`（视频生成完成后自动清理）

---

## 配置速查表

以下是一份完整的 `config.toml` 示例，包含所有常用配置项及说明：

```toml
[reddit.creds]
username = "你的Reddit用户名"
password = "你的Reddit密码"

[reddit.thread]
subreddit = "AskReddit"        # 目标 subreddit
post_id = ""                   # 指定帖子 ID（留空自动选取）
max_comment_length = 500       # 评论最大字符数
min_comment_length = 1         # 评论最小字符数
min_comments = 20              # 帖子最少评论数
blocked_words = ""             # 屏蔽词，逗号分隔

[ai]
ai_similarity_enabled = false
ai_similarity_keywords = ""

[settings]
theme = "dark"                 # dark / light / transparent
storymode = false              # true = 故事模式，false = 评论模式
storymode_max_length = 1000    # 故事模式正文最大字符数
resolution_w = 1080
resolution_h = 1920
opacity = 0.9
zoom = 1.0
allow_nsfw = false
channel_name = "Reddit Tales"
times_to_run = 1

[settings.background]
background_video = "minecraft"          # 背景视频，留空随机
background_audio = "lofi"              # 背景音乐，留空随机
background_audio_volume = 0.15
enable_extra_audio = false
background_thumbnail = false
background_thumbnail_font_family = "arial"
background_thumbnail_font_size = 96
background_thumbnail_font_color = "255,255,255"

[settings.tts]
doubao_app_id = "你的AppID"
doubao_access_token = "你的AccessToken"
doubao_resource_id = "seed-tts-2.0"
doubao_speaker = "zh_female_xiaohe_uranus_bigtts"
random_voice = false
silence_duration = 0.3
no_emojis = false

[settings.translation]
translation_enabled = true
llm_api_url = "https://api.openai.com/v1"
llm_api_key = "sk-xxxxxxxx"
llm_model = "gpt-4o-mini"
```

---

## 免责声明 🚨

- 本程序**不会**自动上传生成的视频，需手动上传到各平台。
- 请遵守 Reddit 使用条款和各平台版权规定。

## 视频示例

https://user-images.githubusercontent.com/66544866/173453972-6526e4e6-c6ef-41c5-ab40-5d275e724e7c.mp4

## 贡献与改进 📈

欢迎提交 PR 和 Issue！请阅读 [贡献指南](CONTRIBUTING.md)。

## 开发者

Cygra - https://github.com/Cygra（本仓库作者）

Elebumm (Lewis) - https://github.com/elebumm（原作者）

Jason Cameron - https://github.com/JasonLovesDoggo（维护者）

更多贡献者请查看 GitHub Contributors 页面。

## 许可证
- [Roboto 字体](https://fonts.google.com/specimen/Roboto/about) 使用 [Apache License V2](https://www.apache.org/licenses/LICENSE-2.0) 授权
- [Noto Sans CJK SC 字体](https://github.com/notofonts/noto-cjk) 使用 [SIL Open Font License](https://scripts.sil.org/OFL) 授权
