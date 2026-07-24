import logging

from celery import shared_task

from common.models import Org
from common.tasks import set_rls_context
from communications.gmail import sync_mailbox
from communications.models import MailboxConnection

logger = logging.getLogger(__name__)


@shared_task
def sync_org_mailboxes(org_id):
    set_rls_context(org_id)
    for mailbox in MailboxConnection.objects.filter(
        org_id=org_id, provider="gmail", is_active=True
    ):
        try:
            sync_mailbox(mailbox)
        except Exception:
            logger.exception("Gmail synchronization failed for mailbox %s", mailbox.id)


@shared_task
def schedule_gmail_sync():
    for org_id in Org.objects.filter(is_active=True).values_list("id", flat=True):
        sync_org_mailboxes.delay(str(org_id))
