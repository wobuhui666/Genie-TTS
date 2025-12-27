# Hugging Face Space 部署计划 - Genie-TTS OpenAI 兼容 API

## 📋 项目概述

将 Genie-TTS 项目部署到 Hugging Face Space，并提供 OpenAI TTS API 兼容的端点。

### 用户需求

- 使用自己的 GPT-SoVITS V2ProPlus 模型
- 提供 `/v1/audio/speech` 端点
- 仅需要 `text` 和 `model` 参数
- 返回 WAV 格式音频
- 使用 Docker 部署

---

## 🏗️ 系统架构

```mermaid
graph TB
    subgraph HuggingFace Space
        A[Docker Container] --> B[FastAPI Server]
        B --> C[/v1/audio/speech]
        B --> D[/health]
        C --> E[Genie-TTS Engine]
        E --> F[ONNX Models]
        E --> G[Reference Audio]
    end
    
    subgraph Client
        H[OpenAI SDK / HTTP Client]
    end
    
    H -->|POST /v1/audio/speech| C
    C -->|WAV Audio Stream| H
```

---

## 📁 文件结构

需要创建以下文件用于 Hugging Face Space 部署：

```
huggingface-space/
├── Dockerfile                 # Docker 构建文件
├── app.py                     # 主应用入口 - OpenAI 兼容 API
├── requirements.txt           # Python 依赖
├── README.md                  # Space 说明文档
├── models/                    # 模型目录 - 用户需要放置 ONNX 模型
│   └── your-voice/           # 每个声音一个目录
│       ├── tts_models/       # ONNX 模型文件
│       └── reference/        # 参考音频文件
│           ├── audio.wav     # 参考音频
│           └── config.json   # 配置文件 - 包含 text 和 language
└── .env.example              # 环境变量示例
```

---

## 🔧 详细实施步骤

### 步骤 1: 创建 OpenAI 兼容 API 端点

**文件**: `huggingface-space/app.py`

**OpenAI TTS API 请求格式**:
```json
{
  "model": "your-voice-name",
  "input": "要合成的文本",
  "voice": "alloy",           // 可选，忽略
  "response_format": "wav",   // 可选，只支持 wav
  "speed": 1.0                // 可选，忽略
}
```

**实现要点**:
1. 创建 `/v1/audio/speech` POST 端点
2. 接受 OpenAI 格式的请求体
3. `model` 参数映射到预加载的角色名
4. 返回 WAV 格式的流式音频响应
5. 应用启动时预加载所有模型

### 步骤 2: 创建 Dockerfile

**关键配置**:
- 基础镜像: Python 3.10
- 安装系统依赖: libsndfile, etc.
- 安装 Python 依赖
- 复制模型文件
- 暴露端口 7860 (Hugging Face Space 默认端口)

### 步骤 3: 模型配置结构

每个声音模型需要以下目录结构：

```
models/voice-name/
├── tts_models/
│   ├── t2s_encoder_fp32.bin
│   ├── t2s_encoder_fp32.onnx
│   ├── t2s_first_stage_decoder_fp32.onnx
│   ├── t2s_shared_fp16.bin
│   ├── t2s_stage_decoder_fp32.onnx
│   ├── vits_fp16.bin
│   ├── vits_fp32.onnx
│   ├── prompt_encoder_fp16.bin      # V2ProPlus 专用
│   └── prompt_encoder_fp32.onnx     # V2ProPlus 专用
└── reference/
    ├── audio.wav                     # 3-10秒的参考音频
    └── config.json                   # 配置文件
```

**config.json 格式**:
```json
{
  "text": "参考音频的文本内容",
  "language": "Chinese"
}
```

### 步骤 4: 创建部署指南

详细说明：
1. 如何转换 PyTorch 模型到 ONNX
2. 如何准备参考音频
3. 如何创建 Hugging Face Space
4. 如何上传模型和配置

---

## 📝 API 规范

### POST /v1/audio/speech

**请求头**:
```
Content-Type: application/json
Authorization: Bearer YOUR_API_KEY  // 可选，忽略
```

**请求体**:
```json
{
  "model": "string",           // 必需 - 声音模型名称
  "input": "string",           // 必需 - 要合成的文本
  "voice": "string",           // 可选 - 忽略
  "response_format": "string", // 可选 - 只支持 wav，忽略其他值
  "speed": "number"            // 可选 - 忽略
}
```

**响应**:
- Content-Type: `audio/wav`
- Body: WAV 音频二进制数据

**错误响应**:
```json
{
  "error": {
    "message": "错误描述",
    "type": "invalid_request_error",
    "code": "model_not_found"
  }
}
```

### GET /health

健康检查端点

**响应**:
```json
{
  "status": "healthy",
  "models": ["voice1", "voice2"]
}
```

### GET /v1/models

列出可用模型（可选实现）

**响应**:
```json
{
  "object": "list",
  "data": [
    {
      "id": "voice-name",
      "object": "model",
      "created": 1234567890,
      "owned_by": "user"
    }
  ]
}
```

---

## 🚀 部署流程

### 1. 本地准备

```bash
# 1. 转换模型
python -c "
import genie_tts as genie
genie.convert_to_onnx(
    torch_pth_path='path/to/your.pth',
    torch_ckpt_path='path/to/your.ckpt',
    output_dir='models/your-voice/tts_models'
)
"

# 2. 准备参考音频
mkdir -p models/your-voice/reference
cp your-reference.wav models/your-voice/reference/audio.wav

# 3. 创建配置文件
echo '{"text": "参考音频文本", "language": "Chinese"}' > models/your-voice/reference/config.json
```

### 2. 创建 Hugging Face Space

1. 访问 https://huggingface.co/spaces
2. 创建新 Space，选择 Docker 类型
3. 上传所有文件

### 3. 使用 API

```python
import requests

response = requests.post(
    "https://your-space.hf.space/v1/audio/speech",
    json={
        "model": "your-voice",
        "input": "你好，这是测试文本。"
    }
)

with open("output.wav", "wb") as f:
    f.write(response.content)
```

或使用 OpenAI SDK（需配置 base_url）:

```python
from openai import OpenAI

client = OpenAI(
    api_key="not-needed",
    base_url="https://your-space.hf.space/v1"
)

response = client.audio.speech.create(
    model="your-voice",
    input="你好，这是测试文本。",
    voice="alloy"  # 会被忽略
)

response.stream_to_file("output.wav")
```

---

## ⚠️ 注意事项

1. **Hugging Face Space 限制**:
   - 免费版 CPU 限制，推理可能较慢
   - 存储限制：需要考虑模型大小

2. **模型文件大小**:
   - V2ProPlus 模型约 230MB
   - 参考音频建议 3-10 秒

3. **语言支持**:
   - Japanese, English, Chinese, Korean
   - 参考音频语言需与模型语言匹配

4. **音频格式**:
   - 输出固定为 WAV 格式
   - 采样率: 32000 Hz
   - 位深: 16-bit
   - 声道: 单声道

---

## 📋 待实现文件清单

| 文件 | 描述 | 优先级 |
|------|------|--------|
| `huggingface-space/app.py` | 主应用 - OpenAI 兼容 API | 高 |
| `huggingface-space/Dockerfile` | Docker 构建文件 | 高 |
| `huggingface-space/requirements.txt` | Python 依赖 | 高 |
| `huggingface-space/README.md` | Space 说明文档 | 中 |
| `docs/deployment-guide.md` | 详细部署指南 | 中 |

---

## 🔄 下一步

1. 审核此计划
2. 切换到 Code 模式实现具体代码
3. 测试 API 兼容性
4. 部署到 Hugging Face Space