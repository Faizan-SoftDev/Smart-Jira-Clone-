"""Stripe checkout and webhook endpoints; provider events are the source of truth."""

import stripe
from django.conf import settings
from django.db import IntegrityError, transaction
from rest_framework import serializers
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.workspaces.models import Workspace
from apps.workspaces.permissions import WorkspaceAction, can_access_workspace

from .models import BillingEvent, Subscription


class CheckoutSerializer(serializers.Serializer):
    tier = serializers.ChoiceField(choices=[Subscription.Tier.PRO, Subscription.Tier.ENTERPRISE])
    success_url = serializers.URLField()
    cancel_url = serializers.URLField()


class CheckoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, workspace_id):
        try:
            workspace = Workspace.objects.get(pk=workspace_id)
        except Workspace.DoesNotExist as exc:
            raise NotFound("Workspace not found.") from exc
        if not can_access_workspace(user=request.user, workspace=workspace, action=WorkspaceAction.MANAGE_WORKSPACE):
            raise PermissionDenied("Only workspace administrators can manage billing.")
        serializer = CheckoutSerializer(data=request.data); serializer.is_valid(raise_exception=True)
        price_id = settings.STRIPE_PRO_PRICE_ID if serializer.validated_data["tier"] == Subscription.Tier.PRO else settings.STRIPE_ENTERPRISE_PRICE_ID
        if not settings.STRIPE_SECRET_KEY or not price_id:
            raise serializers.ValidationError({"detail": "Stripe billing is not configured."})
        stripe.api_key = settings.STRIPE_SECRET_KEY
        subscription, _ = Subscription.objects.get_or_create(workspace=workspace)
        session = stripe.checkout.Session.create(
            mode="subscription", customer=subscription.stripe_customer_id or None,
            line_items=[{"price": price_id, "quantity": max(1, subscription.seat_count)}],
            success_url=serializer.validated_data["success_url"], cancel_url=serializer.validated_data["cancel_url"],
            metadata={"workspace_id": str(workspace.id), "tier": serializer.validated_data["tier"]},
        )
        return Response({"checkout_url": session.url})


class StripeWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        if not settings.STRIPE_WEBHOOK_SECRET:
            return Response(status=400)
        try:
            event = stripe.Webhook.construct_event(request.body, request.headers.get("Stripe-Signature", ""), settings.STRIPE_WEBHOOK_SECRET)
        except (ValueError, stripe.error.SignatureVerificationError):
            return Response(status=400)
        try:
            with transaction.atomic():
                BillingEvent.objects.create(provider_event_id=event["id"], event_type=event["type"], payload=event["data"]["object"])
                obj = event["data"]["object"]
                workspace_id = obj.get("metadata", {}).get("workspace_id")
                if workspace_id and event["type"] in {"customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"}:
                    subscription, _ = Subscription.objects.get_or_create(workspace_id=workspace_id)
                    subscription.stripe_customer_id = obj.get("customer", "")
                    subscription.stripe_subscription_id = obj.get("id", "")
                    subscription.status = Subscription.Status.CANCELED if event["type"].endswith("deleted") else obj.get("status", Subscription.Status.ACTIVE)
                    subscription.save()
        except IntegrityError:  # duplicate event replay is a successful no-op
            pass
        return Response(status=200)
