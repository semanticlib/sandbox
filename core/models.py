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


class VMDefaultSettings(Base):
    __tablename__ = "vm_default_settings"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, default="ubuntu")
    cpu = Column(Integer, default=2)
    memory = Column(Integer, default=4)
    disk = Column(Integer, default=20)
    swap = Column(Integer, default=2)
    image_fingerprint = Column(String, nullable=True)  # LXD image fingerprint
    image_alias = Column(String, nullable=True)  # Image alias (e.g., "ubuntu/24.04")
    image_description = Column(String, nullable=True)  # Human-readable description
    cloud_init = Column(Text, nullable=True)


class ConnectionTemplate(Base):
    __tablename__ = "connection_templates"

    id = Column(Integer, primary_key=True, index=True)
    ssh_config_template = Column(Text, nullable=True)  # SSH config template with placeholders
