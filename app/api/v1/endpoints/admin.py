"""
Admin endpoints
Handles administrative tasks and management
"""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import DatabaseHealthCheck, get_db
from app.core.security import require_admin, require_super_admin
from app.models import User
from app.services.admin import AdminService

router = APIRouter()


@router.get("/dashboard")
async def get_admin_dashboard(
    current_user: User = Depends(require_admin), db: Session = Depends(get_db)
):
    """Get admin dashboard statistics"""
    return AdminService.get_dashboard_stats(db)


@router.get("/users", response_model=List[Dict[str, Any]])
async def get_all_users(
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get all users with filters (admin only)"""
    return AdminService.get_users(db, role, is_active, skip, limit)


@router.put("/users/{user_id}/status")
async def update_user_status(
    user_id: int,
    is_active: bool,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Activate/deactivate user account"""
    return AdminService.update_user_status(db, user_id, is_active)


@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: int,
    role: str,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Update user role (super admin only)"""
    return AdminService.update_user_role(db, user_id, role)


@router.get("/system/health")
async def get_system_health(current_user: User = Depends(require_admin)):
    """Get system health information"""
    return {
        "database": DatabaseHealthCheck.check_connection(),
        "tables": DatabaseHealthCheck.get_table_stats(),
    }


@router.post("/maintenance/vacuum")
async def run_vacuum(
    table_name: Optional[str] = None,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Run VACUUM ANALYZE on database"""
    from app.core.database import DatabaseUtils

    DatabaseUtils.vacuum_analyze(table_name)
    return {"message": f"VACUUM ANALYZE completed for {table_name or 'entire database'}"}
