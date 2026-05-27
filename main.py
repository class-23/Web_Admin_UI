"""
QuantClaw 设备管理后台
"""
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Request, Response, Depends
from fastapi.staticfiles import StaticFiles
from quantclaw_receiver import QuantClawDeviceManager, QuantClawConfig
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager
import subprocess
import socket
import uvicorn
import time
import os
import datetime
import platform
import paramiko
import shlex
import psycopg2
import psycopg2.extras
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from login.limiter import limiter
from login.routers.auth_router import router as auth_router
from login.auth import require_auth
from login.database import get_db, init_db as login_init_db

config = QuantClawConfig(
    pg_host=os.getenv("PG_HOST", "localhost"),
    pg_port=int(os.getenv("PG_PORT", "5432")),
    pg_user=os.getenv("PG_USER", "quant"),
    pg_password=os.getenv("PG_PASSWORD", "open123456"),
    pg_dbname=os.getenv("PG_DBNAME", os.getenv("PG_NAME", "quantclaw")),
    udp_enabled=os.getenv("UDP_ENABLED", "true").lower() == "true",
    allow_insecure=os.getenv("ALLOW_INSECURE", "true").lower() == "true",
    heartbeat_interval_sec=int(os.getenv("HEARTBEAT_INTERVAL_SEC", "60"))
)

device_manager = QuantClawDeviceManager(config)

@asynccontextmanager
async def lifespan(app: FastAPI):
    login_init_db()
    await device_manager.startup()
    yield
    await device_manager.shutdown()

app = FastAPI(
    title=os.getenv("APP_TITLE", "QuantClaw Device Manager"),
    lifespan=lifespan
)


class UserDefaultSettings(BaseModel):
    base_path: str = "."
    language: str = "zh-CN"
    is_admin: bool = False
    can_create: bool = True
    can_delete: bool = True
    can_download: bool = True
    can_edit: bool = True
    can_rename: bool = True
    can_share: bool = True


class GlobalSettings(BaseModel):
    allow_registration: bool = False
    auto_create_home: bool = False
    hide_login_button: bool = True
    user_home_path: str = "/users"
    min_password_length: int = 12
    forbidden_external_links: bool = False
    disable_disk_space_display: bool = False
    theme: str = "系统默认"
    instance_name: str = ""
    branding_folder: str = ""
    chunk_size: str = "10MB"
    chunk_retries: int = 5
    config_version: int = 0
    config_updated_at: str = ""
    user_defaults: UserDefaultSettings = UserDefaultSettings()


class FileRenameRequest(BaseModel):
    path: str
    new_name: str


class FileDeleteRequest(BaseModel):
    path: str
    type: str


class FileCopyRequest(BaseModel):
    source: str
    destination: str


class FileMoveRequest(BaseModel):
    source: str
    destination: str


class FileCreateRequest(BaseModel):
    path: str
    name: str


class FileSaveRequest(BaseModel):
    path: str
    content: str


class FileReadRequest(BaseModel):
    path: str


class SshConfigData(BaseModel):
    host: str = ""
    port: int = 22
    username: str = ""
    password: str = ""
    remote_path: str = os.getenv("SSH_DEFAULT_REMOTE_PATH", "/home/quant")


def get_user_ssh_config(db, user_id):
    cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM ssh_configs WHERE user_id = %s", (user_id,))
    cfg = cur.fetchone()
    cur.close()
    return cfg


def require_ssh_mode(db, user_id):
    cfg = get_user_ssh_config(db, user_id)
    if not cfg or not cfg["host"] or not cfg["username"]:
        raise HTTPException(
            status_code=403,
            detail="SSH 远程服务器未配置。请在 Web 界面左侧菜单底部点击「配置」按钮，设置 SSH 连接参数后再进行操作。"
        )
    return cfg


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api")


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "message": exc.detail, "data": None},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    message = errors[0]["msg"] if errors else "请求参数验证失败"
    return JSONResponse(
        status_code=422,
        content={"code": 422, "message": message, "data": None},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"code": 500, "message": f"服务器内部错误: {str(exc)}", "data": None},
    )


