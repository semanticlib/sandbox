from sqlalchemy import Column, Integer, String, Boolean, Text
from database import Base


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
