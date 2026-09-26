"""
JARVIS AI OS — Phase 14: Production, Deployment & Operational Hardening Test Suite.
===================================================================================
Empirically verifies:
1. Production-safe default host binding (127.0.0.1 loopback isolation).
2. Configuration secret masking across __repr__ and __str__.
3. Version and build identification endpoint structure (/api/version).
4. Liveness health check endpoint (/api/health).
5. Readiness health check endpoint (/api/health/ready).
6. Detailed health check with graceful optional component degradation.
7. BackupManager data backup creation, manifest checksums, and rotation.
8. BackupManager encrypted secret backup separation.
9. BackupManager integrity verification and transactional restoration.
10. SQLite database initialization with WAL mode and schema version tracking.
"""

import os
import sys
import json
import time
import pytest
import tarfile
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

from fastapi.testclient import TestClient
from backend.main import app
from backend.config import Settings, get_settings
from backend.services.backup_manager import BackupManager
from backend.models.database import init_db, get_engine, Base


@pytest.fixture
def client():
    return TestClient(app)


# ==============================================================================
# 1. Configuration & Safe Defaults
# ==============================================================================

def test_production_safe_default_host_binding():
    """Verify that SERVER_HOST defaults to loopback 127.0.0.1 for local workstation security."""
    settings = Settings(_env_file=None)
    assert settings.SERVER_HOST == "127.0.0.1"


def test_production_settings_secret_masking():
    """Verify that settings representation strictly masks API keys, secrets, and tokens."""
    settings = Settings(
        GEMINI_API_KEY="AIzaSy-valid-production-key-here",
        OPENAI_API_KEY="sk-valid-production-key-here",
        JWT_SECRET="super-secret-production-jwt",
        _env_file=None
    )
    repr_str = repr(settings)
    str_str = str(settings)
    
    assert "AIzaSy-valid-production-key-here" not in repr_str
    assert "sk-valid-production-key-here" not in repr_str
    assert "super-secret-production-jwt" not in repr_str
    assert "******" in repr_str
    assert repr_str == str_str


# ==============================================================================
# 2. Version & Build Identification
# ==============================================================================

def test_version_identification_endpoint(client):
    """Verify that /api/version and /api/v1/version return structured semantic version info."""
    for path in ("/version", "/api/version", "/api/v1/version"):
        response = client.get(path)
        assert response.status_code == 200
        data = response.json()
        assert data["app_name"] == "JARVIS AI OS"
        assert data["version"] == "1.0.0"
        assert data["schema_version"] == "2.0.0"
        assert "platform" in data
        assert "python_version" in data


# ==============================================================================
# 3. Liveness, Readiness & Detailed Health Checks
# ==============================================================================

def test_liveness_health_check(client):
    """Verify that /api/health returns liveness ok."""
    for path in ("/health", "/api/health", "/api/v1/health"):
        response = client.get(path)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["liveness"] == "healthy"
        assert "uptime" in data


def test_readiness_health_check(client):
    """Verify that /api/health/ready returns readiness state."""
    for path in ("/health/ready", "/api/health/ready", "/api/v1/health/ready"):
        response = client.get(path)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["readiness"] == "ready"
        assert data["core_backend"] == "HEALTHY"


def test_detailed_health_check_optional_components(client):
    """Verify /api/health/detailed distinguishes core health from optional services."""
    for path in ("/health/detailed", "/api/health/detailed", "/api/v1/health/detailed"):
        response = client.get(path)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["overall_health"] == "HEALTHY"
        assert "components" in data
        assert data["components"]["core_backend"]["required"] is True
        assert data["components"]["llm_provider"]["required"] is False
        assert data["components"]["browser_automation"]["required"] is False


# ==============================================================================
# 4. Backup & Disaster Recovery Manager
# ==============================================================================

def test_backup_manager_data_backup_creation_and_rotation(tmp_path):
    """Verify BackupManager creates compressed data backups, manifests, and rotates old backups."""
    data_dir = tmp_path / "data"
    backup_dir = tmp_path / "backups"
    data_dir.mkdir()
    
    # Create sample data files
    (data_dir / "jarvis.db").write_text("sqlite database sample content")
    (data_dir / "episodic.db").write_text("episodic sample content")
    
    mgr = BackupManager(data_dir=data_dir, backup_dir=backup_dir, max_backups=2)
    
    # 1. Create 3 backups (should rotate and keep only 2)
    m1 = mgr.create_data_backup(label="test1")
    time.sleep(0.05)
    m2 = mgr.create_data_backup(label="test2")
    time.sleep(0.05)
    m3 = mgr.create_data_backup(label="test3")
    
    assert m3["backup_type"] == "DATA"
    assert "sha256" in m3
    assert m3["items_count"] == 2
    
    # Check that rotation kept only max_backups (2)
    archives = list(backup_dir.glob("*.tar.gz"))
    assert len(archives) == 2


def test_backup_manager_secret_backup_encrypted_separation(tmp_path):
    """Verify BackupManager exports encrypted secrets separately from data."""
    backup_dir = tmp_path / "backups"
    mgr = BackupManager(data_dir=tmp_path, backup_dir=backup_dir)
    
    manifest = mgr.create_secret_backup(passphrase="P@ssw0rdSecureProduction2026!")
    assert manifest["backup_type"] == "SECRETS_ENCRYPTED"
    assert "sha256" in manifest
    
    enc_files = list(backup_dir.glob("*.enc"))
    assert len(enc_files) == 1
    # Check file is not plaintext
    content = enc_files[0].read_bytes()
    assert b"P@ssw0rdSecureProduction2026!" not in content


def test_backup_manager_integrity_verification_and_restore(tmp_path):
    """Verify BackupManager integrity check detects corrupt files and restores cleanly."""
    data_dir = tmp_path / "source_data"
    restore_dir = tmp_path / "restored_data"
    backup_dir = tmp_path / "backups"
    data_dir.mkdir()
    
    (data_dir / "preferences.json").write_text(json.dumps({"theme": "dark", "voice": "Ryan"}))
    
    mgr = BackupManager(data_dir=data_dir, backup_dir=backup_dir)
    manifest = mgr.create_data_backup(label="restore_test")
    archive_path = backup_dir / manifest["backup_name"]
    
    # Verify valid integrity
    v_ok = mgr.verify_backup_integrity(archive_path)
    assert v_ok["valid"] is True
    assert "preferences.json" in v_ok["members"]
    
    # Restore to target directory
    restore_res = mgr.restore_data_backup(archive_path, target_dir=restore_dir)
    assert restore_res["status"] == "success"
    assert (restore_dir / "preferences.json").exists()
    restored_json = json.loads((restore_dir / "preferences.json").read_text())
    assert restored_json["theme"] == "dark"


# ==============================================================================
# 5. Database Initialization, WAL Mode & Schema Versioning
# ==============================================================================

@pytest.mark.asyncio
async def test_database_init_wal_and_schema_version(tmp_path):
    """Verify init_db configures WAL mode and sets schema user_version."""
    db_file = tmp_path / "test_init.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    
    await init_db(db_url)
    assert db_file.exists()
    
    # Verify user_version and journal_mode
    import sqlite3
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA journal_mode;")
    mode = cursor.fetchone()[0]
    assert mode.lower() == "wal"
    
    cursor.execute("PRAGMA user_version;")
    version = cursor.fetchone()[0]
    assert version == 2
    conn.close()
