from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from ..core.database import get_db
from ..core.security import get_current_user
from ..models.update_version import UpdateVersion, UpdateStatistic
from ..models.user import User
import hashlib
import os
import zipfile
import tempfile
from pathlib import Path

router = APIRouter(prefix="/updates", tags=["updates"])

# ==================== Pydantic Models ====================

class UpdateCheckRequest(BaseModel):
    product: str = Field(..., validation_alias="Product", description="Tên sản phẩm: SimpleBIM")
    currentVersion: str = Field(..., validation_alias="CurrentVersion", description="Version hiện tại của add-in")
    revitVersion: str = Field(..., validation_alias="RevitVersion", description="Phiên bản Revit đang chạy")
    machineHash: str = Field(..., validation_alias="MachineHash", description="Hash máy để logging")
    os: str = Field(..., validation_alias="OS", description="Chuỗi OS")
    
    class Config:
        populate_by_name = True

class UpdateCheckResponse(BaseModel):
    updateAvailable: bool = Field(..., serialization_alias="UpdateAvailable")
    latestVersion: str = Field(..., serialization_alias="LatestVersion")
    minimumRequiredVersion: str = Field(..., serialization_alias="MinimumRequiredVersion")
    releaseDate: str = Field(..., serialization_alias="ReleaseDate")
    releaseNotes: str = Field(..., serialization_alias="ReleaseNotes")
    downloadUrl: str = Field(..., serialization_alias="DownloadUrl")
    fileSize: int = Field(..., serialization_alias="FileSize")
    checksumSHA256: str = Field(..., serialization_alias="ChecksumSHA256")
    updateType: str = Field(..., serialization_alias="UpdateType")
    forceUpdate: bool = Field(..., serialization_alias="ForceUpdate")
    notificationMessage: str = Field(..., serialization_alias="NotificationMessage")
    
    class Config:
        populate_by_name = True

class VersionCreate(BaseModel):
    version: str
    release_notes: str
    download_url: str
    file_size: int
    checksum_sha256: str
    update_type: str = "optional"
    force_update: bool = False
    min_required_version: str = "1.0.0.0"

class VersionResponse(BaseModel):
    id: int
    version: str
    release_date: str
    release_notes: Optional[str]
    download_url: str
    file_size: int
    checksum_sha256: str
    update_type: str
    force_update: bool
    min_required_version: str
    is_active: bool
    created_at: str
    
    class Config:
        from_attributes = True

# ==================== Helper Functions ====================

def parse_version(version_str: str) -> tuple:
    """Parse semantic version string to tuple for comparison"""
    parts = version_str.strip().lstrip('vV').split('.')
    while len(parts) < 4:
        parts.append('0')
    return tuple(int(p) for p in parts[:4])

def create_release_zip(version: UpdateVersion, repo_path: str) -> str:
    """
    Tạo ZIP file chứa SimpleBIM.dll, SimpleBIM.pdb và install.exe từ repo
    Returns: đường dẫn tới file ZIP được tạo
    """
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, f"SimpleBIM_v{version.version}.zip")
    
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 1. Thêm SimpleBIM.dll từ Releases folder
            dll_path = os.path.join(repo_path, f"Releases/{version.version}/SimpleBIM.dll")
            if os.path.exists(dll_path):
                zipf.write(dll_path, arcname="SimpleBIM.dll")
            
            # 2. Thêm SimpleBIM.pdb từ Releases folder
            pdb_path = os.path.join(repo_path, f"Releases/{version.version}/SimpleBIM.pdb")
            if os.path.exists(pdb_path):
                zipf.write(pdb_path, arcname="SimpleBIM.pdb")
            
            # 3. Luôn thêm install.exe từ Installer folder
            exe_path = os.path.join(repo_path, "Installer/SimpleBIM.Installer.exe")
            if os.path.exists(exe_path):
                zipf.write(exe_path, arcname="SimpleBIM.Installer.exe")
            
            # 4. Thêm config file nếu có
            config_path = os.path.join(repo_path, "Installer/SimpleBIM.Installer.exe.config")
            if os.path.exists(config_path):
                zipf.write(config_path, arcname="SimpleBIM.Installer.exe.config")
        
        return zip_path
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tạo ZIP: {str(e)}")

# ==================== Public Endpoints (No Auth) ====================

