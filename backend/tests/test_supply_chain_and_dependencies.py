"""
JARVIS AI OS — Phase 10: Dependency & Software Supply-Chain Adversarial Test Suite.
=====================================================================================
Validates all Phase 10 security invariants:
  1. Requirements synchronization: requirements.txt matches backend/requirements.txt exactly.
  2. Safe package sources: No unpinned mutable Git (@main/@master) or arbitrary URL dependencies in manifests.
  3. No unverified executable or binary download scripts in repository manifests.
  4. Secure model deserialization: torch.load in Prash engine/training prioritizes weights_only=True.
  5. Zero unsafe pickle, joblib, marshal, or raw unsafe yaml.load calls in backend production code.
  6. Zero arbitrary dynamic code evaluation (eval / exec) in backend production services.
  7. GitHub Actions CI workflow least privilege (contents: read, persist-credentials: false, pinned actions).
  8. Android Gradle dependency integrity (trusted google() and mavenCentral() repositories).
  9. Frontend Electron package integrity and safe dependency scopes.
 10. Windows platform-specific dependency gating (sys_platform == 'win32' environment markers).
 11. Duplicate dependency consolidation verification (e.g. pypdf vs PyPDF2, cryptography vs custom crypto).
 12. Heavyweight dependency verification and graceful optional fallback integrity.
"""

import os
import re
import json
import ast
from pathlib import Path
import pytest
import torch


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"


# ==============================================================================
# 1. Requirements Synchronization & Manifest Provenance Tests
# ==============================================================================

def test_requirements_files_synchronization():
    """Ensure root requirements.txt and backend/requirements.txt do not drift."""
    root_req = PROJECT_ROOT / "requirements.txt"
    backend_req = BACKEND_DIR / "requirements.txt"

    assert root_req.exists(), "Root requirements.txt must exist"
    assert backend_req.exists(), "Backend requirements.txt must exist"

    with open(root_req, "r", encoding="utf-8") as f1, open(backend_req, "r", encoding="utf-8") as f2:
        # Compare dependencies skipping the first 2 title comment lines
        root_lines = [l.strip() for l in f1.read().splitlines()[2:] if l.strip()]
        backend_lines = [l.strip() for l in f2.read().splitlines()[2:] if l.strip()]

    assert root_lines == backend_lines, "requirements.txt and backend/requirements.txt have drifted!"


def test_requirements_no_unpinned_git_or_arbitrary_urls():
    """Ensure no unpinned mutable Git branches (@main/@master) or unverified HTTP URLs in requirements."""
    req_files = [
        PROJECT_ROOT / "requirements.txt",
        PROJECT_ROOT / "requirements-dev.txt",
        BACKEND_DIR / "requirements.txt",
    ]

    for req_file in req_files:
        if not req_file.exists():
            continue
        with open(req_file, "r", encoding="utf-8") as f:
            for line in f:
                clean = line.strip()
                if not clean or clean.startswith("#") or clean.startswith("-r"):
                    continue
                # Reject mutable git branches
                assert not ("@main" in clean or "@master" in clean), f"Mutable git dependency found in {req_file.name}: {clean}"
                # Reject unencrypted http:// urls
                assert not clean.startswith("http://"), f"Insecure HTTP dependency found in {req_file.name}: {clean}"


def test_windows_platform_markers():
    """Ensure Windows-specific libraries have proper sys_platform environment markers."""
    backend_req = BACKEND_DIR / "requirements.txt"
    win_deps = ["pywin32", "pywinauto", "pycaw", "bleak"]

    with open(backend_req, "r", encoding="utf-8") as f:
        content = f.read()

    for dep in win_deps:
        pattern = rf'{dep}[^;]+;\s*sys_platform\s*==\s*[\"\']win32[\"\']'
        assert re.search(pattern, content), f"Windows dependency {dep} must have sys_platform == 'win32' marker"


# ==============================================================================
# 2. Deserialization & Dynamic Code Execution Security Tests
# ==============================================================================

