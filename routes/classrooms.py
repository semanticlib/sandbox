"""Classrooms page routes - manages Classrooms and LXD Profiles"""
from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import AdminUser, LXDSettings, Classroom
from core.config import settings
from services.lxd_service import LXDService

templates = Jinja2Templates(directory="templates")
templates.env.globals['app_title'] = settings.APP_TITLE

router = APIRouter()


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


@router.get("/classrooms", response_class=HTMLResponse)
async def classrooms_page(
    request: Request,
    user: AdminUser = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """Classrooms management page"""
    return templates.TemplateResponse("admin/classrooms.html", {
        "request": request,
        "username": user.username,
    })

# ============================================================
# Cloud-init template and SSH config template routes (API)
# ============================================================

@router.get("/classrooms/cloud-init/template")
async def get_default_cloud_init_template(template_type: str = "container"):
    """Return the default cloud-init template text for VM or Container."""
    from services.cloud_init_service import DEFAULT_CLOUD_INIT_TEMPLATE_VM, DEFAULT_CLOUD_INIT_TEMPLATE_CONTAINER
    
    if template_type == "container":
        template = DEFAULT_CLOUD_INIT_TEMPLATE_CONTAINER
    else:
        template = DEFAULT_CLOUD_INIT_TEMPLATE_VM
    
    return JSONResponse({"success": True, "template": template})


@router.get("/classrooms/connection-templates")
async def get_connection_templates():
    """Get default SSH config template"""
    from services.ssh_config_service import DEFAULT_SSH_CONFIG_TEMPLATE
    return JSONResponse({
        "success": True,
        "ssh_config_template": DEFAULT_SSH_CONFIG_TEMPLATE
    })


# ============================================================
# Classroom CRUD (JSON API) - moved from settings.py
# ============================================================

@router.get("/api/classrooms")
async def get_classrooms(db: Session = Depends(get_db)):
    """Return all classrooms."""
    try:
        classrooms = db.query(Classroom).all()
        return JSONResponse({
            "success": True,
            "classrooms": [
                {
                    "id": c.id,
                    "name": c.name,
                    "username": c.username,
                    "image_type": c.image_type,
                    "lxd_profile": c.lxd_profile,
                    "image_fingerprint": c.image_fingerprint,
                    "image_alias": c.image_alias,
                    "image_description": c.image_description,
                    "ssh_config_template": c.ssh_config_template or "",
                }
                for c in classrooms
            ]
        })
    except Exception as exc:
        import logging
        logging.exception("Error fetching classrooms")
        return JSONResponse({"success": False, "message": str(exc)})


@router.get("/api/classrooms/{classroom_id}")
async def get_classroom(classroom_id: int, db: Session = Depends(get_db)):
    """Return a single classroom by ID."""
    try:
        classroom = db.query(Classroom).filter(Classroom.id == classroom_id).first()
        if not classroom:
            return JSONResponse({"success": False, "message": "Classroom not found"}, status_code=404)
        return JSONResponse({
            "success": True,
            "classroom": {
                "id": classroom.id,
                "name": classroom.name,
                "username": classroom.username,
                "image_type": classroom.image_type,
                "lxd_profile": classroom.lxd_profile,
                "image_fingerprint": classroom.image_fingerprint,
                "image_alias": classroom.image_alias,
                "image_description": classroom.image_description,
                "ssh_config_template": classroom.ssh_config_template or "",
            }
        })
    except Exception as exc:
        import logging
        logging.exception("Error fetching classroom")
        return JSONResponse({"success": False, "message": str(exc)})


@router.post("/api/classrooms")
async def create_classroom(request: Request, db: Session = Depends(get_db)):
    """Create a new classroom."""
    try:
        data = await request.json()
        name = (data.get("name") or "").strip()
        if not name:
            return JSONResponse({"success": False, "message": "Classroom name is required"})

        username = (data.get("username") or "").strip()
        if not username:
            return JSONResponse({"success": False, "message": "Default username is required"})

        # Check if name already exists
        existing = db.query(Classroom).filter(Classroom.name == name).first()
        if existing:
            return JSONResponse({"success": False, "message": "Classroom name already exists"})

        classroom = Classroom(
            name=name,
            username=username,
            image_type=data.get("image_type", "container"),
            lxd_profile=data.get("lxd_profile"),
            image_fingerprint=data.get("image_fingerprint"),
            image_alias=data.get("image_alias"),
            image_description=data.get("image_description"),
            ssh_config_template=data.get("ssh_config_template"),
        )
        db.add(classroom)
        db.commit()
        db.refresh(classroom)

        return JSONResponse({
            "success": True,
            "classroom": {
                "id": classroom.id,
                "name": classroom.name,
                "username": classroom.username,
                "image_type": classroom.image_type,
                "lxd_profile": classroom.lxd_profile,
                "image_fingerprint": classroom.image_fingerprint,
                "image_alias": classroom.image_alias,
                "image_description": classroom.image_description,
                "ssh_config_template": classroom.ssh_config_template or "",
            }
        })
    except Exception as exc:
        import logging
        logging.exception("Error creating classroom")
        return JSONResponse({"success": False, "message": str(exc)})


@router.put("/api/classrooms/{classroom_id}")
async def update_classroom(classroom_id: int, request: Request, db: Session = Depends(get_db)):
    """Update an existing classroom."""
    try:
        classroom = db.query(Classroom).filter(Classroom.id == classroom_id).first()
        if not classroom:
            return JSONResponse({"success": False, "message": "Classroom not found"}, status_code=404)

        data = await request.json()

        # Check if name is being changed and if it already exists
        new_name = data.get("name", classroom.name).strip()
        if new_name != classroom.name:
            existing = db.query(Classroom).filter(Classroom.name == new_name).first()
            if existing:
                return JSONResponse({"success": False, "message": "Classroom name already exists"})
            classroom.name = new_name

        new_username = (data.get("username") or "").strip()
        if not new_username:
            return JSONResponse({"success": False, "message": "Default username is required"})
        classroom.username = new_username

        classroom.image_type = data.get("image_type", classroom.image_type)
        classroom.lxd_profile = data.get("lxd_profile")
        classroom.image_fingerprint = data.get("image_fingerprint")
        classroom.image_alias = data.get("image_alias")
        classroom.image_description = data.get("image_description")
        classroom.ssh_config_template = data.get("ssh_config_template")

        db.commit()
        db.refresh(classroom)

        return JSONResponse({
            "success": True,
            "classroom": {
                "id": classroom.id,
                "name": classroom.name,
                "username": classroom.username,
                "image_type": classroom.image_type,
                "lxd_profile": classroom.lxd_profile,
                "image_fingerprint": classroom.image_fingerprint,
                "image_alias": classroom.image_alias,
                "image_description": classroom.image_description,
                "ssh_config_template": classroom.ssh_config_template or "",
            }
        })
    except Exception as exc:
        import logging
        logging.exception("Error updating classroom")
        return JSONResponse({"success": False, "message": str(exc)})


@router.delete("/api/classrooms/{classroom_id}")
async def delete_classroom(classroom_id: int, db: Session = Depends(get_db)):
    """Delete a classroom."""
    try:
        classroom = db.query(Classroom).filter(Classroom.id == classroom_id).first()
        if not classroom:
            return JSONResponse({"success": False, "message": "Classroom not found"}, status_code=404)

        db.delete(classroom)
        db.commit()

        return JSONResponse({"success": True, "message": f"Classroom '{classroom.name}' deleted"})
    except Exception as exc:
        import logging
        logging.exception("Error deleting classroom")
        return JSONResponse({"success": False, "message": str(exc)})


# ============================================================
# LXD Profile CRUD (JSON API) - moved from settings.py
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
    
    # Check if profile is used by any classroom
    from core.models import Classroom
    using_classrooms = db.query(Classroom).filter(Classroom.lxd_profile == name).all()
    if using_classrooms:
        classroom_names = ", ".join([c.name for c in using_classrooms])
        return JSONResponse({
            "success": False,
            "message": f"Cannot delete profile '{name}': It is used by {len(using_classrooms)} classroom(s): {classroom_names}. Please update the classroom(s) to use a different profile first."
        })
    
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
