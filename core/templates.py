"""Shared Jinja2 templates configuration"""
from fastapi.templating import Jinja2Templates
from jinja2 import filters

from core.config import settings


# Create a single shared templates instance
templates = Jinja2Templates(directory="templates")

# Configure shared filters and globals
templates.env.globals['app_title'] = settings.APP_TITLE
templates.env.filters['filesizeformat'] = filters.do_filesizeformat
