"""Pydantic 数据模型 - OpenAI 兼容格式"""

from typing import List, Optional, Dict, Any, Literal, Union
from pydantic import BaseModel, Field


# ============== Chat Completion 相关模型 ==============

class Message(BaseModel):
    """对话消息"""
    role: Literal["system", "user", "assistant", "function", "tool"]
    content: Optional[str] = None
    name: Optional[str] = None
    function_call: Optional[Dict[str, Any]] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None


class ChatCompletionRequest(BaseModel):
    """Chat Completion 请求"""
    model: str
    messages: List[Message]
    temperature: Optional[float] = Field(default=1.0, ge=0, le=2)
    top_p: Optional[float] = Field(default=1.0, ge=0, le=1)
    n: Optional[int] = Field(default=1, ge=1)
    stream: Optional[bool] = False
    stop: Optional[Union[str, List[str]]] = None
    max_tokens: Optional[int] = None
    presence_penalty: Optional[float] = Field(default=0, ge=-2, le=2)
    frequency_penalty: Optional[float] = Field(default=0, ge=-2, le=2)
    logit_bias: Optional[Dict[str, float]] = None
    user: Optional[str] = None
    # 额外参数
    functions: Optional[List[Dict[str, Any]]] = None
    function_call: Optional[Union[str, Dict[str, str]]] = None
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None
    
    # TTS 加速器特有参数
    tts_enabled: Optional[bool] = Field(default=True, description="是否启用 TTS 预生成")
    tts_model: Optional[str] = Field(default=None, description="TTS 模型名称")


class Choice(BaseModel):
    """响应选项"""
    index: int
    message: Message
    finish_reason: Optional[str] = None


class Usage(BaseModel):
    """Token 使用量"""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    """Chat Completion 响应"""
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Choice]
    usage: Optional[Usage] = None


class Delta(BaseModel):
    """流式响应增量"""
    role: Optional[str] = None
    content: Optional[str] = None
    function_call: Optional[Dict[str, Any]] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None


class StreamChoice(BaseModel):
    """流式响应选项"""
    index: int
    delta: Delta
    finish_reason: Optional[str] = None


class ChatCompletionChunk(BaseModel):
    """Chat Completion 流式响应块"""
    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: List[StreamChoice]


# ============== TTS 相关模型 ==============

class SpeechRequest(BaseModel):
    """TTS 请求 - OpenAI 兼容格式"""
    model: str = Field(..., description="TTS 模型名称")
    input: str = Field(..., description="要合成的文本")
    voice: Optional[str] = Field(default="alloy", description="语音（兼容性参数）")
    response_format: Optional[str] = Field(default="wav", description="响应格式")
    speed: Optional[float] = Field(default=1.0, description="语速（兼容性参数）")


class TTSCacheStats(BaseModel):
    """TTS 缓存统计"""
    total_entries: int
    completed_entries: int
    pending_entries: int
    generating_entries: int
    failed_entries: int
    hit_count: int
    miss_count: int
    hit_rate: float


class EndpointStatus(BaseModel):
    """TTS 端点状态"""
    url: str
    is_available: bool
    current_load: int
    error_count: int
    avg_response_time: float


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    version: str
    tts_endpoints: List[EndpointStatus]
    cache_stats: TTSCacheStats


class ErrorResponse(BaseModel):
    """错误响应"""
    error: Dict[str, Any]