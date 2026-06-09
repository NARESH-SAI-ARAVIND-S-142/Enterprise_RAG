"""
DocuMind 2.0 — Auth Tests
Tests for user registration, login, token management, and isolation.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database import create_all_tables, drop_all_tables, engine


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Create tables before each test, drop after."""
    await create_all_tables()
    yield
    await drop_all_tables()


@pytest_asyncio.fixture
async def client():
    """Async HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_register_new_user(client: AsyncClient):
    """Registration should return JWT tokens and user data."""
    response = await client.post("/auth/register", json={
        "email": "test@example.com",
        "password": "securepass123",
        "full_name": "Test User",
    })
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user"]["email"] == "test@example.com"
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    """Registering with an existing email should return 409."""
    await client.post("/auth/register", json={
        "email": "dup@example.com", "password": "securepass123",
    })
    response = await client.post("/auth/register", json={
        "email": "dup@example.com", "password": "otherpass123",
    })
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_login_valid_credentials(client: AsyncClient):
    """Login with correct credentials should return tokens."""
    await client.post("/auth/register", json={
        "email": "login@example.com", "password": "securepass123",
    })
    response = await client.post("/auth/login", json={
        "email": "login@example.com", "password": "securepass123",
    })
    assert response.status_code == 200
    assert "access_token" in response.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    """Login with wrong password should return 401."""
    await client.post("/auth/register", json={
        "email": "wrong@example.com", "password": "securepass123",
    })
    response = await client.post("/auth/login", json={
        "email": "wrong@example.com", "password": "wrongpass",
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_authenticated(client: AsyncClient):
    """GET /auth/me with valid token should return user data."""
    reg = await client.post("/auth/register", json={
        "email": "me@example.com", "password": "securepass123",
    })
    token = reg.json()["access_token"]

    response = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["email"] == "me@example.com"


@pytest.mark.asyncio
async def test_get_me_no_token(client: AsyncClient):
    """GET /auth/me without token should return 401."""
    response = await client.get("/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_expired_token_rejected(client: AsyncClient):
    """An invalid/expired token should be rejected with 401."""
    response = await client.get(
        "/auth/me", headers={"Authorization": "Bearer invalid.token.here"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient):
    """Token refresh should return new token pair."""
    reg = await client.post("/auth/register", json={
        "email": "refresh@example.com", "password": "securepass123",
    })
    refresh_token = reg.json()["refresh_token"]

    response = await client.post("/auth/refresh", json={
        "refresh_token": refresh_token,
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_user_cannot_access_another_users_documents(client: AsyncClient):
    """Strict isolation: User B's queries must never return User A's data."""
    # Register two users
    user_a = await client.post("/auth/register", json={
        "email": "usera@example.com", "password": "securepass123",
    })
    user_b = await client.post("/auth/register", json={
        "email": "userb@example.com", "password": "securepass123",
    })
    token_a = user_a.json()["access_token"]
    token_b = user_b.json()["access_token"]

    # User A lists documents — should be empty
    docs_a = await client.get(
        "/documents/", headers={"Authorization": f"Bearer {token_a}"}
    )
    assert docs_a.status_code == 200
    assert docs_a.json()["total"] == 0

    # User B lists documents — should also be empty and independent
    docs_b = await client.get(
        "/documents/", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert docs_b.status_code == 200
    assert docs_b.json()["total"] == 0
