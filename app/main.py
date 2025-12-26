from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from .core.database import engine, Base, SessionLocal
from .core.config import settings
from .core.security import get_password_hash
from .models.user import User
from .models.otp import OTPRecord
from .models.update_version import UpdateVersion, UpdateStatistic
from .models.chat import ChatSession, ChatMessage, CachedQuery  # NEW: Chat models
from .routers.auth import router as auth_router
from .routers.keys import router as keys_router
from .routers.updates import router as updates_router
from .routers.chat import router as chat_router  # NEW: Chat router

app = FastAPI(title=settings.APP_NAME)

# Configure CORS
raw_origins = settings.CORS_ORIGINS or "*"
origins = [o.strip() for o in raw_origins.split(",") if o.strip()] if isinstance(raw_origins, str) else raw_origins
allow_credentials = False if "*" in origins else True
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create tables
Base.metadata.create_all(bind=engine)

# Seed default admin user if not exists
with SessionLocal() as db:
    if not db.query(User).filter(User.username == "admin").first():
        admin = User(
            username="admin",
            password_hash=get_password_hash("@Abc12324"),
            email="admin@example.com",
        )
        db.add(admin)
        db.commit()

# Routers
app.include_router(auth_router)
app.include_router(keys_router)
app.include_router(updates_router)
app.include_router(chat_router)  # NEW: Chat API endpoints

@app.get("/")
def root():
    return {"status": "ok"}

@app.get("/health")
def health_get():
    return {"status": "ok"}

@app.head("/health")
def health_head():
    return Response(status_code=200)
