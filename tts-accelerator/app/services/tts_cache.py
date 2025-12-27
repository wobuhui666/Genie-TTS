"""TTS 缓存管理器 - 支持预生成和异步等待"""

import asyncio
import hashlib
import time
import logging
from typing import Optional, Dict, List
from dataclasses import dataclass, field
from enum import Enum

from .tts_balancer import TTSLoadBalancer

logger = logging.getLogger(__name__)


class CacheStatus(Enum):
    """缓存条目状态"""
    PENDING = "pending"        # 待生成
    GENERATING = "generating"  # 生成中
    COMPLETED = "completed"    # 已完成
    FAILED = "failed"          # 生成失败


@dataclass
class TTSCacheEntry:
    """TTS 缓存条目"""
    text: str                           # 原文本
    model: str                          # TTS 模型
    audio: Optional[bytes] = None       # 音频数据
    status: CacheStatus = CacheStatus.PENDING
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    error: Optional[str] = None
    # 用于等待生成完成的事件
    _event: asyncio.Event = field(default_factory=asyncio.Event)
    
    @property
    def generation_time(self) -> Optional[float]:
        """生成耗时"""
        if self.completed_at and self.created_at:
            return self.completed_at - self.created_at
        return None


class TTSCacheManager:
    """
    TTS 缓存管理器
    
    支持：
    - 预提交文本到生成队列
    - 异步等待正在生成的 TTS
    - LRU + TTL 缓存淘汰
    - 缓存统计
    """
    
    def __init__(
        self,
        balancer: TTSLoadBalancer,
        max_size: int = 1000,
        ttl: int = 3600,
        cleanup_interval: int = 300,
    ):
        """
        初始化缓存管理器。
        
        :param balancer: TTS 负载均衡器
        :param max_size: 最大缓存条目数
        :param ttl: 缓存过期时间（秒）
        :param cleanup_interval: 缓存清理间隔（秒）
        """
        self.balancer = balancer
        self.max_size = max_size
        self.ttl = ttl
        self.cleanup_interval = cleanup_interval
        
        # 缓存存储
        self._cache: Dict[str, TTSCacheEntry] = {}
        self._lock = asyncio.Lock()
        
        # 统计信息
        self.hit_count = 0
        self.miss_count = 0
        
        # 清理任务
        self._cleanup_task: Optional[asyncio.Task] = None
    
    def _generate_cache_key(self, text: str, model: str) -> str:
        """
        生成缓存 key。
        
        :param text: 文本内容
        :param model: TTS 模型名称
        :return: SHA256 哈希值
        """
        content = f"{model}:{text}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    async def start(self):
        """启动缓存管理器（包括定期清理任务）"""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("TTS cache manager started")
    
    async def stop(self):
        """停止缓存管理器"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
        logger.info("TTS cache manager stopped")
    
    async def _cleanup_loop(self):
        """定期清理过期缓存"""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cache cleanup error: {e}")
    
    async def _cleanup_expired(self):
        """清理过期的缓存条目"""
        async with self._lock:
            now = time.time()
            expired_keys = [
                key for key, entry in self._cache.items()
                if now - entry.created_at > self.ttl
            ]
            
            for key in expired_keys:
                del self._cache[key]
            
            if expired_keys:
                logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    async def _evict_if_needed(self):
        """如果缓存满了，淘汰最旧的条目"""
        if len(self._cache) >= self.max_size:
            # 按创建时间排序，删除最旧的 10%
            entries = sorted(
                self._cache.items(),
                key=lambda x: x[1].created_at
            )
            to_remove = max(1, len(entries) // 10)
            
            for key, _ in entries[:to_remove]:
                del self._cache[key]
            
            logger.info(f"Evicted {to_remove} cache entries due to size limit")
    
    async def submit(self, text: str, model: str) -> str:
        """
        提交文本到预生成队列。
        
        :param text: 要合成的文本
        :param model: TTS 模型名称
        :return: 缓存 key
        """
        cache_key = self._generate_cache_key(text, model)
        
        async with self._lock:
            # 检查是否已存在
            if cache_key in self._cache:
                logger.debug(f"Cache entry already exists: {cache_key[:16]}...")
                return cache_key
            
            # 淘汰旧条目
            await self._evict_if_needed()
            
            # 创建新条目
            entry = TTSCacheEntry(text=text, model=model)
            self._cache[cache_key] = entry
        
        # 启动异步生成任务
        asyncio.create_task(self._generate(cache_key))
        
        logger.debug(f"Submitted TTS generation: {cache_key[:16]}..., text_len={len(text)}")
        return cache_key
    
    async def _generate(self, cache_key: str):
        """
        执行 TTS 生成。
        
        :param cache_key: 缓存 key
        """
        async with self._lock:
            entry = self._cache.get(cache_key)
            if entry is None:
                return
            entry.status = CacheStatus.GENERATING
        
        try:
            # 调用负载均衡器生成 TTS
            audio = await self.balancer.request(entry.text, entry.model)
            
            async with self._lock:
                entry = self._cache.get(cache_key)
                if entry:
                    entry.audio = audio
                    entry.status = CacheStatus.COMPLETED
                    entry.completed_at = time.time()
                    entry._event.set()
            
            logger.debug(
                f"TTS generation completed: {cache_key[:16]}..., "
                f"audio_size={len(audio)}, time={entry.generation_time:.2f}s"
            )
            
        except Exception as e:
            async with self._lock:
                entry = self._cache.get(cache_key)
                if entry:
                    entry.status = CacheStatus.FAILED
                    entry.error = str(e)
                    entry._event.set()
            
            logger.error(f"TTS generation failed: {cache_key[:16]}..., error={e}")
    
    async def get(
        self,
        text: str,
        model: str,
        timeout: float = 60,
        generate_if_missing: bool = True,
    ) -> Optional[bytes]:
        """
        获取 TTS 音频。
        
        :param text: 文本内容
        :param model: TTS 模型名称
        :param timeout: 等待超时时间（秒）
        :param generate_if_missing: 如果缓存未命中是否现场生成
        :return: WAV 音频数据，如果失败则返回 None
        """
        cache_key = self._generate_cache_key(text, model)
        
        async with self._lock:
            entry = self._cache.get(cache_key)
        
        if entry is None:
            self.miss_count += 1
            
            if not generate_if_missing:
                return None
            
            # 现场生成
            logger.debug(f"Cache miss, generating on-demand: {cache_key[:16]}...")
            await self.submit(text, model)
            
            async with self._lock:
                entry = self._cache.get(cache_key)
        else:
            self.hit_count += 1
        
        if entry is None:
            return None
        
        # 如果已完成，直接返回
        if entry.status == CacheStatus.COMPLETED:
            return entry.audio
        
        # 如果失败，返回 None
        if entry.status == CacheStatus.FAILED:
            logger.warning(f"Returning None for failed entry: {cache_key[:16]}...")
            return None
        
        # 等待生成完成
        try:
            await asyncio.wait_for(entry._event.wait(), timeout=timeout)
            
            if entry.status == CacheStatus.COMPLETED:
                return entry.audio
            else:
                return None
                
        except asyncio.TimeoutError:
            logger.warning(f"Timeout waiting for TTS generation: {cache_key[:16]}...")
            return None
    
    async def get_by_key(self, cache_key: str, timeout: float = 60) -> Optional[bytes]:
        """
        通过缓存 key 获取 TTS 音频。
        
        :param cache_key: 缓存 key
        :param timeout: 等待超时时间（秒）
        :return: WAV 音频数据，如果失败则返回 None
        """
        async with self._lock:
            entry = self._cache.get(cache_key)
        
        if entry is None:
            return None
        
        if entry.status == CacheStatus.COMPLETED:
            return entry.audio
        
        if entry.status == CacheStatus.FAILED:
            return None
        
        try:
            await asyncio.wait_for(entry._event.wait(), timeout=timeout)
            return entry.audio if entry.status == CacheStatus.COMPLETED else None
        except asyncio.TimeoutError:
            return None
    
    def get_stats(self) -> Dict:
        """获取缓存统计信息"""
        status_counts = {status: 0 for status in CacheStatus}
        for entry in self._cache.values():
            status_counts[entry.status] += 1
        
        total_requests = self.hit_count + self.miss_count
        hit_rate = self.hit_count / total_requests if total_requests > 0 else 0
        
        return {
            "total_entries": len(self._cache),
            "completed_entries": status_counts[CacheStatus.COMPLETED],
            "pending_entries": status_counts[CacheStatus.PENDING],
            "generating_entries": status_counts[CacheStatus.GENERATING],
            "failed_entries": status_counts[CacheStatus.FAILED],
            "hit_count": self.hit_count,
            "miss_count": self.miss_count,
            "hit_rate": hit_rate,
        }
    
    async def clear(self):
        """清空缓存"""
        async with self._lock:
            self._cache.clear()
        logger.info("Cache cleared")