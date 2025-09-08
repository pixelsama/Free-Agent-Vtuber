"""
消息格式定义 - 符合集成方案的Redis消息格式
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MemoryUpdateMessage(BaseModel):
    """memory_updates频道消息格式"""
    user_id: str = Field(description="用户ID")
    content: str = Field(description="消息内容")
    source: str = Field(description="消息来源", default="conversation")
    timestamp: int = Field(description="时间戳")
    meta: Optional[Dict[str, Any]] = Field(description="元数据", default_factory=dict)


class LTMRequest(BaseModel):
    """ltm_requests队列请求格式"""
    request_id: str = Field(description="请求ID")
    type: str = Field(description="请求类型: search|add|profile_get|profile_update")
    user_id: str = Field(description="用户ID")
    data: Dict[str, Any] = Field(description="请求数据")


class LTMResponse(BaseModel):
    """ltm_responses发布响应格式"""
    request_id: str = Field(description="请求ID")
    user_id: str = Field(description="用户ID")
    success: bool = Field(description="操作是否成功", default=True)
    memories: Optional[List[Dict[str, Any]]] = Field(description="记忆数据", default_factory=list)
    user_profile: Optional[Dict[str, Any]] = Field(description="用户画像", default=None)
    error: Optional[str] = Field(description="错误信息", default=None)


class SearchRequest(BaseModel):
    """搜索请求数据"""
    query: str = Field(description="搜索查询")
    limit: int = Field(description="返回数量限制", default=5)
    threshold: Optional[float] = Field(description="相似度阈值", default=None)
    category: Optional[str] = Field(description="记忆分类过滤", default=None)


class AddMemoryRequest(BaseModel):
    """添加记忆请求数据"""
    content: str = Field(description="记忆内容")
    metadata: Dict[str, Any] = Field(description="记忆元数据", default_factory=dict)


class ProfileUpdateRequest(BaseModel):
    """用户画像更新请求数据"""
    updates: Dict[str, Any] = Field(description="画像更新数据")