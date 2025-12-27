# 🚀 Hugging Face Space 部署指南

本指南将帮助你将 Genie-TTS OpenAI 兼容 API 部署到 Hugging Face Space。

## 📋 前置要求

1. Hugging Face 账号
2. 模型文件的下载链接（.pth 和 .ckpt）
3. 参考音频文件

## 🔧 部署步骤

### 步骤 1: 创建 Hugging Face Space

1. 访问 [Hugging Face Spaces](https://huggingface.co/spaces)
2. 点击 "Create new Space"
3. 填写信息：
   - **Space name**: 选择一个名称，如 `genie-tts-api`
   - **License**: MIT
   - **SDK**: Docker
   - **Hardware**: CPU Basic（免费）或更高配置
4. 点击 "Create Space"

### 步骤 2: 上传文件

将以下文件上传到你的 Space 仓库：

```
├── Dockerfile
├── app.py
├── requirements.txt
├── README.md
└── models/
    └── liang/
        └── config.json
```

**方法一：使用 Git**

```bash
# 克隆你的 Space 仓库
git clone https://huggingface.co/spaces/YOUR_USERNAME/YOUR_SPACE_NAME
cd YOUR_SPACE_NAME

# 复制文件
cp -r /path/to/huggingface-space/* .

# 提交并推送
git add .
git commit -m "Initial deployment"
git push
```

**方法二：使用 Web 界面**

1. 在 Space 页面点击 "Files" 标签
2. 点击 "Add file" > "Upload files"
3. 上传所有必要文件

### 步骤 3: 等待构建

- Space 会自动开始构建 Docker 镜像
- 构建过程包括：
  1. 安装依赖
  2. 下载模型文件
  3. 转换为 ONNX 格式
- 这个过程可能需要 10-30 分钟

### 步骤 4: 验证部署

构建完成后：

1. 访问健康检查端点：
   ```
   https://YOUR_USERNAME-YOUR_SPACE_NAME.hf.space/health
   ```

2. 测试 API：
   ```bash
   curl -X POST "https://YOUR_USERNAME-YOUR_SPACE_NAME.hf.space/v1/audio/speech" \
     -H "Content-Type: application/json" \
     -d '{"model": "liang", "input": "你好，这是测试。"}' \
     --output test.wav
   ```

## ⚙️ 自定义配置

### 添加新的语音模型

1. 修改 `Dockerfile`，添加新模型的下载和转换：

```dockerfile
# 下载新模型
RUN wget -O /app/temp/new_model.ckpt "YOUR_CKPT_URL" && \
    wget -O /app/temp/new_model.pth "YOUR_PTH_URL" && \
    wget -O /app/models/new_voice/reference/audio.wav "YOUR_REF_AUDIO_URL"

# 转换新模型
RUN python -c "
import genie_tts as genie
genie.convert_to_onnx(
    torch_ckpt_path='/app/temp/new_model.ckpt',
    torch_pth_path='/app/temp/new_model.pth',
    output_dir='/app/models/new_voice/onnx'
)
"
```

2. 创建配置文件 `models/new_voice/config.json`：

```json
{
    "reference_audio": "reference/audio.wav",
    "reference_text": "参考音频的文本内容",
    "language": "Chinese"
}
```

### 修改模型下载链接

编辑 `Dockerfile` 中的以下部分：

```dockerfile
RUN wget -O /app/temp/model.ckpt "YOUR_NEW_CKPT_URL" && \
    wget -O /app/temp/model.pth "YOUR_NEW_PTH_URL" && \
    wget -O /app/models/liang/reference/audio.wav "YOUR_NEW_REF_AUDIO_URL"
```

### 支持的语言

修改 `config.json` 中的 `language` 字段：

- `Chinese` - 中文
- `English` - 英语
- `Japanese` - 日语
- `Korean` - 韩语

## 🐛 故障排除

### 构建失败

1. **检查日志**：在 Space 页面查看构建日志
2. **模型下载失败**：确保下载链接可访问
3. **内存不足**：升级到更高配置的硬件

### API 响应慢

- 免费版 CPU 推理较慢，考虑升级硬件
- 首次请求会加载模型，后续请求会更快

### 模型加载失败

1. 检查 ONNX 转换是否成功
2. 确保 `config.json` 配置正确
3. 检查参考音频文件是否存在

## 💡 优化建议

### 减少镜像大小

构建完成后删除 PyTorch：

```dockerfile
RUN pip uninstall -y torch && rm -rf /root/.cache/pip
```

### 使用 GPU

1. 在 Space 设置中选择 GPU 硬件
2. 修改 `requirements.txt` 使用 GPU 版本的依赖

### 私有部署

如果需要私有部署，可以将 Space 设置为私有，并使用 Hugging Face Token 访问。

## 📞 获取帮助

- [Genie-TTS GitHub Issues](https://github.com/High-Logic/Genie-TTS/issues)
- [Hugging Face Spaces 文档](https://huggingface.co/docs/hub/spaces)