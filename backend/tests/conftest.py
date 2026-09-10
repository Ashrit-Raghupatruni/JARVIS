"""
JARVIS AI OS — Global Pytest Configuration & Fixtures.
"""

import sys
import os
import pytest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Set test environment flags
os.environ["CLAP_ENABLED"] = "false"
os.environ["SYNC_ENABLED"] = "false"
os.environ["DEBUG"] = "true"


@pytest.fixture(scope="session")
def project_root():
    return PROJECT_ROOT
