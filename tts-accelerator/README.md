# TTS Accelerator

智能 TTS 预取代理服务 - 在流式返回 LLM 响应的同时并行预生成 TTS，大幅减少用户等待 TTS 的时间。

## 功能特性

- ✅ **OpenAI 兼容** - 完全兼容 OpenAI Chat Completion 和 TTS API 格式
- ✅ **流式响应** - 支持流式返回 LLM 响应
- ✅ **TTS 预生成** - 在流式接收文本的同时异步预生成 TTS
- ✅ **多 Space 负载均衡** - 支持多个 HuggingFace Space 并行处理
- ✅ **智能缓存** - 使用内存缓存，支持 LRU + TTL 淘汰策略
- ✅ **按句分段** - 智能按句子分段，确保 TTS 质量
- ✅ **API 鉴权** - 支持 Bearer Token 验证，保护 API 端点

## 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    TTS 加速代理服务                          │
│                                                             │
│  用户请求 ──► Chat API 反代 ──► NewAPI (流式)               │
│                    │                                        │
│                    ▼                                        │
│              文本分段器 ──► TTS 缓存管理器                    │
│                              │                              │
│                              ▼                              │
│                        负载均衡器                            │
│                    ┌────┬────┬────┐                         │
│                    │ S1 │ S2 │ S3 │  ◄── HF Spaces          │
│                    └────┴────┴────┘                         │
│                                                             │
│  用户请求 TTS ──► 从缓存获取 ──► 返回音频                    │
└─────────────────────────────────────────────────────────────┘
```

## 快速开始

### 1. 配置环境变量

复制示例配置文件并填入实际值：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```bash
# 必需配置
NEWAPI_BASE_URL=https://your-newapi.com
NEWAPI_API_KEY=sk-xxxx
TTS_ENDPOINTS=https://space1.hf.space,https://space2.hf.space

# 可选配置
TTS_DEFAULT_MODEL=liang
```

### 2. Docker 部署（推荐）

```bash
# 构建并启动
docker-compose up -d

# 查看日志
docker-compose logs -f
```

### 3. 本地运行

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## API 接口

### API 鉴权

`/v1/chat/completions` 和 `/v1/audio/speech` 端点需要 API 鉴权。请在请求头中包含 `Authorization` 头，使用与 `NEWAPI_API_KEY` 相同的值：

```bash
Authorization: Bearer sk-xxxx
```

其中 `sk-xxxx` 是您在 `.env` 文件中配置的 `NEWAPI_API_KEY` 值。

**无需鉴权的端点**：
- `/` - 服务信息
- `/health` - 健康检查
- `/cache/stats` - 缓存统计
- `/cache/clear` - 清空缓存
- `/v1/models` - 列出模型
- `/v1/audio/models` - 列出 TTS 模型

### Chat Completion（反向代理）

与 OpenAI Chat Completion API 完全兼容：

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-xxxx" \
  -d '{
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "你好"}],
    "stream": true
  }'
```

**特殊参数**：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `tts_enabled` | bool | true | 是否启用 TTS 预生成 |
| `tts_model` | string | 配置默认值 | TTS 模型名称 |

### TTS 语音合成

与 OpenAI TTS API 兼容：

```bash
curl -X POST http://localhost:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-xxxx" \
  -d '{
    "model": "liang",
    "input": "要合成的文本"
  }' \
  --output speech.wav
```

### 健康检查

```bash
curl http://localhost:8000/health
```

### 缓存统计

```bash
curl http://localhost:8000/cache/stats
```

## 配置说明

| 环境变量 | 必需 | 默认值 | 说明 |
|----------|------|--------|------|
| `NEWAPI_BASE_URL` | ✅ | - | NewAPI 基础 URL |
| `NEWAPI_API_KEY` | ✅ | - | NewAPI API Key |
| `TTS_ENDPOINTS` | ✅ | - | TTS 服务端点，逗号分隔 |
| `TTS_DEFAULT_MODEL` | ❌ | liang | 默认 TTS 模型 |
| `TTS_MAX_CONCURRENT_PER_ENDPOINT` | ❌ | 3 | 每端点最大并发 |
| `TTS_REQUEST_TIMEOUT` | ❌ | 60 | TTS 请求超时（秒） |
| `CACHE_MAX_SIZE` | ❌ | 1000 | 缓存最大条目数 |
| `CACHE_TTL` | ❌ | 3600 | 缓存过期时间（秒） |
| `LOG_LEVEL` | ❌ | INFO | 日志级别 |

## 工作原理

1. **接收 Chat 请求**：代理接收 OpenAI 格式的 Chat Completion 请求
2. **流式转发**：无论原请求是否流式，都向 NewAPI 发起流式请求
3. **文本分段**：使用智能分段器按句子分割流式文本
4. **TTS 预生成**：每个完整句子异步提交到 TTS 缓存管理器
5. **负载均衡**：TTS 请求分发到多个 HuggingFace Space 并行处理
6. **返回响应**：流式文本立即返回，不等待 TTS 完成
7. **获取 TTS**：后续请求 TTS 时从缓存获取（如正在生成则等待）

## 性能优化建议

1. **增加 TTS 端点**：配置更多 HuggingFace Space 以提高并行度
2. **调整并发数**：根据 Space 性能调整 `TTS_MAX_CONCURRENT_PER_ENDPOINT`
3. **优化分段长度**：调整 `SPLITTER_MAX_LEN` 和 `SPLITTER_MIN_LEN`
4. **增加缓存大小**：根据内存情况调整 `CACHE_MAX_SIZE`

## 许可证

MIT License