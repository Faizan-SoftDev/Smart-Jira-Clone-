"""Provider-neutral billing state; Stripe IDs are stored but never trusted without webhooks."""

from django.db import models

from apps.workspaces.models import Workspace


class Subscription(models.Model):
    class Tier(models.TextChoices):
        FREE = "free", "Free"
        PRO = "pro", "Pro"
        ENTERPRISE = "enterprise", "Enterprise"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        TRIALING = "trialing", "Trialing"
        PAST_DUE = "past_due", "Past due"
        CANCELED = "canceled", "Canceled"

    workspace = models.OneToOneField(Workspace, on_delete=models.CASCADE, related_name="subscription")
    tier = models.CharField(max_length=16, choices=Tier.choices, default=Tier.FREE)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    seat_count = models.PositiveIntegerField(default=1)
    stripe_customer_id = models.CharField(max_length=255, blank=True)
    stripe_subscription_id = models.CharField(max_length=255, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class BillingEvent(models.Model):
    """Idempotency ledger for verified provider webhook events."""

    provider_event_id = models.CharField(max_length=255, unique=True)
    event_type = models.CharField(max_length=120)
    payload = models.JSONField()
    received_at = models.DateTimeField(auto_now_add=True)