@router.post("/check", response_model=UpdateCheckResponse)
async def check_for_updates(request: UpdateCheckRequest, db: Session = Depends(get_db)):
    """Kiểm tra xem có update mới không - endpoint public cho SimpleBIM client"""
    
    try:
        # Get latest active version
        latest = db.query(UpdateVersion).filter(
            UpdateVersion.is_active == True
        ).order_by(desc(UpdateVersion.release_date)).first()
        
        if not latest:
            return UpdateCheckResponse(
                updateAvailable=False,
                latestVersion=request.currentVersion,
                minimumRequiredVersion=request.currentVersion,
                releaseDate=datetime.utcnow().isoformat(),
                releaseNotes="Chưa có bản phát hành nào",
                downloadUrl="",
                fileSize=0,
                checksumSHA256="",
                updateType="optional",
                forceUpdate=False,
                notificationMessage="Chưa có bản phát hành nào"
            )
        
        # Compare versions
        current_version = parse_version(request.currentVersion)
        latest_version = parse_version(latest.version)
        update_available = latest_version > current_version
        
        # Check minimum required version
        min_required = parse_version(latest.min_required_version)
        force_update = current_version < min_required
        
        # Determine update type
        update_type = latest.update_type
        if force_update:
            update_type = "mandatory"
        
        # Notification message
        if force_update:
            notification_msg = "⚠️ CẬP NHẬT BẮT BUỘC - Phiên bản của bạn đã quá cũ"
        elif update_available:
            notification_msg = "🎉 Phiên bản mới có sẵn! Cập nhật để có trải nghiệm tốt nhất"
        else:
            notification_msg = "✅ Bạn đang sử dụng phiên bản mới nhất"
        
        # Log activity
        stat = UpdateStatistic(
            machine_hash=request.machineHash,
            current_version=request.currentVersion,
            target_version=latest.version if update_available else None,
            revit_version=request.revitVersion,
            os_version=request.os,
            action="check",
            status="success"
        )
        db.add(stat)
        db.commit()
        
        return UpdateCheckResponse(
            updateAvailable=update_available,
            latestVersion=latest.version,
            minimumRequiredVersion=latest.min_required_version,
            releaseDate=latest.release_date.isoformat(),
            releaseNotes=latest.release_notes or "",
            downloadUrl=latest.download_url,
            fileSize=latest.file_size,
            checksumSHA256=latest.checksum_sha256,
            updateType=update_type,
            forceUpdate=force_update,
            notificationMessage=notification_msg
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update check failed: {str(e)}")


@router.post("/download-stats")
async def log_download_started(
    version: str,
    machine_hash: str,
    db: Session = Depends(get_db)
):
    """Log khi user bắt đầu download update"""
    stat = UpdateStatistic(
        machine_hash=machine_hash,
        target_version=version,
        action="download",
        status="started"
    )
    db.add(stat)
    db.commit()
    return {"status": "logged"}


@router.post("/install-stats")
async def log_install_result(
    version: str,
    machine_hash: str,
    success: bool,
    error_message: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Log kết quả install update"""
    stat = UpdateStatistic(
        machine_hash=machine_hash,
        target_version=version,
        action="install",
        status="success" if success else "failed",
        error_message=error_message
    )
    db.add(stat)
    db.commit()
    return {"status": "logged"}


@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint"""
    latest = db.query(UpdateVersion).filter(
        UpdateVersion.is_active == True
    ).order_by(desc(UpdateVersion.release_date)).first()
    
    return {
        "status": "healthy",
        "service": "SimpleBIM Update Service",
        "version": "1.0.0",
        "latest_version_known": latest.version if latest else None
    }


# ==================== Admin Endpoints (Require Auth) ====================

@router.get("/versions", response_model=List[VersionResponse])
async def get_all_versions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lấy danh sách tất cả versions - Admin only"""
    versions = db.query(UpdateVersion).order_by(desc(UpdateVersion.release_date)).all()
    return [
        VersionResponse(
            id=v.id,
            version=v.version,
            release_date=v.release_date.isoformat(),
            release_notes=v.release_notes,
            download_url=v.download_url,
            file_size=v.file_size,
            checksum_sha256=v.checksum_sha256,
            update_type=v.update_type,
            force_update=v.force_update,
            min_required_version=v.min_required_version,
            is_active=v.is_active,
            created_at=v.created_at.isoformat()
        )
        for v in versions
    ]


@router.post("/versions", response_model=VersionResponse)
async def create_version(
    data: VersionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Publish một version mới - Admin only"""
    
    # Check if version already exists
    existing = db.query(UpdateVersion).filter(UpdateVersion.version == data.version).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Version {data.version} already exists")
    
    new_version = UpdateVersion(
        version=data.version,
        release_date=datetime.utcnow(),
        release_notes=data.release_notes,
        download_url=data.download_url,
        file_size=data.file_size,
        checksum_sha256=data.checksum_sha256,
        update_type=data.update_type,
        force_update=data.force_update,
        min_required_version=data.min_required_version,
        is_active=True
    )
    
    db.add(new_version)
    db.commit()
    db.refresh(new_version)
    
    return VersionResponse(
        id=new_version.id,
        version=new_version.version,
        release_date=new_version.release_date.isoformat(),
        release_notes=new_version.release_notes,
        download_url=new_version.download_url,
        file_size=new_version.file_size,
        checksum_sha256=new_version.checksum_sha256,
        update_type=new_version.update_type,
        force_update=new_version.force_update,
        min_required_version=new_version.min_required_version,
        is_active=new_version.is_active,
        created_at=new_version.created_at.isoformat()
    )


@router.put("/versions/{version_id}/deactivate")
async def deactivate_version(
    version_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Deactivate một version - Admin only"""
    version = db.query(UpdateVersion).filter(UpdateVersion.id == version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    
    version.is_active = False
    db.commit()
    
    return {"status": "deactivated", "version": version.version}


@router.delete("/versions/{version_id}")
async def delete_version(
    version_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Xóa một version - Admin only"""
    version = db.query(UpdateVersion).filter(UpdateVersion.id == version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    
    db.delete(version)
    db.commit()
    
    return {"status": "deleted", "version": version.version}


@router.get("/statistics")
async def get_update_statistics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get analytics về updates - Admin only"""
    
    total_checks = db.query(UpdateStatistic).filter(UpdateStatistic.action == "check").count()
    total_downloads = db.query(UpdateStatistic).filter(UpdateStatistic.action == "download").count()
    total_installs = db.query(UpdateStatistic).filter(UpdateStatistic.action == "install").count()
    success_installs = db.query(UpdateStatistic).filter(
        UpdateStatistic.action == "install",
        UpdateStatistic.status == "success"
    ).count()
    
    success_rate = round(100 * success_installs / total_installs, 2) if total_installs > 0 else 0
    
    # Version distribution
    version_dist = db.query(
        UpdateStatistic.current_version,
        func.count(UpdateStatistic.id).label('count')
    ).filter(
        UpdateStatistic.action == "check",
        UpdateStatistic.current_version.isnot(None)
    ).group_by(UpdateStatistic.current_version).all()
    
    version_distribution = {v[0]: v[1] for v in version_dist}
    
    return {
        "total_checks": total_checks,
        "total_downloads": total_downloads,
        "total_installs": total_installs,
        "success_installs": success_installs,
        "success_rate": success_rate,
        "version_distribution": version_distribution
    }


@router.post("/calculate-checksum")
async def calculate_file_checksum(
    file_path: str,
    current_user: User = Depends(get_current_user)
):
    """Utility để calculate SHA256 checksum của file - Admin only"""
    try:
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
            
        sha256_hash = hashlib.sha256()
        
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        
        checksum = sha256_hash.hexdigest()
        file_size = os.path.getsize(file_path)
        
        return {
            "file_path": file_path,
            "checksum_sha256": checksum,
            "file_size_bytes": file_size,
            "file_size_mb": round(file_size / (1024 * 1024), 2)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error: {str(e)}")


# ==================== Public Download Endpoint ====================

@router.get("/versions/{version_id}/download")
async def download_version(
    version_id: int,
    db: Session = Depends(get_db)
):
    """
    Download phiên bản SimpleBIM dưới dạng ZIP
    Tự động tạo ZIP chứa SimpleBIM.dll, .pdb và install.exe
    """
    try:
        # Lấy thông tin version từ database
        version = db.query(UpdateVersion).filter(UpdateVersion.id == version_id).first()
        if not version:
            raise HTTPException(status_code=404, detail="Version not found")
        
        # Xác định đường dẫn repo
        # Giả sử backend folder là c:\Users\...\SimpleBIM - Copy\Web\backend
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        repo_path = os.path.dirname(backend_dir)  # c:\Users\...\SimpleBIM - Copy\Web
        repo_root = os.path.dirname(repo_path)   # c:\Users\...\SimpleBIM - Copy
        
        # Tạo ZIP file
        zip_path = create_release_zip(version, repo_root)
        
        # Log download statistic
        stat = UpdateStatistic(
            machine_hash="browser_download",
            target_version=version.version,
            action="download",
            status="web_started"
        )
        db.add(stat)
        db.commit()
        
        # Trả về file để download
        return FileResponse(
            path=zip_path,
            filename=f"SimpleBIM_v{version.version}.zip",
            media_type="application/zip"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tải xuống: {str(e)}")


@router.post("/versions/{version_id}/download-tracked")
async def track_download(
    version_id: int,
    machine_hash: str = None,
    db: Session = Depends(get_db)
):
    """Track download action từ Downloads.js page"""
    try:
        version = db.query(UpdateVersion).filter(UpdateVersion.id == version_id).first()
        if not version:
            raise HTTPException(status_code=404, detail="Version not found")
        
        stat = UpdateStatistic(
            machine_hash=machine_hash or "unknown",
            target_version=version.version,
            action="download",
            status="web_tracked"
        )
        db.add(stat)
        db.commit()
        
        return {
            "status": "success",
            "version": version.version,
            "download_url": f"/updates/versions/{version_id}/download"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error: {str(e)}")
