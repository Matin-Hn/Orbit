"""
Shared fixtures.

Assumptions (adjust import paths if yours differ):
- app.main:app is the FastAPI instance
- app.api.deps:get_db is the async DB dependency
- app.core.redis:get_redis is the redis dependency
- app.models.user:User is your user model
- app.services.auth_service exposes get_current_user_from_cookie,
  get_optional_current_user_from_cookie, require_admin, get_current_channel

Strategy:
- Real async SQLite (aiosqlite) in-memory DB for routes that hit the DB directly
  (channels.py does raw `select(Channel)` queries, comments/users routes hit crud/services).
- fakeredis for the redis dependency.
- Auth dependencies are overridden with fixtures that return fake User/Channel
  objects, so route-level permission logic can be tested without real JWT/cookies.
- Service-layer classes (ChannelService, CommentService) and crud modules are
  mocked via monkeypatch in individual test files, so we test the ROUTE
  (status codes, permission checks, payload shape) rather than re-testing
  business logic that presumably has its own unit tests.
"""
import pytest
import pytest_asyncio
import fakeredis
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import Base
from app.api.deps import get_db
from app.core.redis import get_redis
from app.services.auth_service import (
    get_current_user_from_cookie,
    get_optional_current_user_from_cookie,
    require_admin,
)

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingAsyncSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


@pytest_asyncio.fixture(scope="function")
async def db_session():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingAsyncSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
def redis_client():
    client = fakeredis.FakeStrictRedis(decode_responses=True)
    yield client
    client.flushall()


class FakeUser:
    """Lightweight stand-in for the ORM User model in route-level tests."""

    def __init__(self, id=1, email="user@example.com", username="testuser",
                 role="user", is_active=True, is_verified=True,
                 language="en", theme="light",
                 created_date=None, updated_date=None):
        self.id = id
        self.email = email
        self.username = username
        self.role = role
        self.is_active = is_active
        self.is_verified = is_verified
        self.language = language
        self.theme = theme
        self.created_date = created_date or datetime.now(timezone.utc)
        self.updated_date = updated_date or datetime.now(timezone.utc)


@pytest.fixture
def normal_user():
    return FakeUser(id=1, role="user")


@pytest.fixture
def admin_user():
    return FakeUser(id=99, role="admin")


@pytest_asyncio.fixture(scope="function")
async def client(db_session, redis_client):
    """Unauthenticated client. Use `auth_client`/`admin_client` for authed routes."""

    async def override_get_db():
        yield db_session

    def override_get_redis():
        return redis_client

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def auth_client(client, normal_user):
    app.dependency_overrides[get_current_user_from_cookie] = lambda: normal_user
    app.dependency_overrides[get_optional_current_user_from_cookie] = lambda: normal_user
    yield client
    app.dependency_overrides.pop(get_current_user_from_cookie, None)
    app.dependency_overrides.pop(get_optional_current_user_from_cookie, None)


@pytest_asyncio.fixture(scope="function")
async def admin_client(client, admin_user):
    app.dependency_overrides[get_current_user_from_cookie] = lambda: admin_user
    app.dependency_overrides[get_optional_current_user_from_cookie] = lambda: admin_user
    app.dependency_overrides[require_admin] = lambda: admin_user
    yield client
    app.dependency_overrides.pop(get_current_user_from_cookie, None)
    app.dependency_overrides.pop(get_optional_current_user_from_cookie, None)
    app.dependency_overrides.pop(require_admin, None)