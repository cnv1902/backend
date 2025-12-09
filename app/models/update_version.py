from sqlalchemy import Integer, String, DateTime, Boolean, BigInteger, Text
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from ..core.database import Base

class UpdateVersion(Base):
    """Model lưu trữ thông tin các phiên bản SimpleBIM"""
    __tablename__ = "update_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    release_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    release_notes: Mapped[str] = mapped_column(Text, nullable=True)
    download_url: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    update_type: Mapped[str] = mapped_column(String(20), default="optional")  # optional, recommended, mandatory
    force_update: Mapped[bool] = mapped_column(Boolean, default=False)
    min_required_version: Mapped[str] = mapped_column(String(20), default="1.0.0.0")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UpdateStatistic(Base):
    """Model lưu trữ thống kê về việc check/download/install update"""
    __tablename__ = "update_statistics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    machine_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    current_version: Mapped[str] = mapped_column(String(20), nullable=True)
    target_version: Mapped[str] = mapped_column(String(20), nullable=True)
    revit_version: Mapped[str] = mapped_column(String(10), nullable=True)
    os_version: Mapped[str] = mapped_column(String(100), nullable=True)
    action: Mapped[str] = mapped_column(String(20), nullable=False)  # check, download, install, skip
    status: Mapped[str] = mapped_column(String(20), nullable=True)  # success, failed, cancelled
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
