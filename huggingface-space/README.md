---
title: Genie-TTS OpenAI Compatible API
emoji: 🔮
colorFrom: purple
colorTo: blue
sdk: docker
pinned: false
license: mit
---

# 🔮 Genie-TTS OpenAI Compatible API

基于 [Genie-TTS](https://github.com/High-Logic/Genie-TTS) 的 OpenAI 兼容 TTS API 服务。

## 🚀 功能特点

- ✅ **OpenAI API 兼容** - 使用 `/v1/audio/speech` 端点，兼容 OpenAI SDK
- ✅ **高质量语音合成** - 基于 GPT-SoVITS V2ProPlus 模型
- ✅ **中文支持** - 目前支持中文语音合成
- ✅ **WAV 输出** - 32kHz 高质量音频输出

## 📖 API 使用方法

### 端点

```
POST /v1/audio/speech
```

### 请求格式

```json
{
    "model": "liang",
    "input": "你好，这是一段测试文本。"
}
```

### 请求参数

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `model` | string | ✅ | 语音模型名称 |
| `input` | string | ✅ | 要合成的文本 |
| `voice` | string | ❌ | 忽略 - 仅用于 OpenAI 兼容性 |
| `response_format` | string | ❌ | 忽略 - 只支持 wav |
| `speed` | number | ❌ | 忽略 - 仅用于 OpenAI 兼容性 |

### 响应

- Content-Type: `audio/wav`
- 返回 WAV 格式的音频二进制数据

## 💻 使用示例

### 使用 curl

```bash
curl -X POST "https://your-space.hf.space/v1/audio/speech" \
  -H "Content-Type: application/json" \
  -d '{"model": "liang", "input": "你好，欢迎使用语音合成服务。"}' \
  --output speech.wav
```

### 使用 Python requests

```python
import requests

response = requests.post(
    "https://your-space.hf.space/v1/audio/speech",
    json={
        "model": "liang",
        "input": "你好，这是一段测试文本。"
    }
)

with open("speech.wav", "wb") as f:
    f.write(response.content)
```

### 使用 OpenAI Python SDK

```python
from openai import OpenAI

client = OpenAI(
    api_key="not-needed",  # API key 不需要
    base_url="https://your-space.hf.space/v1"
)

response = client.audio.speech.create(
    model="liang",
    input="你好，这是一段测试文本。",
    voice="alloy"  # 会被忽略
)

response.stream_to_file("speech.wav")
```

## 🔧 其他端点

### 健康检查

```
GET /health
```

响应:
```json
{
    "status": "healthy",
    "models_loaded": 1,
    "available_models": ["liang"]
}
```

### 列出可用模型

```
GET /v1/models
```

响应:
```json
{
    "object": "list",
    "data": [
        {
            "id": "liang",
            "object": "model",
            "created": 1234567890,
            "owned_by": "genie-tts"
        }
    ]
}
```

## 📝 可用模型

| 模型名称 | 语言 | 说明 |
|----------|------|------|
| `liang` | 中文 | GPT-SoVITS V2ProPlus 模型 |

## ⚠️ 注意事项

1. 首次加载可能需要一些时间
2. 免费版 CPU 推理可能较慢
3. 音频输出固定为 WAV 格式 (32kHz, 16-bit, 单声道)

## 🔗 相关链接

- [Genie-TTS GitHub](https://github.com/High-Logic/Genie-TTS)
- [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS)

## 📄 许可证

MIT License