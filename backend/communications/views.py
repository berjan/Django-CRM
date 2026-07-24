from django.core import signing
from django.core.exceptions import ImproperlyConfigured
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import HasOrgContext
from communications.gmail import (
    build_authorization_url,
    connect_mailbox,
    gmail_is_configured,
    reply_to_thread,
    send_lead_email,
    sync_mailbox,
)
from communications.models import EmailThread, MailboxConnection
from communications.serializers import (
    EmailMessageSerializer,
    EmailThreadSerializer,
    MailboxConnectionSerializer,
)
from leads.models import Lead


def _is_admin(profile):
    return profile.role == "ADMIN" or getattr(profile, "is_admin", False)


class MailboxListView(APIView):
    permission_classes = (IsAuthenticated, HasOrgContext)

    def get(self, request):
        mailboxes = MailboxConnection.objects.filter(org=request.profile.org)
        return Response(
            {
                "configured": gmail_is_configured(),
                "mailboxes": MailboxConnectionSerializer(mailboxes, many=True).data,
            }
        )


class GmailConnectView(APIView):
    permission_classes = (IsAuthenticated, HasOrgContext)

    def post(self, request):
        if not _is_admin(request.profile):
            return Response(
                {"detail": "Admin access required"},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            authorization_url = build_authorization_url(
                org_id=request.profile.org_id, user_id=request.user.id
            )
        except ImproperlyConfigured as exc:
            return Response(
                {"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        return Response({"authorization_url": authorization_url})


class GmailCallbackView(APIView):
    permission_classes = (IsAuthenticated, HasOrgContext)

    def post(self, request):
        if not _is_admin(request.profile):
            return Response(
                {"detail": "Admin access required"},
                status=status.HTTP_403_FORBIDDEN,
            )
        code = request.data.get("code", "")
        state_value = request.data.get("state", "")
        if not code or not state_value:
            return Response(
                {"detail": "OAuth code and state are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            mailbox = connect_mailbox(
                code=code,
                state=state_value,
                org=request.profile.org,
                user=request.user,
            )
        except (ImproperlyConfigured, signing.BadSignature, ValueError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(MailboxConnectionSerializer(mailbox).data)


class MailboxSyncView(APIView):
    permission_classes = (IsAuthenticated, HasOrgContext)

    def post(self, request, pk):
        mailbox = get_object_or_404(
            MailboxConnection, pk=pk, org=request.profile.org, is_active=True
        )
        try:
            ingested = sync_mailbox(mailbox)
        except Exception as exc:
            mailbox.last_error = str(exc)[:2000]
            mailbox.save(update_fields=["last_error", "updated_at"])
            return Response(
                {"detail": "Mailbox synchronization failed"},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response(
            {
                "ingested": ingested,
                "mailbox": MailboxConnectionSerializer(mailbox).data,
            }
        )


class MailboxDisconnectView(APIView):
    permission_classes = (IsAuthenticated, HasOrgContext)

    def delete(self, request, pk):
        if not _is_admin(request.profile):
            return Response(
                {"detail": "Admin access required"},
                status=status.HTTP_403_FORBIDDEN,
            )
        mailbox = get_object_or_404(MailboxConnection, pk=pk, org=request.profile.org)
        mailbox.is_active = False
        mailbox.credentials_encrypted = ""
        mailbox.save(update_fields=["is_active", "credentials_encrypted", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class LeadThreadListView(APIView):
    permission_classes = (IsAuthenticated, HasOrgContext)

    def get(self, request, lead_id):
        get_object_or_404(Lead, pk=lead_id, org=request.profile.org)
        threads = (
            EmailThread.objects.filter(org=request.profile.org, lead_id=lead_id)
            .select_related("mailbox")
            .prefetch_related("messages")
        )
        return Response({"threads": EmailThreadSerializer(threads, many=True).data})


class LeadEmailSendView(APIView):
    permission_classes = (IsAuthenticated, HasOrgContext)

    class InputSerializer(serializers.Serializer):
        mailbox_id = serializers.UUIDField()
        subject = serializers.CharField(max_length=512)
        body_text = serializers.CharField()
        follow_up_days = serializers.IntegerField(
            required=False, default=5, min_value=1, max_value=30
        )

    def post(self, request, lead_id):
        payload = self.InputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        lead = get_object_or_404(Lead, pk=lead_id, org=request.profile.org)
        mailbox = get_object_or_404(
            MailboxConnection,
            pk=payload.validated_data["mailbox_id"],
            org=request.profile.org,
            is_active=True,
        )
        try:
            message = send_lead_email(
                mailbox=mailbox,
                lead=lead,
                subject=payload.validated_data["subject"],
                body_text=payload.validated_data["body_text"],
                follow_up_days=payload.validated_data["follow_up_days"],
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            EmailMessageSerializer(message).data, status=status.HTTP_201_CREATED
        )


class ThreadReplyView(APIView):
    permission_classes = (IsAuthenticated, HasOrgContext)

    class InputSerializer(serializers.Serializer):
        body_text = serializers.CharField()

    def post(self, request, pk):
        payload = self.InputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        thread = get_object_or_404(
            EmailThread.objects.select_related("mailbox", "lead"),
            pk=pk,
            org=request.profile.org,
        )
        try:
            message = reply_to_thread(
                thread=thread, body_text=payload.validated_data["body_text"]
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            EmailMessageSerializer(message).data, status=status.HTTP_201_CREATED
        )
