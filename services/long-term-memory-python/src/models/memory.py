"""
记忆数据模型定义
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MemoryCategory(str, Enum):
    """记忆分类枚举"""
    PREFERENCE = "preference"  # 用户偏好
    PERSONALITY = "personality"  # 性格特征
    HABIT = "habit"  # 行为习惯
    HISTORY = "history"  # 重要事件
    CONTEXT = "context"  # 对话上下文


class MemoryMetadata(BaseModel):
    """记忆元数据"""
    category: MemoryCategory = Field(description="记忆分类")
    confidence: float = Field(description="置信度", ge=0.0, le=1.0, default=0.8)
    source: str = Field(description="来源", default="conversation")
    tags: List[str] = Field(description="标签列表", default_factory=list)
    created_at: datetime = Field(description="创建时间", default_factory=datetime.now)
    updated_at: Optional[datetime] = Field(description="更新时间", default=None)


class UserMemory(BaseModel):
    """用户记忆数据结构"""
    user_id: str = Field(description="用户ID")
    content: str = Field(description="记忆内容")
    metadata: MemoryMetadata = Field(description="记忆元数据")


class MemorySearchResult(BaseModel):
    """记忆搜索结果"""
    id: str = Field(description="记忆ID")
    memory: str = Field(description="记忆内容")
    score: float = Field(description="相似度分数")
    metadata: Dict[str, Any] = Field(description="记忆元数据")


class UserProfile(BaseModel):
    """用户画像"""
    user_id: str = Field(description="用户ID")
    preferences: List[str] = Field(description="用户偏好", default_factory=list)
    personality_traits: List[str] = Field(description="性格特征", default_factory=list)
    habits: List[str] = Field(description="行为习惯", default_factory=list)
    important_events: List[str] = Field(description="重要事件", default_factory=list)
    memory_count: int = Field(description="记忆总数", default=0)
    last_updated: datetime = Field(description="最后更新时间", default_factory=datetime.now)