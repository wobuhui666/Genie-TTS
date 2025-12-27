# Genie-TTS OpenAI Compatible API - Docker Image
# ================================================
# This Dockerfile builds a container that:
# 1. Downloads PyTorch model files (.pth, .ckpt) from cloud URLs
# 2. Converts them to ONNX format
# 3. Runs the OpenAI-compatible TTS API server

FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive \
    MODELS_DIR=/app/models \
    GENIE_DATA_DIR=/app/genie_data

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libsndfile1 \
    ffmpeg \
    wget \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies (including torch for model conversion)
RUN pip install --no-cache-dir -r requirements.txt

# Install PyTorch (CPU version for model conversion)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install genie-tts from source or pip
# Option 1: Install from pip
RUN pip install --no-cache-dir genie-tts

# Create directories
RUN mkdir -p /app/models/liang/onnx \
    && mkdir -p /app/models/liang/reference \
    && mkdir -p /app/genie_data \
    && mkdir -p /app/temp

# Download model files
# Model: liang (Chinese V2ProPlus)
RUN echo "Downloading model files..." && \
    wget -q --show-progress -O /app/temp/model.ckpt \
    "https://22333misaka-openlist.hf.space/d/od/shantianliang_proplus_e32.ckpt" && \
    wget -q --show-progress -O /app/temp/model.pth \
    "https://22333misaka-openlist.hf.space/d/od/shantianliang_proplus_e8_s192.pth" && \
    wget -q --show-progress -O /app/models/liang/reference/audio.wav \
    "https://22333misaka-openlist.hf.space/d/od/ref_shantianliang_1.wav" && \
    echo "Download complete!"

# Convert PyTorch models to ONNX
RUN echo "Converting models to ONNX format..." && \
    python -c "
import genie_tts as genie
print('Starting ONNX conversion...')
genie.convert_to_onnx(
    torch_ckpt_path='/app/temp/model.ckpt',
    torch_pth_path='/app/temp/model.pth',
    output_dir='/app/models/liang/onnx'
)
print('ONNX conversion complete!')
" && \
    echo "Conversion complete!"

# Clean up temporary files and torch to reduce image size
RUN rm -rf /app/temp && \
    pip uninstall -y torch && \
    rm -rf /root/.cache/pip

# Create model configuration
RUN echo '{\n\
    "reference_audio": "reference/audio.wav",\n\
    "reference_text": "这是一条参考音频，将此音频拖入参考内，再添加文本，即可合成音色",\n\
    "language": "Chinese"\n\
}' > /app/models/liang/config.json

# Copy application code
COPY app.py .

# Download Genie base data
RUN python -c "import genie_tts; genie_tts.download_genie_data()"

# Expose port (Hugging Face Spaces uses 7860)
EXPOSE 7860

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:7860/health || exit 1

# Run the application
CMD ["python", "app.py"]