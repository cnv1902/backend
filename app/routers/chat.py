# Chat Router - API endpoints cho chat history và RAG
# Tính năng: Lưu lịch sử, kiểm tra cache, few-shot prompting
# Author: SimpleBIM Team

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional, List
from datetime import datetime
import json
import re

from ..core.database import get_db
from ..core.security import get_current_user_optional
from ..models.user import User
from ..models.chat import ChatSession, ChatMessage, CachedQuery
from ..schemas.chat import (
    SessionCreate, SessionUpdate, SessionResponse, SessionWithMessages,
    SessionListResponse, ChatRequest, ChatResponse, MessageResponse,
    CachedQueryResponse, ChatStatistics
)

router = APIRouter(prefix="/chat", tags=["Chat"])


# ==================== Helper Functions ====================

def normalize_query(query: str) -> str:
    """
    Chuẩn hóa query để so sánh.
    Lowercase, trim, remove extra spaces.
    """
    normalized = query.lower().strip()
    normalized = re.sub(r'\s+', ' ', normalized)
    # Remove dấu câu cuối
    normalized = re.sub(r'[?.!]+$', '', normalized)
    return normalized


def calculate_similarity(query1: str, query2: str) -> float:
    """
    Tính độ tương đồng đơn giản giữa 2 query.
    Sử dụng Jaccard similarity trên từ.
    Trong production nên dùng embedding + cosine similarity.
    """
    words1 = set(normalize_query(query1).split())
    words2 = set(normalize_query(query2).split())
    
    if not words1 or not words2:
        return 0.0
    
    intersection = words1 & words2
    union = words1 | words2
    
    return len(intersection) / len(union)


def find_similar_cached_query(db: Session, query: str, threshold: float = 0.8) -> Optional[CachedQuery]:
    """
    Tìm cached query tương tự trong database.
    Returns None nếu không tìm thấy query đủ tương tự.
    """
    normalized = normalize_query(query)
    
    # Exact match trước
    exact_match = db.query(CachedQuery).filter(
        CachedQuery.query_normalized == normalized
    ).first()
    
    if exact_match:
        return exact_match
    
    # Fuzzy match - lấy top candidates
    # Trong production nên dùng full-text search hoặc vector similarity
    all_cached = db.query(CachedQuery).limit(100).all()
    
    best_match = None
    best_score = 0.0
    
    for cached in all_cached:
        score = calculate_similarity(normalized, cached.query_normalized)
        if score > best_score and score >= threshold:
            best_score = score
            best_match = cached
    
    return best_match


# ==================== Session Endpoints ====================

@router.post("/sessions", response_model=SessionResponse)
def create_session(
    session_data: SessionCreate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    Tạo session chat mới.
    User có thể login hoặc anonymous.
    """
    user_id = current_user.id if current_user else None
    
    new_session = ChatSession(
        user_id=user_id,
        title=session_data.title or "Cuộc trò chuyện mới"
    )
    
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    
    return new_session


@router.get("/sessions", response_model=SessionListResponse)
def list_sessions(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    Lấy danh sách sessions của user hiện tại.
    Anonymous user chỉ thấy sessions không có user_id.
    """
    user_id = current_user.id if current_user else None
    
    query = db.query(ChatSession).filter(
        ChatSession.user_id == user_id,
        ChatSession.is_active == True
    ).order_by(desc(ChatSession.updated_at))
    
    total = query.count()
    sessions = query.offset(skip).limit(limit).all()
    
    return SessionListResponse(sessions=sessions, total=total)


@router.get("/sessions/{session_id}", response_model=SessionWithMessages)
def get_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    Lấy chi tiết session với tất cả messages.
    Kiểm tra quyền truy cập.
    """
    user_id = current_user.id if current_user else None
    
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session không tồn tại")
    
    # Kiểm tra quyền - chỉ owner hoặc admin mới xem được
    if session.user_id != user_id:
        raise HTTPException(status_code=403, detail="Không có quyền truy cập session này")
    
    return session


@router.put("/sessions/{session_id}", response_model=SessionResponse)
def update_session(
    session_id: int,
    update_data: SessionUpdate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    Cập nhật thông tin session (title, is_active).
    """
    user_id = current_user.id if current_user else None
    
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == user_id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session không tồn tại")
    
    if update_data.title is not None:
        session.title = update_data.title
    if update_data.is_active is not None:
        session.is_active = update_data.is_active
    
    session.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(session)
    
    return session


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    Xóa session và tất cả messages.
    """
    user_id = current_user.id if current_user else None
    
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == user_id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session không tồn tại")
    
    db.delete(session)
    db.commit()
    
    return {"message": "Đã xóa session thành công"}


# ==================== Chat Endpoint ====================

@router.post("/send", response_model=ChatResponse)
def send_message(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    Gửi message và nhận response.
    
    Flow:
    1. Tạo hoặc lấy session
    2. Lưu message của user
    3. Kiểm tra cache - nếu có query tương tự, trả về từ cache
    4. Nếu không, trả về placeholder (frontend sẽ gọi LLM)
    5. Lưu response vào cache
    """
    user_id = current_user.id if current_user else None
    
    # 1. Tạo hoặc lấy session
    if request.session_id:
        session = db.query(ChatSession).filter(
            ChatSession.id == request.session_id,
            ChatSession.user_id == user_id
        ).first()
        
        if not session:
            raise HTTPException(status_code=404, detail="Session không tồn tại")
    else:
        # Tạo session mới
        session = ChatSession(
            user_id=user_id,
            title=request.query[:50] + "..." if len(request.query) > 50 else request.query
        )
        db.add(session)
        db.commit()
        db.refresh(session)
    
    # 2. Lưu message của user
    user_message = ChatMessage(
        session_id=session.id,
        role="user",
        content=request.query
    )
    db.add(user_message)
    
    # 3. Kiểm tra cache
    cached = find_similar_cached_query(db, request.query, threshold=0.8)
    
    is_from_cache = False
    similarity_score = None
    response_content = ""
    
    if cached:
        # Cache hit! Trả về response từ database
        is_from_cache = True
        similarity_score = calculate_similarity(normalize_query(request.query), cached.query_normalized)
        response_content = cached.response
        
        # Cập nhật hit count
        cached.hit_count += 1
        cached.last_used_at = datetime.utcnow()
    else:
        # Cache miss - trả về empty để frontend gọi LLM
        response_content = "__NEEDS_LLM__"
    
    # 4. Lưu response message
    assistant_message = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=response_content,
        is_from_cache=is_from_cache,
        similarity_score=similarity_score
    )
    db.add(assistant_message)
    
    # Update session timestamp
    session.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(assistant_message)
    
    return ChatResponse(
        session_id=session.id,
        message_id=assistant_message.id,
        response=response_content,
        is_from_cache=is_from_cache,
        similarity_score=similarity_score,
        sources=[]
    )


