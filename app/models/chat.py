# Chat history models - Lưu trữ lịch sử hội thoại AI
# Mục đích: Tái sử dụng responses để tiết kiệm token LLM

from sqlalchemy import Integer, String, DateTime, Text, Boolean, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from ..core.database import Base


class ChatSession(Base):
    """
    Bảng lưu trữ các phiên chat.
    Mỗi user có thể có nhiều sessions.
    """
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Liên kết với user (nullable cho anonymous)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Tên session để user dễ nhận biết
    title: Mapped[str] = mapped_column(String(255), default="Cuộc trò chuyện mới")
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Trạng thái session
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Relationship với messages
    messages: Mapped[list["ChatMessage"]] = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    """
    Bảng lưu từng message trong session.
    Bao gồm cả query (user) và response (assistant).
    """
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Liên kết với session
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("chat_sessions.id"), nullable=False)
    
    # Vai trò: 'user' hoặc 'assistant'
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    
    # Nội dung message
    content: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Flag đánh dấu response từ database cache
    is_from_cache: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Điểm similarity nếu lấy từ cache (để debug)
    similarity_score: Mapped[float] = mapped_column(Float, nullable=True)
    
    # Context đã dùng cho RAG (optional, để debug)
    rag_context: Mapped[str] = mapped_column(Text, nullable=True)
    
    # Relationship ngược với session
    session: Mapped["ChatSession"] = relationship("ChatSession", back_populates="messages")


class CachedQuery(Base):
    """
    Bảng cache các query đã xử lý.
    Dùng để tìm kiếm nhanh query tương tự.
    """
    __tablename__ = "cached_queries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Query gốc (normalized, lowercase, trimmed)
    query_normalized: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Response đã lưu
    response: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Vector embedding của query (JSON string cho đơn giản)
    # Trong production nên dùng pgvector hoặc separate vector DB
    embedding: Mapped[str] = mapped_column(Text, nullable=True)
    
    # Số lần query này được sử dụng lại
    hit_count: Mapped[int] = mapped_column(Integer, default=1)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_used_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Chất lượng response (user feedback, 1-5)
    quality_score: Mapped[float] = mapped_column(Float, nullable=True)
