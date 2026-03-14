"""Dashboard routes"""
from datetime import datetime
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import AdminUser, LXDSettings, VMDefaultSettings
from services.metrics_service import get_system_metrics
from services.lxd_service import LXDService

templates = Jinja2Templates(directory="templates")

router = APIRouter()


def get_current_user(request: Request, db: Session = Depends(get_db)):
    """Get current logged-in user from session cookie"""
    from jose import JWTError, jwt
    from core.security import SECRET_KEY, ALGORITHM
    
    token = request.cookies.get("access_token")
    if not token:
        return None

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        user = db.query(AdminUser).filter(AdminUser.username == username).first()
        return user
    except JWTError:
        return None


def require_auth(request: Request, db: Session = Depends(get_db)):
    """Dependency to require authentication"""
    user = get_current_user(request, db)
    if user is None:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/login"}
        )
    return user


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    user: AdminUser = Depends(require_auth),
    db: Session = Depends(get_db),
    page: int = 1,
    search: str = ""
):
    """Admin dashboard with LXD instance stats and system metrics"""
    instances = []
    total_instances = 0
    running_instances = 0
    lxd_connected = False

    # Get system metrics
    metrics = get_system_metrics()

    # Get LXD instances
    try:
        lxd_service = LXDService(db)
        lxd_service.get_client()

        if lxd_service.is_connected():
            instance_stats = lxd_service.get_instance_stats()
            total_instances = instance_stats["total"]
            running_instances = instance_stats["running"]
            lxd_connected = instance_stats["connected"]

            # Get instance details
            instances = lxd_service.get_all_instances()

            # Filter by search
            if search:
                instances = [i for i in instances if search.lower() in i['name'].lower()]

            # Paginate
            per_page = 10
            total_pages = (len(instances) + per_page - 1) // per_page
            start = (page - 1) * per_page
            end = start + per_page
            instances = instances[start:end]
    except Exception:
        lxd_connected = False

    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request,
        "username": user.username,
        "is_first_login": user.is_first_login,
        "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_instances": total_instances,
        "running_instances": running_instances,
        "lxd_connected": lxd_connected,
        "instances": instances,
        "page": page,
        "search": search,
        "vm_defaults": db.query(VMDefaultSettings).first(),
        # System metrics
        "cpu_percent": metrics["cpu_percent"],
        "memory_used": metrics["memory_used"],
        "memory_total": metrics["memory_total"],
        "memory_percent": metrics["memory_percent"],
        "disk_used": metrics["disk_used"],
        "disk_total": metrics["disk_total"],
        "disk_percent": metrics["disk_percent"]
    })
