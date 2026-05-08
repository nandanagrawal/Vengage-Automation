from fastapi import APIRouter

from app.api.v1.endpoints import (
    activity,
    auth,
    auth_qbo,
    centers,
    customer_types,
    customers,
    dashboard,
    health,
    invoice_uploads,
    invoices,
    product_and_services,
    service_codes,
    sync,
    webhooks,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(dashboard.router, tags=["dashboard"])
api_router.include_router(auth_qbo.router, prefix="/auth/qbo", tags=["quickbooks-oauth"])
api_router.include_router(customer_types.router, tags=["customer-types"])
api_router.include_router(customers.router, tags=["customers"])
api_router.include_router(centers.router, tags=["centers"])
api_router.include_router(product_and_services.router, tags=["product-and-services"])
api_router.include_router(invoices.router, tags=["invoices"])
api_router.include_router(invoice_uploads.router, tags=["invoice-uploads"])
api_router.include_router(service_codes.router, tags=["service-codes"])
api_router.include_router(sync.router, tags=["sync"])
api_router.include_router(activity.router, tags=["activity"])
api_router.include_router(webhooks.router, tags=["webhooks"])