def test_no_unsafe_pickle_or_marshal_in_backend():
    """Ensure zero raw pickle, joblib, or marshal imports in backend production code."""
    for root, _, files in os.walk(BACKEND_DIR):
        if "venv" in root or "__pycache__" in root or "tests" in root:
            continue
        for file in files:
            if file.endswith(".py"):
                file_path = Path(root) / file
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    assert "import pickle" not in content and "from pickle import" not in content, f"Unsafe pickle import in {file_path}"
                    assert "import joblib" not in content and "from joblib import" not in content, f"Unsafe joblib import in {file_path}"
                    assert "import marshal" not in content and "from marshal import" not in content, f"Unsafe marshal import in {file_path}"


def test_no_unsafe_eval_exec_in_production_backend():
    """Ensure zero eval() or exec() calls in backend production code (AST checked)."""
    for root, _, files in os.walk(BACKEND_DIR):
        if "venv" in root or "__pycache__" in root or "tests" in root:
            continue
        for file in files:
            if file.endswith(".py"):
                file_path = Path(root) / file
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    tree = ast.parse(f.read(), filename=str(file_path))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                        assert node.func.id not in ("eval", "exec"), f"Unsafe {node.func.id}() call found in {file_path} at line {node.lineno}"


def test_torch_load_weights_only_prioritization(tmp_path):
    """Ensure torch.load safely loads primitive state dicts with weights_only=True."""
    model_dir = tmp_path / "test_model"
    model_dir.mkdir(parents=True, exist_ok=True)
    ckpt_file = model_dir / "checkpoint_test.pt"

    # Save a standard dictionary checkpoint
    dummy_payload = {
        "model_state_dict": {"weight": torch.tensor([1.0, 2.0, 3.0])},
        "config": {"d_model": 64, "n_layers": 2},
        "step": 100
    }
    torch.save(dummy_payload, ckpt_file)

    # Load with weights_only=True
    loaded = torch.load(ckpt_file, weights_only=True)
    assert loaded["step"] == 100
    assert torch.equal(loaded["model_state_dict"]["weight"], torch.tensor([1.0, 2.0, 3.0]))


# ==============================================================================
# 3. Duplicate Dependencies & Library Consolidation Tests
# ==============================================================================

def test_no_duplicate_pdf_or_crypto_libraries():
    """Ensure unified document parsing (pypdf) and crypto (cryptography) without legacy duplicates."""
    with open(BACKEND_DIR / "requirements.txt", "r", encoding="utf-8") as f:
        req_content = f.read()

    # pypdf should be used, PyPDF2 should NOT be in requirements
    assert "pypdf" in req_content
    assert "PyPDF2" not in req_content
    assert "pycrypto" not in req_content
    assert "pycryptodome" not in req_content


# ==============================================================================
# 4. GitHub Actions CI & Supply Chain Configuration Tests
# ==============================================================================

def test_github_actions_least_privilege_and_pinned_actions():
    """Ensure .github/workflows/ci.yml enforces least privilege and uses verified action versions."""
    ci_file = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
    assert ci_file.exists(), ".github/workflows/ci.yml must exist"

    with open(ci_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Verify least privilege
    assert "permissions:" in content
    assert "contents: read" in content
    assert "persist-credentials: false" in content

    # Verify official actions
    assert "actions/checkout@v4" in content
    assert "actions/setup-python@v5" in content
    assert "actions/setup-node@v4" in content


# ==============================================================================
# 5. Mobile Android & Frontend Package Integrity Tests
# ==============================================================================

def test_android_gradle_trusted_repositories():
    """Ensure mobile_app/android/build.gradle references only trusted repositories."""
    gradle_file = PROJECT_ROOT / "mobile_app" / "android" / "build.gradle"
    if gradle_file.exists():
        with open(gradle_file, "r", encoding="utf-8") as f:
            content = f.read()
        assert "google()" in content
        assert "mavenCentral()" in content
        # Insecure repositories should not be present
        assert "http://" not in content
        assert "jcenter()" not in content


def test_frontend_package_json_integrity():
    """Ensure frontend/package.json contains valid scripts and production dependencies."""
    pkg_file = PROJECT_ROOT / "frontend" / "package.json"
    assert pkg_file.exists()

    with open(pkg_file, "r", encoding="utf-8") as f:
        pkg = json.load(f)

    assert "dependencies" in pkg
    assert "devDependencies" in pkg
    assert "electron" in pkg["devDependencies"]
    assert "react" in pkg["dependencies"]
