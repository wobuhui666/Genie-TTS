"""
Genie-TTS OpenAI Compatible API Server
======================================

This server provides an OpenAI-compatible TTS API endpoint (/v1/audio/speech)
for the Genie-TTS engine.

Usage:
    POST /v1/audio/speech
    {
        "model": "liang",           # Voice model name
        "input": "要合成的文本",     # Text to synthesize
        "voice": "alloy",           # Ignored - for OpenAI compatibility
        "response_format": "wav",   # Only wav is supported
        "speed": 1.0                # Ignored - for OpenAI compatibility
    }
"""

import os
import sys
import io
import wave
import json
import logging
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, Union
from contextlib import asynccontextmanager

import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response, StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Model configuration
MODELS_DIR = Path(os.environ.get("MODELS_DIR", "/app/models"))
VOICES: Dict[str, Dict[str, Any]] = {}

# Audio settings
SAMPLE_RATE = 32000
CHANNELS = 1
BYTES_PER_SAMPLE = 2


class SpeechRequest(BaseModel):
    """OpenAI-compatible speech request model."""
    model: str = Field(..., description="The voice model to use")
    input: str = Field(..., description="The text to synthesize")
    voice: Optional[str] = Field(default="alloy", description="Ignored - for OpenAI compatibility")
    response_format: Optional[str] = Field(default="wav", description="Only wav is supported")
    speed: Optional[float] = Field(default=1.0, description="Ignored - for OpenAI compatibility")


class ErrorResponse(BaseModel):
    """OpenAI-compatible error response."""
    error: Dict[str, Any]


def load_voice_config(voice_dir: Path) -> Optional[Dict[str, Any]]:
    """Load voice configuration from a directory."""
    config_path = voice_dir / "config.json"
    if not config_path.exists():
        logger.warning(f"Config file not found: {config_path}")
        return None
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        # Validate required fields
        required_fields = ["reference_audio", "reference_text", "language"]
        for field in required_fields:
            if field not in config:
                logger.error(f"Missing required field '{field}' in {config_path}")
                return None
        
        # Check if ONNX models exist
        onnx_dir = voice_dir / "onnx"
        if not onnx_dir.exists():
            logger.error(f"ONNX model directory not found: {onnx_dir}")
            return None
        
        config["onnx_dir"] = str(onnx_dir)
        config["voice_dir"] = str(voice_dir)
        
        return config
    except Exception as e:
        logger.error(f"Failed to load config from {config_path}: {e}")
        return None


def discover_voices() -> Dict[str, Dict[str, Any]]:
    """Discover all available voice models."""
    voices = {}
    
    if not MODELS_DIR.exists():
        logger.warning(f"Models directory not found: {MODELS_DIR}")
        return voices
    
    for voice_dir in MODELS_DIR.iterdir():
        if voice_dir.is_dir():
            voice_name = voice_dir.name
            config = load_voice_config(voice_dir)
            if config:
                voices[voice_name] = config
                logger.info(f"Loaded voice: {voice_name} (language: {config.get('language', 'unknown')})")
    
    return voices


def initialize_genie():
    """Initialize Genie-TTS engine and load all voice models."""
    global VOICES
    
    logger.info("Initializing Genie-TTS engine...")
    
    # Import genie_tts
    try:
        import genie_tts as genie
    except ImportError as e:
        logger.error(f"Failed to import genie_tts: {e}")
        raise
    
    # Download Genie data if needed
    logger.info("Checking Genie data...")
    genie.download_genie_data()
    
    # Discover and load voices
    VOICES = discover_voices()
    
    if not VOICES:
        logger.warning("No voice models found!")
        return
    
    # Load each voice model
    for voice_name, config in VOICES.items():
        try:
            logger.info(f"Loading voice model: {voice_name}")
            genie.load_character(
                character_name=voice_name,
                onnx_model_dir=config["onnx_dir"],
                language=config["language"]
            )
            
            # Set reference audio
            ref_audio_path = os.path.join(config["voice_dir"], config["reference_audio"])
            genie.set_reference_audio(
                character_name=voice_name,
                audio_path=ref_audio_path,
                audio_text=config["reference_text"],
                language=config["language"]
            )
            
            logger.info(f"Voice model loaded successfully: {voice_name}")
        except Exception as e:
            logger.error(f"Failed to load voice model {voice_name}: {e}")
            del VOICES[voice_name]
    
    logger.info(f"Genie-TTS initialized with {len(VOICES)} voice(s)")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    initialize_genie()
    yield
    # Shutdown
    logger.info("Shutting down Genie-TTS server...")


