# Chat schemas - Pydantic models cho API validation
# Author: SimpleBIM Team
# Last updated: 2025-12-26

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ==================== Message Schemas ====================

class MessageBase(BaseModel):
    """Base schema cho message"""
    role: str = Field(..., description="Vai trò: 'user' hoặc 'assistant'")
    content: str = Field(..., description="Nội dung tin nhắn")


class MessageCreate(MessageBase):
    """Schema khi tạo message mới"""
    pass


class MessageResponse(MessageBase):
    """Schema trả về message"""
    id: int
    session_id: int
    created_at: datetime
    is_from_cache: bool = False
    similarity_score: Optional[float] = None

    class Config:
        from_attributes = True


# ==================== Session Schemas ====================

class SessionBase(BaseModel):
    """Base schema cho session"""
    title: Optional[str] = "Cuộc trò chuyện mới"


class SessionCreate(SessionBase):
    """Schema khi tạo session mới"""
    pass


class SessionUpdate(BaseModel):
    """Schema khi update session"""
    title: Optional[str] = None
    is_active: Optional[bool] = None


class SessionResponse(SessionBase):
    """Schema trả về session (không có messages)"""
    id: int
    user_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


class SessionWithMessages(SessionResponse):
    """Schema trả về session với tất cả messages"""
    messages: List[MessageResponse] = []


class SessionListResponse(BaseModel):
    """Schema trả về danh sách sessions"""
    sessions: List[SessionResponse]
    total: int


# ==================== Chat Request/Response ====================

class ChatRequest(BaseModel):
    """Schema cho request chat mới"""
    session_id: Optional[int] = Field(None, description="ID session, null để tạo mới")
    query: str = Field(..., min_length=1, description="Câu hỏi của user")


class ChatResponse(BaseModel):
    """Schema trả về sau khi chat"""
    session_id: int
    message_id: int
    response: str
    is_from_cache: bool = Field(False, description="True nếu lấy từ database cache")
    similarity_score: Optional[float] = Field(None, description="Điểm tương đồng với cached query")
    sources: List[str] = Field(default_factory=list, description="Nguồn tài liệu RAG")


# ==================== Query Cache Schemas ====================

class CachedQueryResponse(BaseModel):
    """Schema cho cached query"""
    id: int
    query_normalized: str
    response: str
    hit_count: int
    created_at: datetime
    last_used_at: datetime
    quality_score: Optional[float] = None

    class Config:
        from_attributes = True


# ==================== Statistics ====================

class ChatStatistics(BaseModel):
    """Thống kê chat usage"""
    total_sessions: int
    total_messages: int
    total_cached_queries: int
    cache_hit_rate: float
    tokens_saved_estimate: int
