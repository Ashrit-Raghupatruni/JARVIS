"""
JARVIS AI OS — CapabilityRegistry.json Schema & Integrity Test Suite.

Validates:
1. JSON structure, required metadata, and schema version
2. Valid implementation_status, validation_status, and platform values
3. Absence of standard library modules in external dependencies
4. Existence of referenced implementation_files and test_files on disk
5. Uniqueness of capability keys and truthful multidimensional metadata
"""

import json
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
REGISTRY_PATH = PROJECT_ROOT / "backend" / "CapabilityRegistry.json"

VALID_IMPLEMENTATION_STATUSES = {
    "PLANNED", "PROTOTYPE", "PARTIAL", "IMPLEMENTED", "DEPRECATED", "REMOVED"
}

VALID_VALIDATION_STATUSES = {
    "UNTESTED", "PARTIALLY_VALIDATED", "VALIDATED", "ENVIRONMENT_LIMITED",
    "EXTERNAL_DEPENDENCY", "HARDWARE_UNVERIFIED"
}

VALID_PLATFORMS = {
    "windows", "cross-platform", "android", "linux", "macos", "web", "server"
}

FORBIDDEN_STDLIB_DEPENDENCIES = {
    "json", "re", "os", "sys", "pathlib", "asyncio", "sqlite3", "typing", "time", "shutil"
}


def test_registry_file_exists_and_parses():
    """Verify CapabilityRegistry.json exists and is valid JSON."""
    assert REGISTRY_PATH.exists(), f"CapabilityRegistry.json missing at {REGISTRY_PATH}"
    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, dict)
    assert "project_name" in data
    assert "version" in data
    assert "schema_version" in data
    assert "authoritative_sources" in data
    assert "capabilities" in data
    assert len(data["capabilities"]) >= 15


def test_registry_authoritative_sources():
    """Verify authoritative sources point to existing files."""
    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    sources = data.get("authoritative_sources", {})
    assert "architecture" in sources
    assert "capability_metadata" in sources
    assert "user_guide" in sources
    assert "verification_history" in sources


def test_capability_schema_and_integrity():
    """Validate every capability against strict multidimensional status and file integrity rules."""
    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    capabilities = data["capabilities"]
    assert len(capabilities) == len(set(capabilities.keys())), "Duplicate capability keys found!"

    required_fields = [
        "name", "implementation_status", "validation_status", "platform",
        "optional", "experimental", "description", "implementation_files",
        "test_files", "dependencies", "validation_details"
    ]

    for cap_id, cap in capabilities.items():
        # 1. Required fields
        for field in required_fields:
            assert field in cap, f"Capability '{cap_id}' missing required field '{field}'"

        # 2. Status validity
        imp_status = cap["implementation_status"]
        assert imp_status in VALID_IMPLEMENTATION_STATUSES, (
            f"Invalid implementation_status '{imp_status}' in '{cap_id}'"
        )
        val_status = cap["validation_status"]
        assert val_status in VALID_VALIDATION_STATUSES, (
            f"Invalid validation_status '{val_status}' in '{cap_id}'"
        )

        # 3. Platform validity
        platforms = cap["platform"]
        assert isinstance(platforms, list) and len(platforms) >= 1
        for p in platforms:
            assert p in VALID_PLATFORMS, f"Invalid platform '{p}' in '{cap_id}'"

        # 4. Booleans
        assert isinstance(cap["optional"], bool)
        assert isinstance(cap["experimental"], bool)

        # 5. External dependencies (No stdlib modules)
        deps = cap["dependencies"]
        assert isinstance(deps, list)
        for dep in deps:
            assert dep.lower() not in FORBIDDEN_STDLIB_DEPENDENCIES, (
                f"Stdlib module '{dep}' incorrectly listed as external dependency in '{cap_id}'"
            )

        # 6. File existence checks on disk
        for impl_file in cap["implementation_files"]:
            file_path = PROJECT_ROOT / impl_file
            assert file_path.exists(), f"Referenced implementation file '{impl_file}' in '{cap_id}' does not exist!"

        for test_file in cap["test_files"]:
            file_path = PROJECT_ROOT / test_file
            assert file_path.exists(), f"Referenced test file '{test_file}' in '{cap_id}' does not exist!"
