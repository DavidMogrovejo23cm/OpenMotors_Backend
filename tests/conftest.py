"""Entorno de pruebas separado de la base local y de servicios externos."""
import os
import tempfile

import pytest

_database_dir = tempfile.TemporaryDirectory(prefix="openmotors-tests-")
os.environ["DB_URL"] = f"sqlite:///{_database_dir.name}/tests.sqlite"
os.environ["DATABASE_URL"] = ""
os.environ["JWT_SECRET"] = "openmotors-tests-secret-with-at-least-32-chars"
os.environ["SEED_DEMO_DATA"] = "true"
os.environ["KEEPALIVE_ENABLED"] = "false"
for key in ("SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY",
            "BREVO_API_KEY", "SENDGRID_API_KEY", "RESEND_API_KEY", "MAIL_USERNAME", "MAIL_PASSWORD"):
    os.environ[key] = ""

# Importar antes de los módulos de pruebas que usan nombres antiguos de BD.
from app.core.database import engine  # noqa: E402


@pytest.fixture(autouse=True)
def no_external_email(monkeypatch):
    from app.shared.email_service import email_service
    monkeypatch.setattr(email_service, "enviar", lambda *args, **kwargs: True)


def pytest_sessionfinish(session, exitstatus):
    engine.dispose()
    _database_dir.cleanup()
