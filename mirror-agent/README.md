# 镜子虾 Mirror Agent

一个住在镜子里的 AI 护肤闺蜜 Agent。当前默认走本地 `Ollama + gemma4:e2b`，也保留第三方 OpenAI 兼容接口作为回退，支持：

- 本地 `gemma4:e2b` 文本对话
- 本地 `gemma4:e2b` 图片理解
- 本地 Markdown Memory
- 本地护肤知识库检索

## 快速开始

```bash
cd mirror-agent
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
brew services start ollama
python main.py
```

如果你后面想开语音模式，第一次建议先把系统依赖补上：

```bash
brew install ffmpeg portaudio
```

默认会读取本地 `Ollama`：

```bash
export OLLAMA_BASE_URL="http://127.0.0.1:11434"
export OLLAMA_CHAT_MODEL="gemma4:e2b"
python main.py
```

如果你想切回第三方转发，再显式设置：

```bash
export MIRROR_AGENT_PROVIDER="aiping"
export AIPING_API_KEY="你的第三方转发 Key"
python main.py
```

## 图片命令

```bash
/image "/绝对路径/skin.jpg" 今天脸颊有点红
```

也支持更自然一点的自拍流程：

```text
你：看看我
镜子虾：好嘞，发张照片过来～ 你也可以直接把本地自拍路径贴给我。
你：/Users/yourname/Desktop/selfie.jpg
```

注意：MVP 先按 `jpg/png/webp/bmp` 这些常见图片格式走，本地路径直接发整行就行。

## 网页版启动

```bash
cd mirror-agent
source .venv/bin/activate
python webapp.py
```

然后打开 [http://127.0.0.1:8000](http://127.0.0.1:8000)。

## 语音模式

```bash
cd mirror-agent
source .venv/bin/activate
python main.py --voice
```

语音模式流程：

```text
麦克风监听 -> 说“小镜” -> Whisper 转文字 -> Agent 回复 -> Edge-TTS 播放
```

默认配置：

- 唤醒词：`小镜`
- Whisper 模型：`small`
- TTS 声音：`zh-CN-XiaoyiNeural`

如果你想切换本地转写模型，可以在启动前设置：

```bash
export MIRROR_AGENT_WHISPER_MODEL="medium"
python main.py --voice
```

如果语音模式报错，优先检查：

- macOS 是否给终端/IDE 开了麦克风权限
- `ffmpeg` 和 `portaudio` 是否已安装
- 本地网络是否允许 `edge-tts` 出网合成语音

## 本地 Gemma 4 E2B

如果你想让“镜子虾”后续走本地模型，可以直接用 Ollama 提供的本地服务。

### 启动与模型名

```bash
brew services start ollama
ollama list
ollama run gemma4:e2b "用一句中文介绍自己"
```

本地服务地址：

```text
http://127.0.0.1:11434
```

模型名：

```text
gemma4:e2b
```

### curl 调用示例

```bash
curl http://127.0.0.1:11434/api/generate \
  -d '{
    "model": "gemma4:e2b",
    "prompt": "请只输出最终答案，不要展示思考过程。你是镜子虾，请用两句中文安慰一个熬夜后皮肤状态不好的用户。",
    "stream": false
  }'
```

### Python 调用示例

```python
import requests

response = requests.post(
    "http://127.0.0.1:11434/api/generate",
    json={
        "model": "gemma4:e2b",
        "prompt": "请只输出最终答案，不要展示思考过程。你是镜子虾，请用两句中文安慰一个熬夜后皮肤状态不好的用户。",
        "stream": False,
    },
    timeout=120,
)
response.raise_for_status()
print(response.json()["response"])
```

第一次推理通常会慢一些，我这边实测首轮完整返回大约 10-20 秒，后续会快不少。

## 目录说明

- `main.py`：CLI 入口
- `agent.py`：Agent 核心循环和工具调用
- `tools.py`：工具定义与实现
- `memory.py`：Markdown Memory 读写
- `webapp.py`：本地 Web 服务
- `knowledge/skincare.md`：护肤知识库
- `memory/`：用户画像、日记、洞察
