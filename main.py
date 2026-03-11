import os
from datetime import datetime
from fastapi import FastAPI, Request, Depends, HTTPException, status, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session

from database import engine, get_db, Base
from models import AdminUser
from auth import get_password_hash, verify_password, create_access_token
from jose import JWTError, jwt
from auth import SECRET_KEY, ALGORITHM

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Admin Panel")

templates = Jinja2Templates(directory="templates")


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


def get_current_user(request: Request, db: Session = Depends(get_db)):
    """Get current logged-in user from session cookie"""
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
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/login"}
        )
    return user


def admin_exists(db: Session) -> bool:
    """Check if any admin user exists"""
    return db.query(AdminUser).first() is not None


@app.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request, error: str = None):
    """First-launch setup page - create admin account"""
    db = next(get_db())
    if admin_exists(db):
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("auth/setup.html", {
        "request": request,
        "error": error
    })


@app.post("/setup")
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
    
    # Check if username already exists
    existing = db.query(AdminUser).filter(AdminUser.username == username).first()
    if existing:
        return templates.TemplateResponse("auth/setup.html", {
            "request": request,
            "error": "Username already taken"
        })
    
    # Create admin user
    admin = AdminUser(
        username=username,
        password_hash=get_password_hash(password),
        is_active=True,
        is_first_login=True
    )
    db.add(admin)
    db.commit()
    
    # Auto-login after setup
    access_token = create_access_token(data={"sub": admin.username})
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(key="access_token", value=access_token, httponly=True, max_age=1800)
    return response


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = None):
    """Show login page"""
    db = next(get_db())
    if not admin_exists(db):
        return RedirectResponse(url="/setup")
    
    return templates.TemplateResponse("auth/login.html", {
        "request": request,
        "error": error
    })


@app.post("/login")
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
    
    # Create access token
    access_token = create_access_token(data={"sub": user.username})
    
    # Redirect to dashboard
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(key="access_token", value=access_token, httponly=True, max_age=1800)
    return response


@app.get("/logout")
async def logout():
    """Handle logout"""
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("access_token")
    return response


@app.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    user: AdminUser = Depends(require_auth)
):
    """Admin dashboard page"""
    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request,
        "username": user.username,
        "is_first_login": user.is_first_login,
        "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    user: AdminUser = Depends(require_auth),
    success: str = None,
    error: str = None
):
    """Settings page - change password"""
    return templates.TemplateResponse("admin/settings.html", {
        "request": request,
        "username": user.username,
        "success": success,
        "error": error
    })


@app.post("/settings/change-password")
async def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_auth)
):
    """Handle password change"""
    if len(new_password) < 6:
        return templates.TemplateResponse("admin/settings.html", {
            "request": request,
            "username": user.username,
            "error": "New password must be at least 6 characters"
        })
    
    if new_password != confirm_password:
        return templates.TemplateResponse("admin/settings.html", {
            "request": request,
            "username": user.username,
            "error": "New passwords do not match"
        })
    
    if not verify_password(current_password, user.password_hash):
        return templates.TemplateResponse("admin/settings.html", {
            "request": request,
            "username": user.username,
            "error": "Current password is incorrect"
        })
    
    # Update password
    user.password_hash = get_password_hash(new_password)
    user.is_first_login = False
    db.commit()
    
    return RedirectResponse(url="/admin/settings?success=true", status_code=303)


@app.get("/root-redirect", response_class=HTMLResponse)
async def root_redirect(request: Request, user: AdminUser = Depends(get_current_user)):
    """Root redirect"""
    db = next(get_db())
    if not admin_exists(db):
        return RedirectResponse(url="/setup")
    if user:
        return RedirectResponse(url="/")
    return RedirectResponse(url="/login")


from database import SessionLocal
