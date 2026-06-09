"""
DocuMind 2.0 — Test Configuration
Shared fixtures and test setup.
"""

import os
import sys

# Ensure the backend app is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Override database to use in-memory SQLite for tests
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_documind.db"
os.environ["SECRET_KEY"] = "test-secret-key-for-unit-tests-only-min-32-chars"
os.environ["GROQ_API_KEY"] = "test-key"
os.environ["UPLOAD_DIR"] = "/tmp/documind_test_uploads"
