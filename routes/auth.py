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

templates = Jinja2Templates(directory="templates")
templates.env.globals['app_title'] = settings.APP_TITLE

router = APIRouter()


def admin_exists(db: Session) -> bool:
    """Check if any admin user exists"""
    return db.query(AdminUser).first() is not None


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
    if admin_exists(db):
        return RedirectResponse(url="/login")

    if password != confirm_password:
        return templates.TemplateResponse("auth/setup.html", {
            "request": request,
            "error": "Passwords do not match"
        })

    if len(password) < 6:
        return templates.TemplateResponse("auth/setup.html", {
            "request": request,
            "error": "Password must be at least 6 characters"
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
    response.set_cookie(key="access_token", value=access_token, httponly=True, max_age=1800)
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

    access_token = create_access_token(data={"sub": user.username})
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(key="access_token", value=access_token, httponly=True, max_age=1800)
    return response


@router.get("/logout")
async def logout():
    """Handle logout"""
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("access_token")
    return response
