"""Database configuration

Used by:
- FastAPI request handlers via `get_db` (auto-commit/rollback).
- Celery worker / background jobs via `async_session` (caller-managed transactions).

Production fixes:
- Accepts sqlite://, sqlite+aiosqlite://, postgres://, postgresql://,
  and postgresql+asyncpg:// URLs.
- Uses NullPool only for local SQLite; normal async pooling remains enabled for
  PostgreSQL/asyncpg in production.
"""

from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool

from app.core.config import settings


def normalize_database_url(url: str) -> str:
    """Return an async SQLAlchemy database URL."""
    if url.startswith("sqlite+aiosqlite://"):
        return url
    if url.startswith("sqlite://"):
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


DATABASE_URL = normalize_database_url(settings.DATABASE_URL)

engine_kwargs = {"echo": settings.DEBUG}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["poolclass"] = NullPool

# Create async engine
engine = create_async_engine(DATABASE_URL, **engine_kwargs)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Base class for models
Base = declarative_base()


def normalize_legacy_user_emails_sync(conn) -> None:
    """Rewrite invalid aliases emitted by older local builds.

    Older versions stored values such as ``admin@aistudio.local`` and
    ``deleted_7@local``. Modern email validation rejects those special-use
    domains, which can turn harmless historical rows into API 500 responses.
    This migration is deterministic, idempotent, and safe on SQLite/PostgreSQL.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(conn)
    try:
        columns = {item["name"] for item in inspector.get_columns("users")}
    except Exception:
        return
    if not {"id", "email"}.issubset(columns):
        return

    conn.execute(text("""
        UPDATE users
           SET email = CASE
               WHEN lower(email) = 'admin@aistudio.local'
                    AND NOT EXISTS (
                        SELECT 1 FROM users AS other
                         WHERE lower(other.email) = 'admin@aistudio.com'
                           AND other.id <> users.id
                    )
                 THEN 'admin@aistudio.com'
               WHEN lower(email) LIKE 'deleted_%@local'
                 THEN 'deleted_' || CAST(id AS VARCHAR) || '@deleted.example.com'
               ELSE 'legacy_' || CAST(id AS VARCHAR) || '@legacy.example.com'
           END
         WHERE lower(email) LIKE '%.local'
            OR lower(email) LIKE '%@local'
    """))


@asynccontextmanager
async def async_session():
    """Async DB session for background jobs (Celery, scripts).

    Notes:
    - No auto-commit.
    - Caller must commit/rollback.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_db():
    """Dependency to get database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def ensure_schema_compatibility() -> None:
    """Best-effort startup migration for existing local/production databases.

    Base.metadata.create_all() creates missing tables but it does NOT add columns
    to tables that already exist. This project evolved quickly (admin roles,
    support, img2img/img2vid, payments, refunds), so older SQLite/PostgreSQL
    databases can otherwise crash at runtime with "no such column" errors.

    This function only adds missing nullable/defaulted columns used by the
    current code. It is intentionally conservative and idempotent. Keep real
    Alembic migrations for large production schema changes, but this prevents
    hidden upgrade bugs for current installs.
    """

    def _sync(conn):
        from sqlalchemy import inspect, text

        inspector = inspect(conn)
        dialect = conn.dialect.name

        def qident(name: str) -> str:
            return conn.dialect.identifier_preparer.quote(name)

        def column_names(table: str) -> set[str]:
            try:
                return {c["name"] for c in inspector.get_columns(table)}
            except Exception:
                return set()

        def add_columns(table: str, columns: dict[str, tuple[str, str]]):
            existing = column_names(table)
            if not existing:
                return
            for name, (sqlite_sql, postgres_sql) in columns.items():
                if name in existing:
                    continue
                col_sql = sqlite_sql if dialect == "sqlite" else postgres_sql
                conn.execute(text(f"ALTER TABLE {qident(table)} ADD COLUMN {qident(name)} {col_sql}"))

        bool_false = ("BOOLEAN DEFAULT 0", "BOOLEAN DEFAULT FALSE")
        bool_true = ("BOOLEAN DEFAULT 1", "BOOLEAN DEFAULT TRUE")
        int_zero = ("INTEGER DEFAULT 0", "INTEGER DEFAULT 0")
        dt = ("DATETIME", "TIMESTAMP")
        dt_now = ("DATETIME", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

        add_columns("users", {
            "full_name": ("VARCHAR(255)", "VARCHAR(255)"),
            "is_active": bool_true,
            "is_verified": bool_false,
            "is_admin": bool_false,
            "auth_token_version": int_zero,
            "role": ("VARCHAR(32) DEFAULT 'USER'", "VARCHAR(32) DEFAULT 'USER'"),
            "credits": int_zero,
            "api_key": ("VARCHAR(255)", "VARCHAR(255)"),
            "subscription_tier": ("VARCHAR(50) DEFAULT 'free'", "VARCHAR(50) DEFAULT 'free'"),
            "subscription_status": ("VARCHAR(50) DEFAULT 'inactive'", "VARCHAR(50) DEFAULT 'inactive'"),
            "subscription_expires_at": dt,
            "stripe_customer_id": ("VARCHAR(255)", "VARCHAR(255)"),
            "stripe_subscription_id": ("VARCHAR(255)", "VARCHAR(255)"),
            "created_at": dt_now,
            "updated_at": dt_now,
            "last_login_at": dt,
        })

        add_columns("generations", {
            "negative_prompt": ("TEXT", "TEXT"),
            "width": ("INTEGER", "INTEGER"),
            "height": ("INTEGER", "INTEGER"),
            "duration": ("INTEGER", "INTEGER"),
            "style": ("VARCHAR(100)", "VARCHAR(100)"),
            "strength": ("FLOAT", "DOUBLE PRECISION"),
            "motion_strength": ("INTEGER", "INTEGER"),
            "status": ("VARCHAR(50) DEFAULT 'pending'", "VARCHAR(50) DEFAULT 'pending'"),
            "result_url": ("TEXT", "TEXT"),
            "thumbnail_url": ("TEXT", "TEXT"),
            "local_path": ("TEXT", "TEXT"),
            "model_used": ("VARCHAR(100)", "VARCHAR(100)"),
            "credits_used": int_zero,
            "generation_time": ("FLOAT", "DOUBLE PRECISION"),
            "error_message": ("TEXT", "TEXT"),
            "created_at": dt_now,
            "completed_at": dt,
        })

        add_columns("credit_transactions", {
            "generation_id": ("INTEGER", "INTEGER"),
            "payment_intent_id": ("VARCHAR(255)", "VARCHAR(255)"),
            "balance_after": int_zero,
            "created_at": dt_now,
        })

        add_columns("subscriptions", {
            "stripe_subscription_id": ("VARCHAR(255)", "VARCHAR(255)"),
            "stripe_price_id": ("VARCHAR(255)", "VARCHAR(255)"),
            "current_period_start": dt,
            "current_period_end": dt,
            "amount": ("FLOAT", "DOUBLE PRECISION"),
            "currency": ("VARCHAR(10) DEFAULT 'eur'", "VARCHAR(10) DEFAULT 'eur'"),
            "monthly_credits": int_zero,
            "created_at": dt_now,
            "canceled_at": dt,
        })

        add_columns("payments", {
            "provider": ("VARCHAR(50) DEFAULT 'stripe'", "VARCHAR(50) DEFAULT 'stripe'"),
            "provider_payment_id": ("VARCHAR(255)", "VARCHAR(255)"),
            "payment_type": ("VARCHAR(50)", "VARCHAR(50)"),
            "status": ("VARCHAR(50) DEFAULT 'succeeded'", "VARCHAR(50) DEFAULT 'succeeded'"),
            "amount": ("FLOAT DEFAULT 0", "DOUBLE PRECISION DEFAULT 0"),
            "currency": ("VARCHAR(10) DEFAULT 'eur'", "VARCHAR(10) DEFAULT 'eur'"),
            "created_at": dt_now,
        })

        add_columns("support_tickets", {
            "status": ("VARCHAR(32) DEFAULT 'open'", "VARCHAR(32) DEFAULT 'open'"),
            "admin_notes": ("TEXT", "TEXT"),
            "is_deleted": bool_false,
            "created_at": dt_now,
            "updated_at": dt_now,
        })

        # Fill safe defaults for rows created before the columns existed. This is
        # required for upgraded SQLite DBs where ALTER TABLE could not attach
        # CURRENT_TIMESTAMP as a dynamic default.
        def exec_if_table(table: str, sql: str):
            if column_names(table):
                conn.execute(text(sql))

        exec_if_table("users", "UPDATE users SET is_active=COALESCE(is_active, 1), is_verified=COALESCE(is_verified, 0), is_admin=COALESCE(is_admin, 0), auth_token_version=COALESCE(auth_token_version, 0), role=COALESCE(role, 'USER'), credits=COALESCE(credits, 0), subscription_tier=COALESCE(subscription_tier, 'free'), subscription_status=COALESCE(subscription_status, 'inactive'), created_at=COALESCE(created_at, CURRENT_TIMESTAMP), updated_at=COALESCE(updated_at, CURRENT_TIMESTAMP)")
        exec_if_table("generations", "UPDATE generations SET status=COALESCE(status, 'pending'), credits_used=COALESCE(credits_used, 0), created_at=COALESCE(created_at, CURRENT_TIMESTAMP)")
        exec_if_table("credit_transactions", "UPDATE credit_transactions SET balance_after=COALESCE(balance_after, 0), created_at=COALESCE(created_at, CURRENT_TIMESTAMP)")
        exec_if_table("subscriptions", "UPDATE subscriptions SET currency=COALESCE(currency, 'eur'), monthly_credits=COALESCE(monthly_credits, 0), created_at=COALESCE(created_at, CURRENT_TIMESTAMP)")
        exec_if_table("payments", "UPDATE payments SET provider=COALESCE(provider, 'stripe'), status=COALESCE(status, 'succeeded'), amount=COALESCE(amount, 0), currency=COALESCE(currency, 'eur'), created_at=COALESCE(created_at, CURRENT_TIMESTAMP)")
        exec_if_table("support_tickets", "UPDATE support_tickets SET status=COALESCE(status, 'open'), is_deleted=COALESCE(is_deleted, 0), created_at=COALESCE(created_at, CURRENT_TIMESTAMP), updated_at=COALESCE(updated_at, CURRENT_TIMESTAMP)")

        # Rewrite invalid aliases emitted by older local builds after all
        # compatibility columns exist.
        normalize_legacy_user_emails_sync(conn)

    async with engine.begin() as conn:
        await conn.run_sync(_sync)
