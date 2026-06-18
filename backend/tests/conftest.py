import os
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from httpx import AsyncClient

# Ensure required env vars exist BEFORE importing the app
os.environ.setdefault("SECRET_KEY", "test-secret-key-change-me")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-change-me")
os.environ.setdefault("JWT_ISSUER", "ai-studio-pro-test")
os.environ.setdefault("JWT_AUDIENCE", "ai-studio-pro-test")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")
os.environ.setdefault("ENABLE_SECURITY_HEADERS", "true")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_dummy")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_dummy")

from app.core.database import Base
from app.core import database as database_module
from main import app


@pytest.fixture(scope="session")
def event_loop():
    # pytest-asyncio compatibility
    import asyncio
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("db") / "test.db"
    url = f"sqlite+aiosqlite:///{db_path}"
    engine = create_async_engine(url, echo=False, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture()
async def client(test_engine):
    # Patch the global engine/sessionmaker used by the app
    database_module.engine = test_engine
    database_module.AsyncSessionLocal = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    # Override the get_db dependency to use the test DB
    async def _override_get_db():
        async with database_module.AsyncSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[database_module.get_db] = _override_get_db

    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
