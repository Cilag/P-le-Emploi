import sys
import os
import types

# Make packages installed to /tmp/py_pkgs available (system site-packages is read-only)
sys.path.insert(0, "/tmp/py_pkgs")

# backend root → enables `from app.xxx` imports
_here = os.path.dirname(__file__)
_backend = os.path.abspath(os.path.join(_here, ".."))
sys.path.insert(0, os.path.join(_backend, "app"))  # `from workers_client import …`
sys.path.insert(0, _backend)                        # `from app.xxx import …`

# Override settings BEFORE pydantic-settings reads env at first Settings() instantiation.
# Using SQLite+aiosqlite so the FastAPI lifespan can run create_all without a real PG server.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:////tmp/test_pe.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("CV_AUDIT_DEFAULT_RECIPIENT", "test@example.com")

# ---------------------------------------------------------------------------
# Scaffold-bug shim: backend/app/api/routes/cv.py imports from `app.core.config`
# but the correct module is `app.config`.  Inject a compatible fake so that
# `from app.main import app` succeeds during test collection.
# TODO (Web Lead): fix cv.py → replace `from app.core.config import settings`
#                  with `from app.config import settings` and `settings.UPLOAD_DIR`
#                  with `settings.upload_dir`.
# ---------------------------------------------------------------------------

class _CvShimSettings:
    UPLOAD_DIR = "/tmp/test_uploads"
    upload_dir = "/tmp/test_uploads"


_app_core = types.ModuleType("app.core")
_app_core_config = types.ModuleType("app.core.config")
_app_core_config.settings = _CvShimSettings()
sys.modules.setdefault("app.core", _app_core)
sys.modules.setdefault("app.core.config", _app_core_config)
