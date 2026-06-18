from sqlalchemy import select, func
from app.core.database import async_session
from app.core.config import settings
from app.models.user import User
from app.core.security import get_password_hash
from pydantic import EmailStr, TypeAdapter


def _validated_seed_email(value: str) -> str:
    """Validate initial-admin configuration before touching the database."""
    return str(TypeAdapter(EmailStr).validate_python((value or "").strip())).lower()


async def ensure_initial_admins():
    """
    Create initial admin accounts if they do not already exist.
    Reads from env:
    INITIAL_ADMIN_EMAIL
    INITIAL_ADMIN_PASSWORD
    INITIAL_ADMIN_FULL_NAME

    Optional second admin:
    INITIAL_ADMIN_EMAIL_2
    INITIAL_ADMIN_PASSWORD_2
    INITIAL_ADMIN_FULL_NAME_2
    """

    admins = []

    if getattr(settings, "INITIAL_ADMIN_EMAIL", None) and getattr(settings, "INITIAL_ADMIN_PASSWORD", None):
        admins.append(
            {
                "email": _validated_seed_email(settings.INITIAL_ADMIN_EMAIL),
                "password": settings.INITIAL_ADMIN_PASSWORD,
                "full_name": getattr(settings, "INITIAL_ADMIN_FULL_NAME", "Super Admin"),
            }
        )

    if getattr(settings, "INITIAL_ADMIN_EMAIL_2", None) and getattr(settings, "INITIAL_ADMIN_PASSWORD_2", None):
        admins.append(
            {
                "email": _validated_seed_email(settings.INITIAL_ADMIN_EMAIL_2),
                "password": settings.INITIAL_ADMIN_PASSWORD_2,
                "full_name": getattr(settings, "INITIAL_ADMIN_FULL_NAME_2", "Admin 2"),
            }
        )

    if not admins:
        return

    async with async_session() as db:
        for admin_data in admins:
            result = await db.execute(
                select(User).where(func.lower(User.email) == admin_data["email"])
            )
            existing = result.scalar_one_or_none()

            if existing:
                changed = False

                if not getattr(existing, "is_admin", False):
                    existing.is_admin = True
                    changed = True

                if getattr(existing, "role", "").upper() != "ADMIN":
                    existing.role = "ADMIN"
                    changed = True

                if not getattr(existing, "is_active", True):
                    existing.is_active = True
                    changed = True

                if changed:
                    await db.commit()
            else:
                new_admin = User(
                    email=admin_data["email"],
                    hashed_password=get_password_hash(admin_data["password"]),
                    full_name=admin_data["full_name"],
                    is_active=True,
                    is_verified=True,
                    is_admin=True,
                    role="ADMIN",
                    credits=1000,
                )
                db.add(new_admin)
                await db.commit()