@app.get("/api/settings")
async def get_settings(user = Depends(require_auth), db = Depends(get_db)):
    cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT data FROM settings WHERE user_id = %s", (user["id"],))
    row = cur.fetchone()
    cur.close()
    if row and row["data"]:
        return GlobalSettings(**row["data"])
    return GlobalSettings()


@app.post("/api/settings")
async def update_settings(settings: GlobalSettings, user = Depends(require_auth), db = Depends(get_db)):
    cur = db.cursor()
    cur.execute(
        "INSERT INTO settings (user_id, data) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE SET data = %s, updated_at = NOW()",
        (user["id"], psycopg2.extras.Json(settings.dict()), psycopg2.extras.Json(settings.dict()))
    )
    db.commit()
    cur.close()
    return {"success": True, "settings": settings}


_cors_origins = os.getenv("CORS_ALLOW_ORIGINS", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[_cors_origins] if _cors_origins != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/login", response_class=HTMLResponse)
async def login():
    with open("templates/login.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/register", response_class=HTMLResponse)
async def register():
    with open("templates/register.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password():
    with open("templates/forgot-password.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/reset-password", response_class=HTMLResponse)
async def reset_password():
    with open("templates/reset-password.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/change-password", response_class=HTMLResponse)
async def change_password_page():
    with open("templates/change-password.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/setting", response_class=HTMLResponse)
async def setting():
    with open("templates/setting.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/file_manager", response_class=HTMLResponse)
async def file_manager():
    with open("templates/file_manager.html", "r", encoding="utf-8") as f:
        return f.read()


def get_disk_usage():
    try:
        if platform.system() == "Windows":
            result = subprocess.run(
                ["wmic", "logicaldisk", "get", "Size,FreeSpace,Caption", "/format:csv"],
                capture_output=True, text=True, timeout=5
            )
            disks = []
            lines = result.stdout.strip().split('\n')
            for line in lines[1:]:
                if line.strip():
                    parts = line.split(',')
                    if len(parts) >= 4:
                        caption = parts[1]
                        try:
                            free_space = int(parts[2]) if parts[2] else 0
                            size = int(parts[3]) if parts[3] else 0
                            if size > 0:
                                used = size - free_space
                                percent = (used / size) * 100 if size > 0 else 0
                                disks.append({
                                    "caption": caption,
                                    "total": size,
                                    "used": used,
                                    "free": free_space,
                                    "percent": round(percent, 1)
                                })
                        except (ValueError, IndexError):
                            continue
            return disks
        else:
            result = subprocess.run(
                ["df", "-B1", "."],
                capture_output=True, text=True, timeout=5
            )
            disks = []
            lines = result.stdout.strip().split('\n')
            for line in lines[1:]:
                parts = line.split()
                if len(parts) >= 6:
                    try:
                        total = int(parts[1])
                        used = int(parts[2])
                        free = int(parts[3])
                        percent = int(parts[4].replace('%', ''))
                        disks.append({
                            "caption": parts[5] if len(parts) > 5 else parts[0],
                            "total": total,
                            "used": used,
                            "free": free,
                            "percent": percent
                        })
                    except (ValueError, IndexError):
                        continue
            return disks
    except Exception as e:
        print(f"Error getting disk usage: {e}")
        return []


def format_bytes(bytes_value):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} PB"


@app.get("/api/disk_usage")
async def get_disk_usage_api():
    disks = get_disk_usage()
    formatted_disks = []
    for disk in disks:
        formatted_disks.append({
            "caption": disk["caption"],
            "total": disk["total"],
            "total_formatted": format_bytes(disk["total"]),
            "used": disk["used"],
            "used_formatted": format_bytes(disk["used"]),
            "free": disk["free"],
            "free_formatted": format_bytes(disk["free"]),
            "percent": disk["percent"]
        })
    return JSONResponse(
        content={"disks": formatted_disks},
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )


@app.get("/api/files")
async def list_files(path: str = None, user = Depends(require_auth), db = Depends(get_db)):
    ssh_cfg = get_user_ssh_config(db, user["id"])
    if ssh_cfg and ssh_cfg["host"] and ssh_cfg["username"]:
        try:
            if not path:
                path = ssh_cfg["remote_path"]
            items = ssh_manager.list_directory(
                ssh_cfg["host"], ssh_cfg["port"],
                ssh_cfg["username"], ssh_cfg["password"],
                path
            )
            parent = None
            normalized = path.rstrip("/")
            if normalized and normalized != "":
                parent = os.path.dirname(normalized)
                if parent == "/":
                    parent = "/"
            return {
                "success": True,
                "path": path,
                "parent": parent if parent != path else None,
                "items": items
            }
        except Exception as e:
            error_msg = str(e)
            if isinstance(e, paramiko.AuthenticationException):
                error_msg = "SSH 认证失败"
            elif isinstance(e, socket.timeout):
                error_msg = "SSH 连接超时"
            return JSONResponse(
                content={"success": False, "path": path, "error": error_msg, "items": []},
                status_code=500
            )

    require_ssh_mode(db, user["id"])
    if not path:
        path = "/"

    try:
        items = []
        for name in os.listdir(path):
            full_path = os.path.join(path, name)
            try:
                stat_info = os.stat(full_path)
                is_dir = os.path.isdir(full_path)
                items.append({
                    "name": name,
                    "type": "folder" if is_dir else "file",
                    "size": stat_info.st_size if not is_dir else 0,
                    "modified": datetime.datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
                    "path": full_path
                })
            except (PermissionError, OSError):
                continue

        items.sort(key=lambda x: (0 if x["type"] == "folder" else 1, x["name"].lower()))

        parent = os.path.dirname(path.rstrip("\\"))
        if parent == path.rstrip("\\"):
            parent = None

        return {
            "success": True,
            "path": path,
            "parent": parent,
            "items": items
        }
    except Exception as e:
        return JSONResponse(
            content={
                "success": False,
                "path": path,
                "error": str(e),
                "items": []
            },
            status_code=500,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )


@app.post("/api/files/rename")
async def rename_file(request: FileRenameRequest, user = Depends(require_auth), db = Depends(get_db)):
    ssh_cfg = get_user_ssh_config(db, user["id"])
    if ssh_cfg and ssh_cfg["host"] and ssh_cfg["username"]:
        try:
            new_path = ssh_manager.rename_remote(
                ssh_cfg["host"], ssh_cfg["port"],
                ssh_cfg["username"], ssh_cfg["password"],
                request.path, request.new_name
            )
            return {"success": True, "new_path": new_path}
        except Exception as e:
            return JSONResponse(
                content={"success": False, "error": str(e)},
                status_code=500
            )
    require_ssh_mode(db, user["id"])
    try:
        dir_path = os.path.dirname(request.path)
        new_path = os.path.join(dir_path, request.new_name)
        os.rename(request.path, new_path)
        return {"success": True, "new_path": new_path}
    except Exception as e:
        return JSONResponse(
            content={"success": False, "error": str(e)},
            status_code=500,
            headers={"Cache-Control": "no-cache"}
        )


@app.post("/api/files/delete")
async def delete_file(request: FileDeleteRequest, user = Depends(require_auth), db = Depends(get_db)):
    ssh_cfg = get_user_ssh_config(db, user["id"])
    if ssh_cfg and ssh_cfg["host"] and ssh_cfg["username"]:
        try:
            ssh_manager.delete_remote(
                ssh_cfg["host"], ssh_cfg["port"],
                ssh_cfg["username"], ssh_cfg["password"],
                request.path, request.type
            )
            return {"success": True}
        except Exception as e:
            return JSONResponse(
                content={"success": False, "error": str(e)},
                status_code=500
            )
    require_ssh_mode(db, user["id"])
    try:
        if request.type == "folder":
            os.rmdir(request.path)
        else:
            os.remove(request.path)
        return {"success": True}
    except OSError as e:
        if "[WinError 145]" in str(e) or "directory not empty" in str(e).lower():
            import shutil
            shutil.rmtree(request.path)
            return {"success": True}
        return JSONResponse(
            content={"success": False, "error": str(e)},
            status_code=500,
            headers={"Cache-Control": "no-cache"}
        )
    except Exception as e:
        return JSONResponse(
            content={"success": False, "error": str(e)},
            status_code=500,
            headers={"Cache-Control": "no-cache"}
        )


@app.post("/api/files/copy")
async def copy_file(request: FileCopyRequest, user = Depends(require_auth), db = Depends(get_db)):
    ssh_cfg = get_user_ssh_config(db, user["id"])
    if ssh_cfg and ssh_cfg["host"] and ssh_cfg["username"]:
        try:
            ssh_manager.copy_remote(
                ssh_cfg["host"], ssh_cfg["port"],
                ssh_cfg["username"], ssh_cfg["password"],
                request.source, request.destination
            )
            return {"success": True}
        except Exception as e:
            return JSONResponse(
                content={"success": False, "error": str(e)},
                status_code=500
            )
    require_ssh_mode(db, user["id"])
    try:
        import shutil
        if os.path.isdir(request.source):
            shutil.copytree(request.source, request.destination)
        else:
            shutil.copy2(request.source, request.destination)
        return {"success": True}
    except Exception as e:
        return JSONResponse(
            content={"success": False, "error": str(e)},
            status_code=500,
            headers={"Cache-Control": "no-cache"}
        )


@app.post("/api/files/move")
async def move_file(request: FileMoveRequest, user = Depends(require_auth), db = Depends(get_db)):
    ssh_cfg = get_user_ssh_config(db, user["id"])
    if ssh_cfg and ssh_cfg["host"] and ssh_cfg["username"]:
        try:
            ssh_manager.move_remote(
                ssh_cfg["host"], ssh_cfg["port"],
                ssh_cfg["username"], ssh_cfg["password"],
                request.source, request.destination
            )
            return {"success": True}
        except Exception as e:
            return JSONResponse(
                content={"success": False, "error": str(e)},
                status_code=500
            )
    require_ssh_mode(db, user["id"])
    try:
        os.rename(request.source, request.destination)
        return {"success": True}
    except Exception as e:
        return JSONResponse(
            content={"success": False, "error": str(e)},
            status_code=500,
            headers={"Cache-Control": "no-cache"}
        )


@app.post("/api/files/create-folder")
async def create_folder(request: FileCreateRequest, user = Depends(require_auth), db = Depends(get_db)):
    ssh_cfg = get_user_ssh_config(db, user["id"])
    if ssh_cfg and ssh_cfg["host"] and ssh_cfg["username"]:
        try:
            ssh_manager.create_folder_remote(
                ssh_cfg["host"], ssh_cfg["port"],
                ssh_cfg["username"], ssh_cfg["password"],
                f"{request.path.rstrip('/')}/{request.name}"
            )
            return {"success": True, "path": f"{request.path.rstrip('/')}/{request.name}"}
        except Exception as e:
            return JSONResponse(
                content={"success": False, "error": str(e)},
                status_code=500
            )
    require_ssh_mode(db, user["id"])
    try:
        full_path = os.path.join(request.path, request.name)
        os.makedirs(full_path, exist_ok=True)
        return {"success": True, "path": full_path}
    except Exception as e:
        return JSONResponse(
            content={"success": False, "error": str(e)},
            status_code=500,
            headers={"Cache-Control": "no-cache"}
        )


@app.post("/api/files/create-file")
async def create_file(request: FileCreateRequest, user = Depends(require_auth), db = Depends(get_db)):
    ssh_cfg = get_user_ssh_config(db, user["id"])
    if ssh_cfg and ssh_cfg["host"] and ssh_cfg["username"]:
        try:
            path = f"{request.path.rstrip('/')}/{request.name}"
            ssh_manager.create_file_remote(
                ssh_cfg["host"], ssh_cfg["port"],
                ssh_cfg["username"], ssh_cfg["password"],
                path
            )
            return {"success": True, "path": path}
        except Exception as e:
            return JSONResponse(
                content={"success": False, "error": str(e)},
                status_code=500
            )
    require_ssh_mode(db, user["id"])
    try:
        full_path = os.path.join(request.path, request.name)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write('')
        return {"success": True, "path": full_path}
    except Exception as e:
        return JSONResponse(
            content={"success": False, "error": str(e)},
            status_code=500,
            headers={"Cache-Control": "no-cache"}
        )


@app.post("/api/files/save")
async def save_file(request: FileSaveRequest, user = Depends(require_auth), db = Depends(get_db)):
    ssh_cfg = get_user_ssh_config(db, user["id"])
    if ssh_cfg and ssh_cfg["host"] and ssh_cfg["username"]:
        try:
            ssh_manager.write_file_content(
                ssh_cfg["host"], ssh_cfg["port"],
                ssh_cfg["username"], ssh_cfg["password"],
                request.path, request.content
            )
            return {"success": True}
        except Exception as e:
            return JSONResponse(
                content={"success": False, "error": str(e)},
                status_code=500
            )
    require_ssh_mode(db, user["id"])
    try:
        with open(request.path, 'w', encoding='utf-8') as f:
            f.write(request.content)
        return {"success": True}
    except Exception as e:
        return JSONResponse(
            content={"success": False, "error": str(e)},
            status_code=500,
            headers={"Cache-Control": "no-cache"}
        )


@app.post("/api/files/read")
async def read_file(request: FileReadRequest, user = Depends(require_auth), db = Depends(get_db)):
    ssh_cfg = get_user_ssh_config(db, user["id"])
    if ssh_cfg and ssh_cfg["host"] and ssh_cfg["username"]:
        try:
            content = ssh_manager.read_file_content(
                ssh_cfg["host"], ssh_cfg["port"],
                ssh_cfg["username"], ssh_cfg["password"],
                request.path
            )
            return {"success": True, "content": content}
        except Exception as e:
            return JSONResponse(
                content={"success": False, "error": str(e)},
                status_code=500
            )
    require_ssh_mode(db, user["id"])
    try:
        with open(request.path, 'r', encoding='utf-8') as f:
            content = f.read()
        return {"success": True, "content": content}
    except Exception as e:
        return JSONResponse(
            content={"success": False, "error": str(e)},
            status_code=500,
            headers={"Cache-Control": "no-cache"}
        )


@app.get("/api/ssh/status")
async def ssh_connection_status(user = Depends(require_auth), db = Depends(get_db)):
    cfg = get_user_ssh_config(db, user["id"])
    if not cfg or not cfg["host"] or not cfg["username"]:
        return {"configured": False, "connected": False, "message": "未配置 SSH 连接"}
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname=cfg["host"], port=cfg["port"], username=cfg["username"], password=cfg["password"], timeout=5)
        ssh.close()
        return {
            "configured": True,
            "connected": True,
            "host": cfg["host"],
            "username": cfg["username"],
            "remote_path": cfg["remote_path"],
            "message": f"已连接到 {cfg['host']}"
        }
    except Exception as e:
        return {
            "configured": True,
            "connected": False,
            "host": cfg["host"],
            "username": cfg["username"],
            "message": f"连接失败: {str(e)}"
        }


