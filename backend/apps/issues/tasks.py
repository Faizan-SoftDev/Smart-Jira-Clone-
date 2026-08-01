"""Asynchronous issue tasks. Scanner integration is isolated behind this boundary."""

from celery import shared_task
from django.core.mail import send_mail

from .models import IssueAttachment, Notification


@shared_task(bind=True, autoretry_for=(OSError,), retry_backoff=True, max_retries=3)
def scan_attachment(self, attachment_id: str) -> None:
    """Mark an upload clean only after its bytes can be safely accessed.

    Replace the placeholder scanner call with ClamAV/S3 malware scanning in the
    deployment environment; failures leave the attachment pending for retry.
    """
    attachment = IssueAttachment.objects.get(pk=attachment_id)
    if attachment.scan_status != IssueAttachment.ScanStatus.PENDING:
        return
    with attachment.file.open("rb") as uploaded:
        uploaded.read(1)  # verifies object availability without loading the whole file
    attachment.scan_status = IssueAttachment.ScanStatus.CLEAN
    attachment.save(update_fields=["scan_status"])


@shared_task
def send_mention_email(notification_id: str) -> None:
    """Deliver a concise mention email; failed delivery remains visible in-app."""
    notification = Notification.objects.select_related("recipient__user", "issue__project").get(pk=notification_id)
    if notification.notification_type != Notification.Type.MENTION:
        return
    send_mail(
        subject=f"You were mentioned on {notification.issue.key}",
        message=f"You were mentioned on {notification.issue.key}: {notification.issue.title}",
        from_email=None,
        recipient_list=[notification.recipient.user.email],
        fail_silently=False,
    )
