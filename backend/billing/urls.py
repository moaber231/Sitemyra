from django.urls import path

from .views import (
    create_checkout,
    create_portal_session,
    plans,
    stripe_webhook,
    subscription_status,
)

urlpatterns = [
    path("plans/", plans, name="billing-plans"),
    path("subscription/", subscription_status, name="billing-subscription"),
    path("checkout/", create_checkout, name="billing-checkout"),
    path("portal/", create_portal_session, name="billing-portal"),
    path("webhook/", stripe_webhook, name="billing-webhook"),
]