# Create FastAPI app
app = FastAPI(
    title="Genie-TTS OpenAI Compatible API",
    description="OpenAI-compatible Text-to-Speech API powered by Genie-TTS",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def root():
    """Root endpoint - health check."""
    return {
        "status": "healthy",
        "service": "Genie-TTS OpenAI Compatible API",
        "available_models": list(VOICES.keys())
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "models_loaded": len(VOICES),
        "available_models": list(VOICES.keys())
    }


@app.get("/v1/models")
async def list_models():
    """List available models (OpenAI-compatible)."""
    import time
    
    models = []
    for voice_name in VOICES.keys():
        models.append({
            "id": voice_name,
            "object": "model",
            "created": int(time.time()),
            "owned_by": "genie-tts"
        })
    
    return {
        "object": "list",
        "data": models
    }


def generate_wav_header(data_size: int) -> bytes:
    """Generate WAV file header."""
    header = io.BytesIO()
    
    # RIFF header
    header.write(b'RIFF')
    header.write((data_size + 36).to_bytes(4, 'little'))  # File size - 8
    header.write(b'WAVE')
    
    # fmt chunk
    header.write(b'fmt ')
    header.write((16).to_bytes(4, 'little'))  # Chunk size
    header.write((1).to_bytes(2, 'little'))   # Audio format (PCM)
    header.write((CHANNELS).to_bytes(2, 'little'))  # Number of channels
    header.write((SAMPLE_RATE).to_bytes(4, 'little'))  # Sample rate
    header.write((SAMPLE_RATE * CHANNELS * BYTES_PER_SAMPLE).to_bytes(4, 'little'))  # Byte rate
    header.write((CHANNELS * BYTES_PER_SAMPLE).to_bytes(2, 'little'))  # Block align
    header.write((BYTES_PER_SAMPLE * 8).to_bytes(2, 'little'))  # Bits per sample
    
    # data chunk
    header.write(b'data')
    header.write(data_size.to_bytes(4, 'little'))
    
    return header.getvalue()


@app.post("/v1/audio/speech")
async def create_speech(request: SpeechRequest):
    """
    Generate speech from text (OpenAI-compatible endpoint).
    
    This endpoint is compatible with the OpenAI TTS API format.
    Only the 'model' and 'input' parameters are used.
    """
    import genie_tts as genie
    
    # Validate model
    if request.model not in VOICES:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "message": f"Model '{request.model}' not found. Available models: {list(VOICES.keys())}",
                    "type": "invalid_request_error",
                    "code": "model_not_found"
                }
            }
        )
    
    # Validate input
    if not request.input or not request.input.strip():
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "message": "Input text cannot be empty",
                    "type": "invalid_request_error",
                    "code": "invalid_input"
                }
            }
        )
    
    try:
        # Collect audio chunks
        audio_chunks = []
        
        async for chunk in genie.tts_async(
            character_name=request.model,
            text=request.input.strip(),
            play=False,
            split_sentence=True
        ):
            audio_chunks.append(chunk)
        
        if not audio_chunks:
            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "message": "Failed to generate audio",
                        "type": "server_error",
                        "code": "generation_failed"
                    }
                }
            )
        
        # Combine all chunks
        audio_data = b''.join(audio_chunks)
        
        # Generate complete WAV file
        wav_header = generate_wav_header(len(audio_data))
        wav_content = wav_header + audio_data
        
        return Response(
            content=wav_content,
            media_type="audio/wav",
            headers={
                "Content-Disposition": "attachment; filename=speech.wav"
            }
        )
    
    except Exception as e:
        logger.error(f"TTS generation failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "message": f"TTS generation failed: {str(e)}",
                    "type": "server_error",
                    "code": "generation_failed"
                }
            }
        )


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=404,
        content={
            "error": {
                "message": "Not found",
                "type": "invalid_request_error",
                "code": "not_found"
            }
        }
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "message": "Internal server error",
                "type": "server_error",
                "code": "internal_error"
            }
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)