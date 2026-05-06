from fastapi import APIRouter

from app.api.v1.endpoints import activity, auth, auth_qbo, customers, health, sync, webhooks

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(auth_qbo.router, prefix="/auth/qbo", tags=["quickbooks-oauth"])
api_router.include_router(customers.router, tags=["customers"])
api_router.include_router(sync.router, tags=["sync"])
api_router.include_router(activity.router, tags=["activity"])
api_router.include_router(webhooks.router, tags=["webhooks"])
