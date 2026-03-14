"""Main FastAPI application entry point"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jinja2 import filters

from core.database import engine, Base
from core.config import settings

# Import models BEFORE creating tables
from core import models  # noqa: F401

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.APP_TITLE)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="templates")
templates.env.filters['filesizeformat'] = filters.do_filesizeformat
templates.env.globals['app_title'] = settings.APP_TITLE


# ============== Include Routers ==============

from routes import auth, dashboard, instances, settings

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(instances.router)
app.include_router(settings.router)


# ============== Exception Handlers ==============

from fastapi import Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse

from core.database import get_db
from core.models import AdminUser


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Handle 404 errors"""
    return templates.TemplateResponse("errors/404.html", {
        "request": request,
        "status_code": 404,
        "message": "The page you're looking for doesn't exist."
    }, status_code=404)


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc):
    """Handle general exceptions"""
    return templates.TemplateResponse("errors/500.html", {
        "request": request,
        "status_code": 500,
        "message": "Something went wrong. Please try again later."
    }, status_code=500)


# ============== Additional Routes ==============

from fastapi.responses import RedirectResponse
from jose import JWTError, jwt
from core.config import settings


def get_current_user(request: Request, db = Depends(get_db)):
    """Get current logged-in user from session cookie"""
    token = request.cookies.get("access_token")
    if not token:
        return None

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        user = db.query(AdminUser).filter(AdminUser.username == username).first()
        return user
    except JWTError:
        return None


@app.get("/root-redirect", response_class=HTMLResponse)
async def root_redirect(request: Request, user: AdminUser = Depends(get_current_user)):
    """Root redirect"""
    db = next(get_db())
    
    def admin_exists(db_session):
        return db_session.query(AdminUser).first() is not None
    
    if not admin_exists(db):
        return RedirectResponse(url="/setup")
    if user:
        return RedirectResponse(url="/")
    return RedirectResponse(url="/login")


# ============== Health Check Endpoint ==============

@app.get("/health")
async def health_check(db=Depends(get_db)):
    """
    Health check endpoint for monitoring.
    Returns system status including LXD connectivity and disk space.
    """
    import shutil
    
    health_status = {
        "status": "healthy",
        "checks": {}
    }
    
    # Check database connection
    try:
        db.execute("SELECT 1")
        health_status["checks"]["database"] = {"status": "ok"}
    except Exception as e:
        health_status["checks"]["database"] = {"status": "error", "message": str(e)}
        health_status["status"] = "unhealthy"
    
    # Check LXD connection
    try:
        from services.lxd_service import LXDService
        from core.models import LXDSettings
        
        lxd_settings = db.query(LXDSettings).first()
        if lxd_settings:
            lxd_service = LXDService(db)
            lxd_service.get_client()
            
            if lxd_service.is_connected():
                # Try to get server info
                server = lxd_service.client.api.get().json()
                health_status["checks"]["lxd"] = {
                    "status": "ok",
                    "server": server.get("environment", {}).get("server_name", "unknown")
                }
            else:
                health_status["checks"]["lxd"] = {"status": "disconnected"}
                health_status["status"] = "degraded"
        else:
            health_status["checks"]["lxd"] = {"status": "not_configured"}
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["checks"]["lxd"] = {"status": "error", "message": str(e)}
        health_status["status"] = "unhealthy"
    
    # Check disk space
    try:
        total, used, free = shutil.disk_usage("/")
        free_gb = free / (1024 ** 3)
        health_status["checks"]["disk"] = {
            "status": "ok",
            "free_gb": round(free_gb, 2),
            "used_percent": round((used / total) * 100, 1)
        }
        
        # Warn if disk space is low
        if free_gb < 10:
            health_status["checks"]["disk"]["warning"] = "Low disk space"
            if health_status["status"] == "healthy":
                health_status["status"] = "degraded"
    except Exception as e:
        health_status["checks"]["disk"] = {"status": "error", "message": str(e)}
    
    # Check if admin user exists
    try:
        admin_exists = db.query(AdminUser).first() is not None
        health_status["checks"]["admin_user"] = {"status": "ok" if admin_exists else "not_setup"}
        if not admin_exists:
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["checks"]["admin_user"] = {"status": "error", "message": str(e)}
    
    return health_status


# ============== Startup ==============

@app.on_event("startup")
async def startup_event():
    """Application startup"""
    print(f"🚀 {settings.APP_TITLE} started")
