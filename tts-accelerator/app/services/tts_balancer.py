"""TTS 负载均衡器 - 支持多 HuggingFace Space 并行请求"""

import asyncio
import time
import logging
from typing import List, Optional, Dict
from dataclasses import dataclass, field
import httpx

logger = logging.getLogger(__name__)


@dataclass
class TTSEndpoint:
    """TTS 服务端点"""
    url: str
    is_available: bool = True
    current_load: int = 0
    last_request_time: float = 0
    error_count: int = 0
    total_requests: int = 0
    total_response_time: float = 0
    
    @property
    def avg_response_time(self) -> float:
        """平均响应时间"""
        if self.total_requests == 0:
            return 0
        return self.total_response_time / self.total_requests
    
    def record_success(self, response_time: float):
        """记录成功请求"""
        self.total_requests += 1
        self.total_response_time += response_time
        self.error_count = 0  # 重置连续错误计数
        self.is_available = True
    
    def record_failure(self):
        """记录失败请求"""
        self.error_count += 1
        # 连续 3 次失败后标记为不可用
        if self.error_count >= 3:
            self.is_available = False
            logger.warning(f"Endpoint {self.url} marked as unavailable after {self.error_count} consecutive errors")


class TTSLoadBalancer:
    """
    TTS 负载均衡器
    
    使用最少连接算法将请求分发到多个 HuggingFace Space，
    支持并发控制、失败重试和健康检查。
    """
    
    def __init__(
        self,
        endpoints: List[str],
        max_concurrent_per_endpoint: int = 3,
        request_timeout: int = 60,
        retry_count: int = 2,
    ):
        """
        初始化负载均衡器。
        
        :param endpoints: TTS 服务端点 URL 列表
        :param max_concurrent_per_endpoint: 每个端点最大并发数
        :param request_timeout: 请求超时时间（秒）
        :param retry_count: 失败重试次数
        """
        self.endpoints: List[TTSEndpoint] = [
            TTSEndpoint(url=url.rstrip('/')) for url in endpoints
        ]
        self.max_concurrent = max_concurrent_per_endpoint
        self.request_timeout = request_timeout
        self.retry_count = retry_count
        
        # 每个端点的信号量，控制并发
        self.semaphores: Dict[str, asyncio.Semaphore] = {
            ep.url: asyncio.Semaphore(max_concurrent_per_endpoint)
            for ep in self.endpoints
        }
        
        # HTTP 客户端
        self.client: Optional[httpx.AsyncClient] = None
        
        # 统计信息
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
    
    async def initialize(self):
        """初始化 HTTP 客户端"""
        if self.client is None:
            self.client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.request_timeout),
                follow_redirects=True,
            )
    
    async def close(self):
        """关闭 HTTP 客户端"""
        if self.client:
            await self.client.aclose()
            self.client = None
    
    def _select_endpoint(self) -> Optional[TTSEndpoint]:
        """
        选择最优端点（最少连接算法）。
        
        :return: 选中的端点，如果没有可用端点则返回 None
        """
        available = [ep for ep in self.endpoints if ep.is_available]
        
        if not available:
            # 如果所有端点都不可用，尝试重置状态
            logger.warning("All endpoints unavailable, attempting reset")
            for ep in self.endpoints:
                ep.is_available = True
                ep.error_count = 0
            available = self.endpoints
        
        # 按当前负载排序，选择负载最小的
        available.sort(key=lambda ep: (ep.current_load, ep.avg_response_time))
        return available[0] if available else None
    
    async def request(self, text: str, model: str) -> bytes:
        """
        发送 TTS 请求到最优端点。
        
        :param text: 要合成的文本
        :param model: TTS 模型名称
        :return: WAV 音频数据
        :raises: Exception 如果所有重试都失败
        """
        await self.initialize()
        
        self.total_requests += 1
        last_error = None
        
        for attempt in range(self.retry_count + 1):
            endpoint = self._select_endpoint()
            if endpoint is None:
                raise Exception("No available TTS endpoints")
            
            try:
                result = await self._do_request(endpoint, text, model)
                self.successful_requests += 1
                return result
            except Exception as e:
                last_error = e
                logger.warning(
                    f"TTS request failed (attempt {attempt + 1}/{self.retry_count + 1}): "
                    f"endpoint={endpoint.url}, error={e}"
                )
                
                if attempt < self.retry_count:
                    # 指数退避
                    await asyncio.sleep(0.5 * (2 ** attempt))
        
        self.failed_requests += 1
        raise Exception(f"All TTS request attempts failed: {last_error}")
    
    async def _do_request(self, endpoint: TTSEndpoint, text: str, model: str) -> bytes:
        """
        执行单个 TTS 请求。
        
        :param endpoint: 目标端点
        :param text: 要合成的文本
        :param model: TTS 模型名称
        :return: WAV 音频数据
        """
        async with self.semaphores[endpoint.url]:
            endpoint.current_load += 1
            endpoint.last_request_time = time.time()
            start_time = time.time()
            
            try:
                # 构造 OpenAI 兼容的 TTS 请求
                response = await self.client.post(
                    f"{endpoint.url}/v1/audio/speech",
                    json={
                        "model": model,
                        "input": text,
                        "voice": "alloy",
                        "response_format": "wav",
                    },
                    headers={
                        "Content-Type": "application/json",
                    },
                )
                
                response.raise_for_status()
                
                # 记录成功
                response_time = time.time() - start_time
                endpoint.record_success(response_time)
                
                logger.debug(
                    f"TTS request successful: endpoint={endpoint.url}, "
                    f"text_len={len(text)}, response_time={response_time:.2f}s"
                )
                
                return response.content
                
            except httpx.HTTPStatusError as e:
                endpoint.record_failure()
                raise Exception(f"HTTP error {e.response.status_code}: {e.response.text}")
            except httpx.TimeoutException:
                endpoint.record_failure()
                raise Exception("Request timeout")
            except Exception as e:
                endpoint.record_failure()
                raise Exception(f"Request failed: {e}")
            finally:
                endpoint.current_load -= 1
    
    async def health_check(self) -> Dict[str, bool]:
        """
        检查所有端点的健康状态。
        
        :return: 端点 URL 到健康状态的映射
        """
        await self.initialize()
        
        results = {}
        
        for endpoint in self.endpoints:
            try:
                response = await self.client.get(
                    f"{endpoint.url}/health",
                    timeout=10,
                )
                is_healthy = response.status_code == 200
                endpoint.is_available = is_healthy
                if is_healthy:
                    endpoint.error_count = 0
                results[endpoint.url] = is_healthy
            except Exception as e:
                logger.warning(f"Health check failed for {endpoint.url}: {e}")
                results[endpoint.url] = False
        
        return results
    
    def get_stats(self) -> Dict:
        """获取负载均衡器统计信息"""
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": (
                self.successful_requests / self.total_requests 
                if self.total_requests > 0 else 0
            ),
            "endpoints": [
                {
                    "url": ep.url,
                    "is_available": ep.is_available,
                    "current_load": ep.current_load,
                    "error_count": ep.error_count,
                    "avg_response_time": ep.avg_response_time,
                    "total_requests": ep.total_requests,
                }
                for ep in self.endpoints
            ],
        }