@app.post("/api/ssh/configure")
async def ssh_configure(config: SshConfigData, user = Depends(require_auth), db = Depends(get_db)):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname=config.host, port=config.port, username=config.username, password=config.password, timeout=10)
        ssh.close()

        cur = db.cursor()
        cur.execute(
            "INSERT INTO ssh_configs (user_id, host, port, username, password, remote_path) "
            "VALUES (%s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (user_id) DO UPDATE SET host = %s, port = %s, username = %s, password = %s, remote_path = %s, updated_at = NOW()",
            (user["id"], config.host, config.port, config.username, config.password, config.remote_path or "/",
             config.host, config.port, config.username, config.password, config.remote_path or "/")
        )
        db.commit()
        cur.close()

        saved_cfg = get_user_ssh_config(db, user["id"])
        return {
            "success": True,
            "message": "连接成功！已保存配置到数据库",
            "config": {
                "host": saved_cfg["host"],
                "port": saved_cfg["port"],
                "username": saved_cfg["username"],
                "password": saved_cfg["password"],
                "remote_path": saved_cfg["remote_path"]
            }
        }
    except paramiko.AuthenticationException:
        return {"success": False, "message": "SSH 认证失败，请检查用户名和密码"}
    except socket.timeout:
        return {"success": False, "message": "SSH 连接超时（10秒），请检查服务器地址和端口"}
    except OSError as e:
        return {"success": False, "message": f"无法连接到服务器: {str(e)}"}
    except Exception as e:
        return {"success": False, "message": f"连接失败: {str(e)}"}


