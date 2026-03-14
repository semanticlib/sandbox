"""Settings routes: LXD, VM defaults, password change"""
from fastapi import APIRouter, Request, Depends, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import AdminUser, LXDSettings, VMDefaultSettings
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
    password_error: str = None,
    vm_success: str = None,
    vm_error: str = None,
    templates_success: str = None
):
    """Settings page - change password, LXD configuration, and VM defaults"""
    from core.models import ConnectionTemplate
    
    lxd_settings = db.query(LXDSettings).first()
    vm_settings = db.query(VMDefaultSettings).first()
    connection_templates = db.query(ConnectionTemplate).first()

    return templates.TemplateResponse("admin/settings.html", {
        "request": request,
        "username": user.username,
        "lxd_settings": lxd_settings,
        "vm_settings": vm_settings,
        "connection_templates": connection_templates,
        "lxd_success": lxd_success,
        "lxd_error": lxd_error,
        "password_success": password_success,
        "password_error": password_error,
        "vm_success": vm_success,
        "vm_error": vm_error,
        "templates_success": templates_success
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
    from core.models import ConnectionTemplate
    
    if len(new_password) < 6:
        return templates.TemplateResponse("admin/settings.html", {
            "request": request,
            "username": user.username,
            "lxd_settings": db.query(LXDSettings).first(),
            "vm_settings": db.query(VMDefaultSettings).first(),
            "connection_templates": db.query(ConnectionTemplate).first(),
            "password_error": "New password must be at least 6 characters"
        })

    if new_password != confirm_password:
        return templates.TemplateResponse("admin/settings.html", {
            "request": request,
            "username": user.username,
            "lxd_settings": db.query(LXDSettings).first(),
            "vm_settings": db.query(VMDefaultSettings).first(),
            "connection_templates": db.query(ConnectionTemplate).first(),
            "password_error": "New passwords do not match"
        })

    if not verify_password(current_password, user.password_hash):
        return templates.TemplateResponse("admin/settings.html", {
            "request": request,
            "username": user.username,
            "lxd_settings": db.query(LXDSettings).first(),
            "vm_settings": db.query(VMDefaultSettings).first(),
            "connection_templates": db.query(ConnectionTemplate).first(),
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
            "message": "Certificate generated! Copy the certificate and add it to LXD trust store."
        })
    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)})


@router.post("/settings/vm")
async def save_vm_settings(
    request: Request,
    username: str = Form(...),
    cpu: int = Form(...),
    memory: int = Form(...),
    disk: int = Form(...),
    swap: int = Form(...),
    image_fingerprint: str = Form(""),
    image_alias: str = Form(""),
    image_description: str = Form(""),
    cloud_init: str = Form(""),
    db: Session = Depends(get_db)
):
    """Save default VM settings"""
    # Validate cloud-init template if provided
    if cloud_init.strip():
        from services.cloud_init_service import validate_cloud_init_template
        is_valid, error_msg = validate_cloud_init_template(cloud_init)
        if not is_valid:
            return RedirectResponse(
                url=f"/settings?vm_error={error_msg}",
                status_code=303
            )

    settings = db.query(VMDefaultSettings).first()

    if settings:
        settings.username = username
        settings.cpu = cpu
        settings.memory = memory
        settings.disk = disk
        settings.swap = swap
        settings.image_fingerprint = image_fingerprint if image_fingerprint else None
        settings.image_alias = image_alias if image_alias else None
        settings.image_description = image_description if image_description else None
        settings.cloud_init = cloud_init if cloud_init else None
    else:
        settings = VMDefaultSettings(
            username=username,
            cpu=cpu,
            memory=memory,
            disk=disk,
            swap=swap,
            image_fingerprint=image_fingerprint if image_fingerprint else None,
            image_alias=image_alias if image_alias else None,
            image_description=image_description if image_description else None,
            cloud_init=cloud_init if cloud_init else None
        )
        db.add(settings)

    db.commit()

    return RedirectResponse(url="/settings?vm_success=VM defaults saved successfully", status_code=303)


@router.get("/settings/vm/template")
async def get_cloud_init_template():
    """Get the default cloud-init template"""
    from services.cloud_init_service import DEFAULT_CLOUD_INIT_TEMPLATE
    return JSONResponse({
        "success": True,
        "template": DEFAULT_CLOUD_INIT_TEMPLATE
    })


@router.get("/settings/vm/images")
async def get_available_images(db: Session = Depends(get_db)):
    """Get available LXD images for VM creation"""
    from services.lxd_service import LXDService
    
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
            # Get image info
            description = img.properties.get('description', 'Unknown')
            aliases = [alias.name for alias in img.aliases]
            
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
                "description": description,
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
    except Exception as e:
        return JSONResponse({
            "success": False,
            "message": str(e)
        })


@router.get("/settings/connection-templates")
async def get_connection_templates(db: Session = Depends(get_db)):
    """Get connection templates (SSH config and instructions)"""
    from core.models import ConnectionTemplate
    from services.ssh_config_service import DEFAULT_SSH_CONFIG_TEMPLATE, DEFAULT_INSTRUCTIONS_TEMPLATE
    
    templates = db.query(ConnectionTemplate).first()
    
    return JSONResponse({
        "success": True,
        "ssh_config_template": templates.ssh_config_template if templates and templates.ssh_config_template else DEFAULT_SSH_CONFIG_TEMPLATE,
        "instructions_template": templates.instructions_template if templates and templates.instructions_template else DEFAULT_INSTRUCTIONS_TEMPLATE
    })


@router.post("/settings/connection-templates")
async def save_connection_templates(
    request: Request,
    ssh_config_template: str = Form(...),
    instructions_template: str = Form(...),
    db: Session = Depends(get_db)
):
    """Save connection templates"""
    from core.models import ConnectionTemplate
    
    templates = db.query(ConnectionTemplate).first()
    
    if templates:
        templates.ssh_config_template = ssh_config_template
        templates.instructions_template = instructions_template
    else:
        templates = ConnectionTemplate(
            ssh_config_template=ssh_config_template,
            instructions_template=instructions_template
        )
        db.add(templates)
    
    db.commit()
    
    return RedirectResponse(url="/settings?templates_success=Connection templates saved successfully", status_code=303)
