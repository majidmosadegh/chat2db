"""Security regression tests for encryption fail-closed behavior and SQL guards."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

BACKEND_ROOT = Path(__file__).resolve().parents[2]
SECURITY_PATH = BACKEND_ROOT / "db" / "security.py"


def _load_security_module():
    """Load db.security without importing package side effects."""
    spec = importlib.util.spec_from_file_location("chat2db_security_under_test", SECURITY_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load security module for tests")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


security = _load_security_module()
SQLSecurityError = security.SQLSecurityError
decrypt_password = security.decrypt_password
validate_read_only_sql = security.validate_read_only_sql
validate_sql = security.validate_sql


@pytest.fixture()
def fernet_key(monkeypatch: pytest.MonkeyPatch) -> str:
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("CHAT2DB_ENCRYPTION_KEY", key)
    return key


def test_decrypt_password_requires_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CHAT2DB_ENCRYPTION_KEY", raising=False)
    with pytest.raises(RuntimeError, match="CHAT2DB_ENCRYPTION_KEY"):
        decrypt_password("not-a-real-token")


def test_decrypt_password_round_trip(fernet_key: str) -> None:
    token = Fernet(fernet_key.encode()).encrypt(b"secret-value").decode()
    assert decrypt_password(token) == "secret-value"


def test_decrypt_password_fails_closed_on_bad_token(fernet_key: str) -> None:
    with pytest.raises(ValueError, match="Unable to decrypt"):
        decrypt_password("definitely-not-valid-fernet-token")


def test_validate_sql_blocks_destructive_and_information_schema() -> None:
    validate_sql("SELECT 1")
    with pytest.raises(SQLSecurityError):
        validate_sql("DELETE FROM users")
    with pytest.raises(SQLSecurityError):
        validate_sql("SELECT * FROM information_schema.tables")


def test_validate_read_only_sql_allows_information_schema_but_blocks_writes() -> None:
    validate_read_only_sql(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
    )
    with pytest.raises(SQLSecurityError):
        validate_read_only_sql("DROP TABLE users")
    with pytest.raises(SQLSecurityError):
        validate_read_only_sql("SELECT 1; SELECT 2;")


def test_database_module_requires_encryption_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CHAT2DB_ENCRYPTION_KEY", raising=False)
    # Execute only the encryption bootstrap portion of database.py to avoid
    # importing the full FastAPI application graph.
    source = (BACKEND_ROOT / "api" / "database.py").read_text(encoding="utf-8")
    bootstrap = []
    for line in source.splitlines():
        bootstrap.append(line)
        if line.strip() == "router = APIRouter()":
            break
    ns: dict = {"__name__": "api.database_bootstrap_test"}
    with pytest.raises(RuntimeError, match="CHAT2DB_ENCRYPTION_KEY"):
        exec(compile("\n".join(bootstrap), "database.py", "exec"), ns, ns)
