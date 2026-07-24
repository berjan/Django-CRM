from django.urls import path

from communications.views import (
    GmailCallbackView,
    GmailConnectView,
    LeadEmailSendView,
    LeadThreadListView,
    MailboxDisconnectView,
    MailboxListView,
    MailboxSyncView,
    ThreadReplyView,
)

app_name = "api_communications"

urlpatterns = [
    path("mailboxes/", MailboxListView.as_view(), name="mailboxes"),
    path("gmail/connect/", GmailConnectView.as_view(), name="gmail_connect"),
    path("gmail/callback/", GmailCallbackView.as_view(), name="gmail_callback"),
    path(
        "mailboxes/<uuid:pk>/sync/",
        MailboxSyncView.as_view(),
        name="mailbox_sync",
    ),
    path(
        "mailboxes/<uuid:pk>/disconnect/",
        MailboxDisconnectView.as_view(),
        name="mailbox_disconnect",
    ),
    path(
        "leads/<uuid:lead_id>/threads/",
        LeadThreadListView.as_view(),
        name="lead_threads",
    ),
    path(
        "leads/<uuid:lead_id>/send/",
        LeadEmailSendView.as_view(),
        name="lead_send",
    ),
    path(
        "threads/<uuid:pk>/reply/",
        ThreadReplyView.as_view(),
        name="thread_reply",
    ),
]
