"""API router"""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, users, generations, credits, subscriptions, webhooks, version, admin_stats, models, admin_generations, runtime
# NEW
from app.api.v1.endpoints.admin_users import router as admin_users_router
from app.api.v1.endpoints.support_tickets import router as support_router, admin_router as admin_support_router

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(generations.router, prefix="/generations", tags=["Generations"])
api_router.include_router(credits.router, prefix="/credits", tags=["Credits"])
api_router.include_router(subscriptions.router, prefix="/subscriptions", tags=["Subscriptions"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])
api_router.include_router(version.router, prefix="/version", tags=["Version"])
api_router.include_router(admin_stats.router, prefix="/admin/stats", tags=["Admin"])
api_router.include_router(admin_generations.router, prefix="/admin", tags=["Admin Generations"])

api_router.include_router(models.router, prefix="", tags=["Models"])
api_router.include_router(runtime.router, prefix="", tags=["Runtime"])


# Admin user management (NEW)
api_router.include_router(admin_users_router, prefix="/admin/users")

# Support tickets (NEW)
api_router.include_router(support_router, prefix="/support")
api_router.include_router(admin_support_router, prefix="/admin/support")

