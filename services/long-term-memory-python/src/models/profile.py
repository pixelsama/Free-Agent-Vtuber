"""
用户画像数据模型

定义用户画像的数据结构和构建逻辑
"""
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    """用户画像模型"""
    user_id: str = Field(description="用户ID")
    preferences: List[str] = Field(default_factory=list, description="用户偏好列表")
    personality_traits: List[str] = Field(default_factory=list, description="性格特征列表")
    context_info: List[str] = Field(default_factory=list, description="上下文信息列表")
    updated_at: str = Field(description="更新时间")
    version: str = Field(default="1.0", description="画像版本")
    
    class Config:
        extra = "allow"


class ProfileBuilder:
    """用户画像构建器"""
    
    def __init__(self):
        # 分类关键词映射
        self.preference_keywords = [
            "喜欢", "爱好", "偏好", "感兴趣", "热爱", "迷恋", "钟爱"
        ]
        self.personality_keywords = [
            "性格", "个性", "特点", "脾气", "内向", "外向", "开朗", "安静"
        ]
        self.context_keywords = [
            "工作", "职业", "学习", "学生", "大学", "公司", "专业", "技能"
        ]

    async def build_profile(self, user_id: str, memories: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        基于记忆数据构建用户画像
        
        Args:
            user_id: 用户ID
            memories: 用户记忆列表
            
        Returns:
            构建的用户画像
        """
        profile = UserProfile(
            user_id=user_id,
            updated_at=datetime.now().isoformat()
        )
        
        # 分析记忆内容并分类
        for memory in memories:
            content = memory.get("memory", "") or memory.get("content", "")
            category = memory.get("metadata", {}).get("category", "")
            
            # 根据内容和分类提取信息
            self._extract_preferences(content, profile.preferences)
            self._extract_personality_traits(content, profile.personality_traits)
            self._extract_context_info(content, profile.context_info)
        
        # 去重并限制长度
        profile.preferences = list(set(profile.preferences))[:10]
        profile.personality_traits = list(set(profile.personality_traits))[:10]
        profile.context_info = list(set(profile.context_info))[:10]
        
        return profile.dict()

    def _extract_preferences(self, content: str, preferences: List[str]):
        """从内容中提取用户偏好"""
        for keyword in self.preference_keywords:
            if keyword in content:
                # 简单的关键词提取逻辑
                if "动漫" in content:
                    preferences.append("动漫")
                if "编程" in content or "代码" in content or "开发" in content:
                    preferences.append("编程")
                if "音乐" in content:
                    preferences.append("音乐")
                if "游戏" in content:
                    preferences.append("游戏")
                if "电影" in content:
                    preferences.append("电影")

    def _extract_personality_traits(self, content: str, traits: List[str]):
        """从内容中提取性格特征"""
        trait_mapping = {
            "内向": ["内向", "安静", "不爱说话", "害羞"],
            "外向": ["外向", "开朗", "活泼", "健谈"],
            "好学": ["好学", "爱学习", "求知欲", "钻研"],
            "细心": ["细心", "仔细", "认真", "严谨"],
            "乐观": ["乐观", "积极", "正面", "开心"]
        }
        
        for trait, keywords in trait_mapping.items():
            for keyword in keywords:
                if keyword in content:
                    traits.append(trait)
                    break

    def _extract_context_info(self, content: str, context_info: List[str]):
        """从内容中提取上下文信息"""
        context_mapping = {
            "软件工程师": ["软件工程师", "程序员", "开发者", "工程师"],
            "学生": ["学生", "大学生", "研究生", "本科生"],
            "设计师": ["设计师", "UI设计", "平面设计"],
            "教师": ["教师", "老师", "讲师", "教授"],
            "创业者": ["创业", "创始人", "CEO", "老板"]
        }
        
        for context, keywords in context_mapping.items():
            for keyword in keywords:
                if keyword in content:
                    context_info.append(context)
                    break