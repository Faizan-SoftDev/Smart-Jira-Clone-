"""Account security policies shared by login and privileged operations."""

from apps.billing.models import Subscription


def requires_two_factor(user) -> bool:
    """Enterprise workspace members require a confirmed TOTP device."""
    return Subscription.objects.filter(
        workspace__memberships__user=user,
        tier=Subscription.Tier.ENTERPRISE,
        status__in=[Subscription.Status.ACTIVE, Subscription.Status.TRIALING],
    ).exists()


def has_confirmed_two_factor(user) -> bool:
    return bool(getattr(getattr(user, "totp_device", None), "confirmed", False))
