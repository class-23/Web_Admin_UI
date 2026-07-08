"""
设备管理路由
处理设备注册、心跳、设备列表、设备配置
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db, get_settings_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.device import Device
from app.schemas.device import DeviceConfigUpdate
from app.utils.quantclaw_receiver.exceptions import QuantClawError

router = APIRouter(prefix="/api", tags=["设备"])


def get_device_manager(request: Request):
    return request.app.state.device_manager


# ------------------------------------------------------------------
# 设备端调用（无需认证）
# ------------------------------------------------------------------

@router.api_route("/device/register", methods=["POST", "GET"])
async def register_device(request: Request):
    """设备注册"""
    mgr = get_device_manager(request)
    try:
        result = await mgr.register_device(request)
        return JSONResponse(content=result, status_code=200)
    except QuantClawError as e:
        return JSONResponse(content=e.to_dict(), status_code=200)


@router.api_route("/device/heartbeat", methods=["POST", "GET"])
async def heartbeat_device(request: Request):
    """设备心跳"""
    mgr = get_device_manager(request)
    try:
        result = await mgr.process_heartbeat(request)
        return JSONResponse(content=result, status_code=200)
    except QuantClawError as e:
        return JSONResponse(content=e.to_dict(), status_code=200)


@router.post("/devices")
async def create_device(request: Request):
    """创建设备（register 别名）"""
    mgr = get_device_manager(request)
    return await mgr.create_device(request)


@router.get("/device/{device_id}/status")
async def registration_status(device_id: str, request: Request):
    """设备注册状态"""
    mgr = get_device_manager(request)
    return mgr.db_manager.get_registration_status(device_id)


@router.get("/device/{device_id}/heartbeat")
async def heartbeat_status(device_id: str, request: Request):
    """设备心跳状态"""
    mgr = get_device_manager(request)
    return mgr.db_manager.get_heartbeat_status(device_id)


# ------------------------------------------------------------------
# 管理端调用（需认证）
# ------------------------------------------------------------------

@router.get("/devices")
def list_devices(request: Request):
    """获取所有设备列表（公开访问）"""
    mgr = get_device_manager(request)
    result = mgr.db_manager.get_devices_list()
    return {"code": 0, "message": "ok", "data": result}


@router.get("/device/{device_id}/config")
def get_device_config(
    device_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings_db: Session = Depends(get_settings_db),
):
    """获取设备配置"""
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    if device.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作此设备")

    mgr = get_device_manager(request)
    config = mgr.db_manager.get_device_config(device_id)
    return {"code": 0, "message": "ok", "data": config}


@router.put("/device/{device_id}/config")
def update_device_config(
    device_id: int,
    config_data: DeviceConfigUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings_db: Session = Depends(get_settings_db),
):
    """更新设备配置"""
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    if device.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作此设备")

    mgr = get_device_manager(request)
    result = mgr.db_manager.update_device_config(
        device_id, config_data.model_dump(exclude_unset=True)
    )
    return {"code": 0, "message": "ok", "data": result}


@router.get("/receiver/health")
def health_check(request: Request):
    """健康检查"""
    mgr = get_device_manager(request)
    return mgr.db_manager.health_check()
