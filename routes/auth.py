"""Authentication routes: setup, login, logout"""
from datetime import datetime
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import AdminUser
from core.security import get_password_hash, verify_password, create_access_token
from core.config import settings
from core.rate_limiter import login_rate_limiter

templates = Jinja2Templates(directory="templates")
templates.env.globals['app_title'] = settings.APP_TITLE

router = APIRouter()


def admin_exists(db: Session) -> bool:
    """Check if any admin user exists"""
    return db.query(AdminUser).first() is not None


def get_client_ip(request: Request) -> str:
    """Get client IP address from request"""
    # Check for X-Forwarded-For header (behind proxy)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    # Check for X-Real-IP header
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    # Fallback to direct client IP
    return request.client.host if request.client else "unknown"


@router.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request, error: str = None):
    """First-launch setup page - create admin account"""
    db = next(get_db())
    if admin_exists(db):
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("auth/setup.html", {
        "request": request,
        "error": error
    })


@router.post("/setup")
async def setup_admin(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Handle setup form - create first admin"""
    # Rate limit setup attempts (prevent brute-force on first admin account)
    client_ip = get_client_ip(request)
    if login_rate_limiter.is_rate_limited(client_ip):
        retry_after = login_rate_limiter.get_retry_after(client_ip)
        return templates.TemplateResponse("auth/setup.html", {
            "request": request,
            "error": f"Too many attempts. Please try again in {retry_after} seconds."
        })
    
    if admin_exists(db):
        return RedirectResponse(url="/login")

    if password != confirm_password:
        return templates.TemplateResponse("auth/setup.html", {
            "request": request,
            "error": "Passwords do not match"
        })

    # Validate password strength
    from core.security import validate_password_strength
    is_valid, error = validate_password_strength(password)
    if not is_valid:
        return templates.TemplateResponse("auth/setup.html", {
            "request": request,
            "error": error
        })

    existing = db.query(AdminUser).filter(AdminUser.username == username).first()
    if existing:
        return templates.TemplateResponse("auth/setup.html", {
            "request": request,
            "error": "Username already taken"
        })

    admin = AdminUser(
        username=username,
        password_hash=get_password_hash(password),
        is_active=True,
        is_first_login=True
    )
    db.add(admin)
    db.commit()

    access_token = create_access_token(data={"sub": admin.username})
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=3600,  # 1 hour (matches ACCESS_TOKEN_EXPIRE_MINUTES)
        samesite="lax",
        secure=True  # Only send over HTTPS
    )
    return response


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = None):
    """Show login page"""
    db = next(get_db())
    if not admin_exists(db):
        return RedirectResponse(url="/setup")

    return templates.TemplateResponse("auth/login.html", {
        "request": request,
        "error": error
    })


@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Handle login form submission"""
    # Get client IP for rate limiting
    client_ip = get_client_ip(request)
    
    # Rate limit by IP address
    if login_rate_limiter.is_rate_limited(client_ip):
        retry_after = login_rate_limiter.get_retry_after(client_ip)
        return templates.TemplateResponse("auth/login.html", {
            "request": request,
            "error": f"Too many login attempts. Please try again in {retry_after} seconds."
        })
    
    # Also rate limit by username to prevent targeted attacks
    if login_rate_limiter.is_rate_limited(f"user:{username}"):
        retry_after = login_rate_limiter.get_retry_after(f"user:{username}")
        return templates.TemplateResponse("auth/login.html", {
            "request": request,
            "error": f"Too many login attempts for this account. Please try again in {retry_after} seconds."
        })
    
    user = db.query(AdminUser).filter(AdminUser.username == username).first()

    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse("auth/login.html", {
            "request": request,
            "error": "Invalid username or password"
        })

    if not user.is_active:
        return templates.TemplateResponse("auth/login.html", {
            "request": request,
            "error": "Account is disabled"
        })

    # Reset rate limiter on successful login
    login_rate_limiter.reset(client_ip)
    login_rate_limiter.reset(f"user:{username}")

    access_token = create_access_token(data={"sub": user.username})
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=3600,  # 1 hour (matches ACCESS_TOKEN_EXPIRE_MINUTES)
        samesite="lax",
        secure=True  # Only send over HTTPS
    )
    return response


@router.get("/logout")
async def logout():
    """Handle logout"""
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("access_token")
    return response