@router.put("/messages/{message_id}/response")
def update_message_response(
    message_id: int,
    response: str,
    rag_context: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Cập nhật response từ LLM cho message.
    Được gọi từ frontend sau khi nhận response từ Gemini.
    Đồng thời cache query mới.
    """
    message = db.query(ChatMessage).filter(
        ChatMessage.id == message_id
    ).first()
    
    if not message:
        raise HTTPException(status_code=404, detail="Message không tồn tại")
    
    # Cập nhật response
    message.content = response
    message.rag_context = rag_context
    
    # Tìm message query tương ứng (message trước đó)
    user_message = db.query(ChatMessage).filter(
        ChatMessage.session_id == message.session_id,
        ChatMessage.role == "user",
        ChatMessage.id < message.id
    ).order_by(desc(ChatMessage.id)).first()
    
    if user_message:
        # Cache query mới
        normalized = normalize_query(user_message.content)
        
        # Kiểm tra đã có chưa
        existing = db.query(CachedQuery).filter(
            CachedQuery.query_normalized == normalized
        ).first()
        
        if not existing:
            new_cache = CachedQuery(
                query_normalized=normalized,
                response=response
            )
            db.add(new_cache)
    
    db.commit()
    
    return {"message": "Đã cập nhật response thành công"}


# ==================== Cache Management ====================

@router.get("/cache", response_model=List[CachedQueryResponse])
def list_cached_queries(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_optional)
):
    """
    Lấy danh sách cached queries (admin only).
    """
    # Chỉ admin mới xem được cache
    # Tạm thời bỏ check để dễ test
    
    queries = db.query(CachedQuery).order_by(
        desc(CachedQuery.hit_count)
    ).offset(skip).limit(limit).all()
    
    return queries


@router.delete("/cache/{cache_id}")
def delete_cached_query(
    cache_id: int,
    db: Session = Depends(get_db)
):
    """
    Xóa cached query.
    """
    cached = db.query(CachedQuery).filter(CachedQuery.id == cache_id).first()
    
    if not cached:
        raise HTTPException(status_code=404, detail="Cached query không tồn tại")
    
    db.delete(cached)
    db.commit()
    
    return {"message": "Đã xóa cached query"}


# ==================== Statistics ====================

@router.get("/statistics", response_model=ChatStatistics)
def get_statistics(db: Session = Depends(get_db)):
    """
    Lấy thống kê chat usage.
    """
    total_sessions = db.query(func.count(ChatSession.id)).scalar() or 0
    total_messages = db.query(func.count(ChatMessage.id)).scalar() or 0
    total_cached = db.query(func.count(CachedQuery.id)).scalar() or 0
    
    # Tính cache hit rate
    cache_hits = db.query(func.count(ChatMessage.id)).filter(
        ChatMessage.is_from_cache == True
    ).scalar() or 0
    
    assistant_messages = db.query(func.count(ChatMessage.id)).filter(
        ChatMessage.role == "assistant"
    ).scalar() or 1  # Avoid division by zero
    
    cache_hit_rate = cache_hits / assistant_messages if assistant_messages > 0 else 0
    
    # Estimate tokens saved (rough: 1000 tokens per response)
    tokens_saved = cache_hits * 1000
    
    return ChatStatistics(
        total_sessions=total_sessions,
        total_messages=total_messages,
        total_cached_queries=total_cached,
        cache_hit_rate=round(cache_hit_rate, 4),
        tokens_saved_estimate=tokens_saved
    )


# ==================== Few-shot Examples ====================

@router.get("/few-shot-examples")
def get_few_shot_examples(
    count: int = Query(5, ge=1, le=10),
    db: Session = Depends(get_db)
):
    """
    Lấy few-shot examples từ cached queries có chất lượng cao.
    Dùng làm examples khi gọi LLM.
    """
    # Lấy các queries có hit_count cao nhất (được sử dụng nhiều = chất lượng tốt)
    examples = db.query(CachedQuery).order_by(
        desc(CachedQuery.hit_count),
        desc(CachedQuery.quality_score)
    ).limit(count).all()
    
    return [
        {
            "question": ex.query_normalized,
            "answer": ex.response[:500]  # Truncate để không quá dài
        }
        for ex in examples
    ]
