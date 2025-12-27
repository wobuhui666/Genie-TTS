"""TTS 加速代理服务 - 主入口"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers import chat_router, speech_router
from .services.proxy_client import ProxyClient
from .services.tts_balancer import TTSLoadBalancer
from .services.tts_cache import TTSCacheManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    settings = get_settings()
    
    # 配置日志级别
    logging.getLogger().setLevel(getattr(logging, settings.log_level.upper()))
    
    logger.info("Starting TTS Accelerator...")
    logger.info(f"NewAPI URL: {settings.newapi_base_url}")
    logger.info(f"TTS Endpoints: {settings.tts_endpoint_list}")
    
    # 初始化代理客户端
    proxy_client = ProxyClient(
        base_url=settings.newapi_base_url,
        api_key=settings.newapi_api_key,
        timeout=settings.newapi_timeout,
    )
    await proxy_client.initialize()
    app.state.proxy_client = proxy_client
    
    # 初始化 TTS 负载均衡器
    tts_balancer = TTSLoadBalancer(
        endpoints=settings.tts_endpoint_list,
        max_concurrent_per_endpoint=settings.tts_max_concurrent_per_endpoint,
        request_timeout=settings.tts_request_timeout,
        retry_count=settings.tts_retry_count,
    )
    await tts_balancer.initialize()
    app.state.tts_balancer = tts_balancer
    
    # 初始化 TTS 缓存管理器
    tts_cache = TTSCacheManager(
        balancer=tts_balancer,
        max_size=settings.cache_max_size,
        ttl=settings.cache_ttl,
        cleanup_interval=settings.cache_cleanup_interval,
    )
    await tts_cache.start()
    app.state.tts_cache = tts_cache
    
    logger.info("TTS Accelerator started successfully!")
    
    yield
    
    # 清理资源
    logger.info("Shutting down TTS Accelerator...")
    await tts_cache.stop()
    await tts_balancer.close()
    await proxy_client.close()
    logger.info("TTS Accelerator stopped.")


# 创建 FastAPI 应用
app = FastAPI(
    title="TTS Accelerator",
    description="智能 TTS 预取代理服务 - 在流式返回 LLM 响应的同时并行预生成 TTS",
    version="1.0.0",
    lifespan=lifespan,
)

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(chat_router)
app.include_router(speech_router)


@app.get("/")
async def root():
    """根路径 - 服务信息"""
    return {
        "service": "TTS Accelerator",
        "version": "1.0.0",
        "description": "智能 TTS 预取代理服务",
    }


@app.get("/health")
async def health():
    """健康检查"""
    settings = get_settings()
    tts_cache = app.state.tts_cache
    tts_balancer = app.state.tts_balancer
    
    return {
        "status": "healthy",
        "version": "1.0.0",
        "cache_stats": tts_cache.get_stats(),
        "balancer_stats": tts_balancer.get_stats(),
    }


@app.get("/cache/stats")
async def cache_stats():
    """缓存统计"""
    tts_cache = app.state.tts_cache
    return tts_cache.get_stats()


@app.post("/cache/clear")
async def clear_cache():
    """清空缓存"""
    tts_cache = app.state.tts_cache
    await tts_cache.clear()
    return {"status": "success", "message": "Cache cleared"}


@app.get("/v1/models")
async def list_models():
    """列出可用模型 - OpenAI 兼容"""
    import time
    settings = get_settings()
    
    return {
        "object": "list",
        "data": [
            {
                "id": settings.tts_default_model,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "genie-tts",
            }
        ]
    }


# 错误处理
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(
        status_code=404,
        content={
            "error": {
                "message": "Not found",
                "type": "invalid_request_error",
                "code": "not_found",
            }
        }
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    logger.error(f"Internal error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "message": "Internal server error",
                "type": "server_error",
                "code": "internal_error",
            }
        }
    )


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(app, host=settings.host, port=settings.port)