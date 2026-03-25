"""Settings routes: LXD, VM defaults, password change"""
from fastapi import APIRouter, Request, Depends, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import AdminUser, LXDSettings, VMDefaultSettings, ContainerDefaultSettings
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
    container_success: str = None,
    container_error: str = None,
    templates_success: str = None
):
    """Settings page - change password, LXD configuration, and VM/container defaults"""
    from core.models import ConnectionTemplate

    lxd_settings = db.query(LXDSettings).first()
    vm_settings = db.query(VMDefaultSettings).first()
    container_settings = db.query(ContainerDefaultSettings).first()
    connection_templates = db.query(ConnectionTemplate).first()

    return templates.TemplateResponse("admin/settings.html", {
        "request": request,
        "username": user.username,
        "lxd_settings": lxd_settings,
        "vm_settings": vm_settings,
        "container_settings": container_settings,
        "connection_templates": connection_templates,
        "lxd_success": lxd_success,
        "lxd_error": lxd_error,
        "password_success": password_success,
        "password_error": password_error,
        "vm_success": vm_success,
        "vm_error": vm_error,
        "container_success": container_success,
        "container_error": container_error,
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
    from core.security import validate_password_strength

    # Validate new password strength
    is_valid, error = validate_password_strength(new_password)
    if not is_valid:
        return templates.TemplateResponse("admin/settings.html", {
            "request": request,
            "username": user.username,
            "lxd_settings": db.query(LXDSettings).first(),
            "vm_settings": db.query(VMDefaultSettings).first(),
            "connection_templates": db.query(ConnectionTemplate).first(),
            "password_error": error
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
            "message": "Certificate generated successfully"
        })
    except Exception:
        import logging
        logging.exception("Error generating certificate")
        return JSONResponse({"success": False, "message": "Failed to generate certificate"})


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
    # Validate username
    from core.validators import validate_username, validate_positive_integer

    is_valid, error = validate_username(username)
    if not is_valid:
        return RedirectResponse(
            url=f"/settings?vm_error={error}",
            status_code=303
        )

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


@router.post("/settings/container")
async def save_container_settings(
    request: Request,
    username: str = Form(...),
    cpu: int = Form(...),
    memory: int = Form(...),
    disk: int = Form(...),
    image_fingerprint: str = Form(""),
    image_alias: str = Form(""),
    image_description: str = Form(""),
    cloud_init: str = Form(""),
    db: Session = Depends(get_db)
):
    """Save default container settings"""
    # Validate username
    from core.validators import validate_username

    is_valid, error = validate_username(username)
    if not is_valid:
        return RedirectResponse(
            url=f"/settings?container_error={error}",
            status_code=303
        )

    # Validate cloud-init template if provided
    if cloud_init.strip():
        from services.cloud_init_service import validate_cloud_init_template
        is_valid, error_msg = validate_cloud_init_template(cloud_init)
        if not is_valid:
            return RedirectResponse(
                url=f"/settings?container_error={error_msg}",
                status_code=303
            )

    settings = db.query(ContainerDefaultSettings).first()

    if settings:
        settings.username = username
        settings.cpu = cpu
        settings.memory = memory
        settings.disk = disk
        settings.image_fingerprint = image_fingerprint if image_fingerprint else None
        settings.image_alias = image_alias if image_alias else None
        settings.image_description = image_description if image_description else None
        settings.cloud_init = cloud_init if cloud_init else None
    else:
        settings = ContainerDefaultSettings(
            username=username,
            cpu=cpu,
            memory=memory,
            disk=disk,
            image_fingerprint=image_fingerprint if image_fingerprint else None,
            image_alias=image_alias if image_alias else None,
            image_description=image_description if image_description else None,
            cloud_init=cloud_init if cloud_init else None
        )
        db.add(settings)

    db.commit()

    return RedirectResponse(url="/settings?container_success=Container defaults saved successfully", status_code=303)


@router.get("/settings/vm/template")
async def get_cloud_init_template():
    """Get the default cloud-init template"""
    from services.cloud_init_service import DEFAULT_CLOUD_INIT_TEMPLATE
    return JSONResponse({
        "success": True,
        "template": DEFAULT_CLOUD_INIT_TEMPLATE
    })


@router.get("/settings/vm/images")
async def get_available_images(
    db: Session = Depends(get_db),
    instance_type: str = "virtual-machine"
):
    """Get available LXD images for VM or container creation"""
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


@router.get("/api/lxd/profiles")
async def get_lxd_profiles(db: Session = Depends(get_db)):
    """Return all LXD profiles with parsed resource defaults."""
    import re
    from services.lxd_service import LXDService

    lxd_service = LXDService(db)
    lxd_service.get_client()

    if not lxd_service.is_connected():
        return JSONResponse({"success": False, "message": "LXD not connected"})

    def _parse_size_gib(value: str) -> int | None:
        """Convert LXD size string like '4GiB', '4096MiB', '2GB' to integer GiB."""
        if not value:
            return None
        value = value.strip()
        m = re.match(r'^(\d+(?:\.\d+)?)\s*(GiB|GB|MiB|MB|KiB|KB)?$', value, re.IGNORECASE)
        if not m:
            return None
        num, unit = float(m.group(1)), (m.group(2) or 'GiB').upper()
        if unit in ('MIB', 'MB'):
            return max(1, round(num / 1024))
        if unit in ('KIB', 'KB'):
            return max(1, round(num / (1024 * 1024)))
        return round(num)  # GiB / GB

    try:
        profiles = []
        for profile in lxd_service.client.profiles.all():
            cfg = profile.config or {}
            devices = profile.devices or {}

            # Parse CPU
            cpu_raw = cfg.get("limits.cpu")
            cpu = int(cpu_raw) if cpu_raw and cpu_raw.isdigit() else None

            # Parse memory
            memory = _parse_size_gib(cfg.get("limits.memory"))

            # Parse disk from root device
            root_dev = devices.get("root", {})
            disk = _parse_size_gib(root_dev.get("size"))

            # Cloud-init template presence
            has_cloud_init = bool(cfg.get("user.user-data"))

            profiles.append({
                "name": profile.name,
                "description": profile.description or "",
                "cpu": cpu,
                "memory": memory,
                "disk": disk,
                "has_cloud_init": has_cloud_init,
            })

        return JSONResponse({"success": True, "profiles": profiles})
    except Exception:
        import logging
        logging.exception("Error fetching LXD profiles")
        return JSONResponse({"success": False, "message": "Failed to fetch profiles"})


@router.get("/settings/connection-templates")
async def get_connection_templates(db: Session = Depends(get_db)):
    """Get connection templates (SSH config)"""
    from core.models import ConnectionTemplate
    from services.ssh_config_service import DEFAULT_SSH_CONFIG_TEMPLATE

    templates = db.query(ConnectionTemplate).first()

    return JSONResponse({
        "success": True,
        "ssh_config_template": templates.ssh_config_template if templates and templates.ssh_config_template else DEFAULT_SSH_CONFIG_TEMPLATE
    })


@router.post("/settings/connection-templates")
async def save_connection_templates(
    request: Request,
    ssh_config_template: str = Form(...),
    db: Session = Depends(get_db)
):
    """Save connection templates"""
    from core.models import ConnectionTemplate

    templates = db.query(ConnectionTemplate).first()

    if templates:
        templates.ssh_config_template = ssh_config_template
    else:
        templates = ConnectionTemplate(
            ssh_config_template=ssh_config_template
        )
        db.add(templates)

    db.commit()

    return RedirectResponse(url="/settings?templates_success=Connection templates saved successfully", status_code=303)


# ============================================================
# LXD Profile CRUD  (JSON API)
# ============================================================

def _lxd_service_connected(db) -> LXDService | None:
    """Return a connected LXDService or None."""
    svc = LXDService(db)
    svc.get_client()
    return svc if svc.is_connected() else None


def _parse_size_gib_shared(value: str):
    """Convert LXD size string (4GiB, 4096MiB …) to integer GiB. Returns None if unparseable."""
    import re
    if not value:
        return None
    m = re.match(r'^(\d+(?:\.\d+)?)\s*(GiB|GB|MiB|MB|KiB|KB)?$', value.strip(), re.IGNORECASE)
    if not m:
        return None
    num, unit = float(m.group(1)), (m.group(2) or 'GiB').upper()
    if unit in ('MIB', 'MB'):
        return max(1, round(num / 1024))
    if unit in ('KIB', 'KB'):
        return max(1, round(num / (1024 * 1024)))
    return round(num)


def _profile_to_dict(profile) -> dict:
    """Serialize a pylxd Profile object to a JSON-friendly dict."""
    cfg = profile.config or {}
    devices = profile.devices or {}
    root_dev = devices.get("root", {})
    cpu_raw = cfg.get("limits.cpu")
    return {
        "name": profile.name,
        "description": profile.description or "",
        "cpu": int(cpu_raw) if cpu_raw and cpu_raw.isdigit() else None,
        "memory": _parse_size_gib_shared(cfg.get("limits.memory")),
        "disk": _parse_size_gib_shared(root_dev.get("size")),
        "cloud_init": cfg.get("user.user-data") or "",
    }


@router.get("/api/lxd/profiles/{name}")
async def get_lxd_profile(name: str, db: Session = Depends(get_db)):
    """Return full details of a single LXD profile."""
    svc = _lxd_service_connected(db)
    if not svc:
        return JSONResponse({"success": False, "message": "LXD not connected"})
    try:
        profile = svc.client.profiles.get(name)
        return JSONResponse({"success": True, "profile": _profile_to_dict(profile)})
    except Exception:
        return JSONResponse({"success": False, "message": f"Profile '{name}' not found"}, status_code=404)


@router.post("/api/lxd/profiles")
async def create_lxd_profile(request: Request, db: Session = Depends(get_db)):
    """Create a new LXD profile."""
    svc = _lxd_service_connected(db)
    if not svc:
        return JSONResponse({"success": False, "message": "LXD not connected"})
    try:
        data = await request.json()
        name = (data.get("name") or "").strip()
        if not name:
            return JSONResponse({"success": False, "message": "Profile name is required"})

        config = {}
        devices = {}
        if data.get("cpu"):
            config["limits.cpu"] = str(int(data["cpu"]))
        if data.get("memory"):
            config["limits.memory"] = f"{int(data['memory'])}GiB"
        if data.get("cloud_init"):
            config["user.user-data"] = data["cloud_init"]
        if data.get("disk"):
            devices["root"] = {
                "type": "disk",
                "path": "/",
                "pool": "default",
                "size": f"{int(data['disk'])}GiB",
            }

        profile = svc.client.profiles.create(
            name=name,
            description=data.get("description", ""),
            config=config,
            devices=devices,
        )
        return JSONResponse({"success": True, "profile": _profile_to_dict(profile)})
    except Exception as exc:
        import logging
        logging.exception("Error creating LXD profile")
        return JSONResponse({"success": False, "message": str(exc)})


@router.put("/api/lxd/profiles/{name}")
async def update_lxd_profile(name: str, request: Request, db: Session = Depends(get_db)):
    """Update an existing LXD profile's resource limits and cloud-init."""
    svc = _lxd_service_connected(db)
    if not svc:
        return JSONResponse({"success": False, "message": "LXD not connected"})
    try:
        profile = svc.client.profiles.get(name)
        data = await request.json()

        cfg = dict(profile.config or {})
        devices = dict(profile.devices or {})

        # Update limits
        if data.get("cpu") is not None:
            cfg["limits.cpu"] = str(int(data["cpu"]))
        if data.get("memory") is not None:
            cfg["limits.memory"] = f"{int(data['memory'])}GiB"
        if "cloud_init" in data:
            if data["cloud_init"]:
                cfg["user.user-data"] = data["cloud_init"]
            else:
                cfg.pop("user.user-data", None)

        # Update root disk device
        if data.get("disk") is not None:
            root = dict(devices.get("root", {
                "type": "disk", "path": "/", "pool": "default"
            }))
            root["size"] = f"{int(data['disk'])}GiB"
            devices["root"] = root

        profile.config = cfg
        profile.devices = devices
        if "description" in data:
            profile.description = data["description"]
        profile.save()

        return JSONResponse({"success": True, "profile": _profile_to_dict(profile)})
    except Exception as exc:
        import logging
        logging.exception("Error updating LXD profile")
        return JSONResponse({"success": False, "message": str(exc)})


@router.delete("/api/lxd/profiles/{name}")
async def delete_lxd_profile(name: str, db: Session = Depends(get_db)):
    """Delete an LXD profile (cannot delete profiles in use)."""
    if name == "default":
        return JSONResponse({"success": False, "message": "Cannot delete the 'default' profile"})
    svc = _lxd_service_connected(db)
    if not svc:
        return JSONResponse({"success": False, "message": "LXD not connected"})
    try:
        profile = svc.client.profiles.get(name)
        profile.delete()
        return JSONResponse({"success": True, "message": f"Profile '{name}' deleted"})
    except Exception as exc:
        import logging
        logging.exception("Error deleting LXD profile")
        return JSONResponse({"success": False, "message": str(exc)})
