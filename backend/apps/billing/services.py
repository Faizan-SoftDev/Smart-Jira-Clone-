"""Feature checks that keep billing policy outside HTTP views."""

from .models import Subscription


TIER_FEATURES = {
    Subscription.Tier.FREE: frozenset({"kanban", "basic_workflows"}),
    Subscription.Tier.PRO: frozenset({"kanban", "basic_workflows", "custom_fields", "sprints", "reports"}),
    Subscription.Tier.ENTERPRISE: frozenset({"kanban", "basic_workflows", "custom_fields", "sprints", "reports", "api_access", "sso", "custom_domains"}),
}


def has_feature(*, workspace, feature: str) -> bool:
    subscription, _ = Subscription.objects.get_or_create(workspace=workspace)
    return subscription.status in {Subscription.Status.ACTIVE, Subscription.Status.TRIALING} and feature in TIER_FEATURES[subscription.tier]