@app.api_route("/api/device/register", methods=["GET", "POST"])
async def register_device(request: Request):
    result = await device_manager.register_device(request)
    return {"code": 0, "message": "ok", "data": result}


@app.api_route("/api/device/heartbeat", methods=["GET", "POST"])
async def send_heartbeat(request: Request):
    result = await device_manager.process_heartbeat(request)
    return {"code": 0, "message": "ok", "data": result}


@app.post("/api/devices")
async def create_device(request: Request, user = Depends(require_auth), db = Depends(get_db)):
    result = await device_manager.create_device(request)
    return {"code": 0, "message": "ok", "data": result}


@app.get("/api/devices")
async def get_devices(user = Depends(require_auth), db = Depends(get_db)):
    devices = await device_manager.get_devices_list()
    return {"code": 0, "message": "ok", "data": devices}


@app.get("/api/health")
async def health_check():
    return await device_manager.health_check()


class SshClientManager:
    def __init__(self):
        self._connections = {}

    def _get_key(self, host, port):
        return f"{host}:{port}"

    def get_connection(self, host, port, username, password):
        key = self._get_key(host, port)
        if key in self._connections:
            try:
                self._connections[key].exec_command("echo alive", timeout=5)
                return self._connections[key]
            except:
                try:
                    self._connections[key].close()
                except:
                    pass
                del self._connections[key]

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname=host, port=port, username=username, password=password, timeout=int(os.getenv("SSH_CONNECT_TIMEOUT", "10")))
        self._connections[key] = ssh
        return ssh

    def _sudo(self, host, port, username, password, command, timeout=None):
        if timeout is None:
            timeout = int(os.getenv("SSH_SUDO_TIMEOUT", "30"))
        ssh = self.get_connection(host, port, username, password)
        full_cmd = f"sudo {command}"
        stdin, stdout, stderr = ssh.exec_command(full_cmd, timeout=timeout)
        exit_code = stdout.channel.recv_exit_status()
        error = stderr.read().decode("utf-8").strip()
        return exit_code == 0, error, stdout.read().decode("utf-8")

    def _write_temp_sudo_mv(self, host, port, username, password, target_path, content):
        temp_name = "web_admin_" + str(int(time.time())) + "_" + str(hash(target_path) % 10000)
        temp_path = "/tmp/" + temp_name
        ssh = self.get_connection(host, port, username, password)
        with ssh.open_sftp() as sftp:
            with sftp.open(temp_path, "w") as f:
                f.write(content.encode("utf-8") if isinstance(content, str) else content)
        ok, err, _ = self._sudo(host, port, username, password, "mv " + shlex.quote(temp_path) + " " + shlex.quote(target_path))
        if not ok:
            self._sudo(host, port, username, password, "rm -f " + shlex.quote(temp_path))
            raise Exception(err or "文件操作失败")
        return True

    def list_directory(self, host, port, username, password, path):
        ok, err, out = self._sudo(host, port, username, password, f"ls -la {shlex.quote(str(path))}")
        if not ok:
            raise Exception(err or "读取目录失败")
        lines = [l for l in out.split("\n") if l.strip()]
        items = []
        for line in lines:
            parts = line.split()
            if len(parts) < 9:
                continue
            if parts[0].startswith("total") or parts[0] == "总用量":
                continue
            name = " ".join(parts[8:])
            if name in (".", ".."):
                continue
            is_dir = parts[0].startswith("d")
            try:
                size = int(parts[4])
            except:
                size = 0
            month = parts[5]
            day = parts[6]
            time_or_year = parts[7]
            now_year = datetime.datetime.now().year
            try:
                mod_str = month + " " + day + " " + time_or_year
                modified = datetime.datetime.strptime(mod_str + " " + str(now_year), "%b %d %H:%M %Y").isoformat()
            except:
                try:
                    modified = datetime.datetime.strptime(mod_str, "%b %d %Y").isoformat()
                except:
                    modified = datetime.datetime.now().isoformat()
            items.append({
                "name": name,
                "type": "folder" if is_dir else "file",
                "size": 0 if is_dir else size,
                "modified": modified,
                "path": f"{path.rstrip('/')}/{name}"
            })
        items.sort(key=lambda x: (0 if x["type"] == "folder" else 1, x["name"].lower()))
        return items

    def rename_remote(self, host, port, username, password, old_path, new_name):
        dir_path = old_path.rsplit("/", 1)[0]
        new_path = (dir_path + "/" + new_name) if dir_path else ("/" + new_name)
        cmd = "mv " + shlex.quote(old_path) + " " + shlex.quote(new_path)
        ok, err, _ = self._sudo(host, port, username, password, cmd)
        if not ok:
            raise Exception(err or "重命名失败")
        return new_path

    def delete_remote(self, host, port, username, password, path, type_):
        sq = shlex.quote
        if type_ == "folder":
            ok, err, _ = self._sudo(host, port, username, password, "rm -rf " + sq(path))
        else:
            ok, err, _ = self._sudo(host, port, username, password, "rm -f " + sq(path))
        if not ok:
            raise Exception(err or "删除失败")
        return True

    def copy_remote(self, host, port, username, password, source, destination):
        sq = shlex.quote
        ok, err, _ = self._sudo(host, port, username, password, "cp -r " + sq(source) + " " + sq(destination))
        if not ok:
            raise Exception(err or "复制失败")
        return True

    def move_remote(self, host, port, username, password, source, destination):
        sq = shlex.quote
        ok, err, _ = self._sudo(host, port, username, password, "mv " + sq(source) + " " + sq(destination))
        if not ok:
            raise Exception(err or "移动失败")
        return True

    def create_folder_remote(self, host, port, username, password, path):
        ok, err, _ = self._sudo(host, port, username, password, "mkdir -p " + shlex.quote(path))
        if not ok:
            raise Exception(err or "创建文件夹失败")
        return True

    def create_file_remote(self, host, port, username, password, path):
        return self._write_temp_sudo_mv(host, port, username, password, path, "")

    def read_file_content(self, host, port, username, password, path):
        ok, err, out = self._sudo(host, port, username, password, "cat " + shlex.quote(path))
        if not ok:
            raise Exception(err or "读取文件失败")
        return out

    def write_file_content(self, host, port, username, password, path, content):
        return self._write_temp_sudo_mv(host, port, username, password, path, content)


ssh_manager = SshClientManager()

# 确保静态文件优先服务
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
# 模板文件服务放在最后，避免覆盖静态文件
app.mount("/", StaticFiles(directory=os.path.join(BASE_DIR, "templates"), html=True), name="templates")

if __name__ == "__main__":
    uvicorn.run(
        app,
        host=os.getenv("APP_HOST", "0.0.0.0"),
        port=int(os.getenv("APP_PORT", "8081"))
    )
