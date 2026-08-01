from django.urls import path
from .api import CheckoutView, StripeWebhookView

urlpatterns = [
    path("workspaces/<uuid:workspace_id>/billing/checkout/", CheckoutView.as_view()),
    path("billing/stripe/webhook/", StripeWebhookView.as_view()),
]
