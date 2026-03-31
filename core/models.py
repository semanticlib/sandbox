from sqlalchemy import Column, Integer, String, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_first_login = Column(Boolean, default=True)


class LXDSettings(Base):
    __tablename__ = "lxd_settings"

    id = Column(Integer, primary_key=True, index=True)
    use_socket = Column(Boolean, default=False)
    server_url = Column(String, nullable=True)
    client_cert = Column(Text, nullable=True)
    client_key = Column(Text, nullable=True)
    verify_ssl = Column(Boolean, default=True)


class Classroom(Base):
    """Classroom configuration - combines VM/Container defaults, image selection, and SSH config"""
    __tablename__ = "classrooms"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)  # Classroom name (e.g., "CS101", "Data Science Lab")
    username = Column(String, default="ubuntu")  # Default username for instances
    image_type = Column(String, default="container")  # "container" or "virtual-machine"
    cloud_init = Column(Text, nullable=True)  # Cloud-init template for instance initialization
    local_forwards = Column(Text, nullable=True)  # SSH local port forwards (one per line: sourcePort:localhost:targetPort)
    image_fingerprint = Column(String, nullable=True)  # LXD image fingerprint
    image_alias = Column(String, nullable=True)  # Image alias (e.g., "ubuntu/24.04")
    image_description = Column(String, nullable=True)  # Human-readable description
