"""Settings routes: LXD connection and password change"""
from fastapi import APIRouter, Request, Depends, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import AdminUser, LXDSettings
from core.config import settings
from core.security import get_password_hash, verify_password
from services.lxd_service import LXDService

templates = Jinja2Templates(directory="templates")
templates.env.globals['app_title'] = settings.APP_TITLE

router = APIRouter(tags=["settings"])


def get_current_user(request: Request, db: Session = Depends(get_db)):
    """Get current logged-in user from session cookie"""
    from jose import JWTError, jwt
    from core.config import settings

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


def require_auth(request: Request, db: Session = Depends(get_db)):
    """Dependency to require authentication"""
    user = get_current_user(request, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/login"}
        )
    return user


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    user: AdminUser = Depends(require_auth),
    db: Session = Depends(get_db),
    lxd_success: str = None,
    lxd_error: str = None,
    password_success: str = None,
    password_error: str = None
):
    """Settings page - change password, LXD configuration"""
    lxd_settings = db.query(LXDSettings).first()

    return templates.TemplateResponse("admin/settings.html", {
        "request": request,
        "username": user.username,
        "lxd_settings": lxd_settings,
        "lxd_success": lxd_success,
        "lxd_error": lxd_error,
        "password_success": password_success,
        "password_error": password_error
    })


@router.post("/settings/change-password")
async def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_auth)
):
    """Handle password change"""
    from core.security import validate_password_strength

    # Validate new password strength
    is_valid, error = validate_password_strength(new_password)
    if not is_valid:
        return templates.TemplateResponse("admin/settings.html", {
            "request": request,
            "username": user.username,
            "lxd_settings": db.query(LXDSettings).first(),
            "password_error": error
        })

    if new_password != confirm_password:
        return templates.TemplateResponse("admin/settings.html", {
            "request": request,
            "username": user.username,
            "lxd_settings": db.query(LXDSettings).first(),
            "password_error": "New passwords do not match"
        })

    if not verify_password(current_password, user.password_hash):
        return templates.TemplateResponse("admin/settings.html", {
            "request": request,
            "username": user.username,
            "lxd_settings": db.query(LXDSettings).first(),
            "password_error": "Current password is incorrect"
        })

    user.password_hash = get_password_hash(new_password)
    user.is_first_login = False
    db.commit()

    return RedirectResponse(url="/settings?password_success=true", status_code=303)


@router.post("/settings/lxd")
async def save_lxd_settings(
    request: Request,
    server_url: str = Form(""),
    use_socket: str = Form("off"),
    client_cert: str = Form(""),
    client_key: str = Form(""),
    verify_ssl: str = Form("off"),
    db: Session = Depends(get_db)
):
    """Save LXD connection settings"""
    settings = db.query(LXDSettings).first()

    if settings:
        settings.server_url = server_url if server_url else None
        settings.use_socket = use_socket == "on"
        settings.client_cert = client_cert if client_cert else None
        settings.client_key = client_key if client_key else None
        settings.verify_ssl = verify_ssl == "on"
    else:
        settings = LXDSettings(
            server_url=server_url if server_url else None,
            use_socket=use_socket == "on",
            client_cert=client_cert if client_cert else None,
            client_key=client_key if client_key else None,
            verify_ssl=verify_ssl == "on"
        )
        db.add(settings)

    db.commit()

    return RedirectResponse(url="/settings?lxd_success=Settings saved successfully", status_code=303)


@router.post("/settings/lxd/test")
async def test_lxd_connection(request: Request, db: Session = Depends(get_db)):
    """Test LXD connection"""
    lxd_service = LXDService(db)
    result = lxd_service.test_connection()
    return JSONResponse(result)


@router.post("/settings/lxd/generate-cert")
async def generate_certificate(request: Request):
    """Generate client certificate for LXD authentication"""
    try:
        from utils.cert_utils import generate_client_certificate
        cert_pem, key_pem = generate_client_certificate("fastapi-client")
        return JSONResponse({
            "success": True,
            "certificate": cert_pem,
            "key": key_pem,
            "message": "Certificate generated successfully"
        })
    except Exception:
        import logging
        logging.exception("Error generating certificate")
        return JSONResponse({"success": False, "message": "Failed to generate certificate"})


@router.get("/settings/vm/images")
async def get_available_images(
    db: Session = Depends(get_db),
    instance_type: str = "virtual-machine"
):
    """Get available LXD images for VM or container creation"""
    lxd_service = LXDService(db)
    lxd_service.get_client()

    if not lxd_service.is_connected():
        return JSONResponse({
            "success": False,
            "message": "LXD not connected"
        })

    try:
        images = []
        for img in lxd_service.client.images.all():
            # Filter by instance type
            if img.type != instance_type:
                continue

            # Get image info
            description = img.properties.get('description', 'Unknown')

            # Handle aliases which can be dicts or objects
            aliases = []
            for a in img.aliases:
                if isinstance(a, dict):
                    name = a.get('name')
                else:
                    name = getattr(a, 'name', None)
                if name:
                    aliases.append(name)

            # Handle created_at which might be datetime or string
            created_at = None
            if img.created_at:
                if hasattr(img.created_at, 'isoformat'):
                    created_at = img.created_at.isoformat()
                else:
                    created_at = str(img.created_at)

            images.append({
                "fingerprint": img.fingerprint[:12],  # Short fingerprint
                "full_fingerprint": img.fingerprint,
                "description": f"{description}",
                "aliases": aliases,
                "architecture": img.architecture,
                "type": img.type,
                "size": img.size,
                "created_at": created_at
            })

        # Sort by description
        images.sort(key=lambda x: x['description'])

        return JSONResponse({
            "success": True,
            "images": images
        })
    except Exception:
        import logging
        logging.exception("Error fetching images")
        return JSONResponse({
            "success": False,
            "message": "Failed to fetch images"
        })


@router.get("/settings/vm/template")
async def get_vm_cloud_init_template():
    """Return the default cloud-init template text."""
    from services.cloud_init_service import DEFAULT_CLOUD_INIT_TEMPLATE
    return JSONResponse({"success": True, "template": DEFAULT_CLOUD_INIT_TEMPLATE})


@router.get("/settings/connection-templates")
async def get_connection_templates():
    """Get default SSH config template"""
    from services.ssh_config_service import DEFAULT_SSH_CONFIG_TEMPLATE
    return JSONResponse({
        "success": True,
        "ssh_config_template": DEFAULT_SSH_CONFIG_TEMPLATE
    })
