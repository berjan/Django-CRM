from django.core import signing
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.db.models import Count, F, Prefetch, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
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
from communications.models import (
    EmailDraft,
    EmailTemplate,
    EmailTemplateVersion,
    EmailThread,
    LeadEmailTemplateAssignment,
    MailboxConnection,
    ThreadReadState,
)
from communications.render import ALLOWED_VARIABLES, render_email, text_to_html
from communications.serializers import (
    EmailDraftSerializer,
    EmailMessageSerializer,
    EmailTemplateSerializer,
    EmailThreadSerializer,
    LeadEmailTemplateAssignmentSerializer,
    MailboxConnectionSerializer,
)
from leads.models import Lead


def _is_admin(profile):
    return profile.role == "ADMIN" or getattr(profile, "is_admin", False)


def _visible_templates(profile):
    return EmailTemplate.objects.filter(org=profile.org).filter(
        Q(scope=EmailTemplate.SCOPE_ORG)
        | Q(scope=EmailTemplate.SCOPE_PERSONAL, owner=profile)
    )


def _template_writable(request, pk):
    template = get_object_or_404(EmailTemplate, pk=pk, org=request.profile.org)
    if template.scope == EmailTemplate.SCOPE_ORG and not _is_admin(request.profile):
        return None, Response(
            {"detail": "Only admins can manage organization templates"},
            status=status.HTTP_403_FORBIDDEN,
        )
    if (
        template.scope == EmailTemplate.SCOPE_PERSONAL
        and template.owner_id != request.profile.id
    ):
        return None, Response(
            {"detail": "You can only manage your own personal templates"},
            status=status.HTTP_403_FORBIDDEN,
        )
    return template, None


def _scope_owner(profile, scope):
    if scope == EmailTemplate.SCOPE_ORG:
        if not _is_admin(profile):
            raise serializers.ValidationError(
                {"scope": "Only admins can manage organization templates"}
            )
        return None
    if scope == EmailTemplate.SCOPE_PERSONAL:
        return profile
    raise serializers.ValidationError({"scope": "Invalid template scope"})


def _unique_template_name(*, org, scope, owner, requested_name):
    base = requested_name[:255]
    candidate = base
    number = 2
    while EmailTemplate.objects.filter(
        org=org, scope=scope, owner=owner, name=candidate
    ).exists():
        suffix = f" ({number})"
        candidate = f"{base[: 255 - len(suffix)]}{suffix}"
        number += 1
    return candidate


def _thread_queryset(profile):
    return (
        EmailThread.objects.filter(org=profile.org)
        .select_related("mailbox", "lead")
        .prefetch_related(
            "messages",
            Prefetch(
                "read_states",
                queryset=ThreadReadState.objects.filter(profile=profile),
                to_attr="request_read_states",
            ),
        )
        .annotate(
            message_count_value=Count("messages", distinct=True),
            draft_count_value=Count(
                "drafts",
                filter=Q(drafts__status=EmailDraft.STATUS_DRAFT),
                distinct=True,
            ),
        )
    )


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
        threads = _thread_queryset(request.profile).filter(lead_id=lead_id)
        return Response({"threads": EmailThreadSerializer(threads, many=True).data})


class ThreadDetailView(APIView):
    permission_classes = (IsAuthenticated, HasOrgContext)

    def get(self, request, pk):
        thread = get_object_or_404(_thread_queryset(request.profile), pk=pk)
        return Response(EmailThreadSerializer(thread).data)


class ThreadReadView(APIView):
    permission_classes = (IsAuthenticated, HasOrgContext)

    def post(self, request, pk):
        thread = get_object_or_404(EmailThread, pk=pk, org=request.profile.org)
        ThreadReadState.objects.update_or_create(
            org=request.profile.org,
            thread=thread,
            profile=request.profile,
            defaults={"last_read_at": timezone.now()},
        )
        refreshed = get_object_or_404(_thread_queryset(request.profile), pk=pk)
        return Response(EmailThreadSerializer(refreshed).data)


class LeadEmailSendView(APIView):
    permission_classes = (IsAuthenticated, HasOrgContext)

    def post(self, request, lead_id):
        return Response(
            {
                "detail": (
                    "Direct sending has been replaced by reviewable drafts. "
                    "Create a draft and use its send endpoint."
                )
            },
            status=status.HTTP_410_GONE,
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


class ThreadDraftListCreateView(APIView):
    permission_classes = (IsAuthenticated, HasOrgContext)

    class InputSerializer(serializers.Serializer):
        template_id = serializers.UUIDField(required=False, allow_null=True)
        body_text = serializers.CharField(required=False)
        follow_up_days = serializers.IntegerField(
            required=False, default=5, min_value=1, max_value=30
        )

        def validate(self, attrs):
            if not attrs.get("template_id") and not attrs.get("body_text"):
                raise serializers.ValidationError(
                    "Reply drafts require template_id or body_text"
                )
            return attrs

    def get(self, request, pk):
        thread = get_object_or_404(EmailThread, pk=pk, org=request.profile.org)
        drafts = EmailDraft.objects.filter(
            org=request.profile.org,
            thread=thread,
            status=EmailDraft.STATUS_DRAFT,
        ).select_related("mailbox", "template_version")
        return Response({"results": EmailDraftSerializer(drafts, many=True).data})

    @transaction.atomic
    def post(self, request, pk):
        payload = self.InputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        thread = get_object_or_404(
            EmailThread.objects.select_related("lead", "mailbox"),
            pk=pk,
            org=request.profile.org,
        )
        if not thread.lead.email:
            raise serializers.ValidationError({"lead": "Lead has no email address"})
        template_version = None
        source = EmailDraft.SOURCE_MANUAL
        if payload.validated_data.get("template_id"):
            template = get_object_or_404(
                _visible_templates(request.profile),
                pk=payload.validated_data["template_id"],
                is_active=True,
            )
            template_version = get_object_or_404(
                EmailTemplateVersion,
                org=request.profile.org,
                template=template,
                version=template.current_version,
            )
            rendered = render_email(
                subject=template_version.subject,
                body_text=template_version.body_text,
                lead=thread.lead,
                organization=request.profile.org,
                sender=request.profile,
            )
            if not rendered.valid:
                raise serializers.ValidationError(
                    {
                        "missing_variables": rendered.missing_variables,
                        "unknown_variables": rendered.unknown_variables,
                    }
                )
            body_text = rendered.body_text
            source = EmailDraft.SOURCE_TEMPLATE
        else:
            body_text = payload.validated_data["body_text"].strip()
        draft = EmailDraft.objects.create(
            org=request.profile.org,
            lead=thread.lead,
            thread=thread,
            mailbox=thread.mailbox,
            template_version=template_version,
            recipient=thread.lead.email.strip().lower(),
            subject=thread.subject,
            body_text=body_text,
            body_html=text_to_html(body_text),
            follow_up_days=payload.validated_data["follow_up_days"],
            source=source,
        )
        return Response(
            EmailDraftSerializer(draft).data, status=status.HTTP_201_CREATED
        )


class EmailTemplateListCreateView(APIView):
    permission_classes = (IsAuthenticated, HasOrgContext)

    def get(self, request):
        templates = _visible_templates(request.profile)
        active = request.query_params.get("active")
        if active is not None:
            templates = templates.filter(is_active=active.lower() == "true")
        search = request.query_params.get("search")
        if search:
            templates = templates.filter(
                Q(name__icontains=search)
                | Q(description__icontains=search)
                | Q(subject__icontains=search)
            )
        return Response({"results": EmailTemplateSerializer(templates, many=True).data})

    @transaction.atomic
    def post(self, request):
        serializer = EmailTemplateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        scope = serializer.validated_data.get("scope", EmailTemplate.SCOPE_ORG)
        owner = _scope_owner(request.profile, scope)
        template = EmailTemplate.objects.create(
            org=request.profile.org,
            owner=owner,
            **serializer.validated_data,
        )
        EmailTemplateVersion.objects.create(
            org=request.profile.org,
            template=template,
            version=1,
            subject=template.subject,
            body_text=template.body_text,
        )
        return Response(
            EmailTemplateSerializer(template).data,
            status=status.HTTP_201_CREATED,
        )


class EmailTemplateDetailView(APIView):
    permission_classes = (IsAuthenticated, HasOrgContext)

    def get(self, request, pk):
        template = get_object_or_404(_visible_templates(request.profile), pk=pk)
        return Response(EmailTemplateSerializer(template).data)

    def put(self, request, pk):
        return self._update(request, pk, partial=False)

    def patch(self, request, pk):
        return self._update(request, pk, partial=True)

    @transaction.atomic
    def _update(self, request, pk, *, partial):
        template, error = _template_writable(request, pk)
        if error:
            return error
        serializer = EmailTemplateSerializer(
            template, data=request.data, partial=partial
        )
        serializer.is_valid(raise_exception=True)
        scope = serializer.validated_data.get("scope", template.scope)
        owner = _scope_owner(request.profile, scope)
        content_changed = any(
            field in serializer.validated_data
            and serializer.validated_data[field] != getattr(template, field)
            for field in ("subject", "body_text")
        )
        for field, value in serializer.validated_data.items():
            setattr(template, field, value)
        template.scope = scope
        template.owner = owner
        if content_changed:
            template.current_version += 1
        template.save()
        if content_changed:
            EmailTemplateVersion.objects.create(
                org=template.org,
                template=template,
                version=template.current_version,
                subject=template.subject,
                body_text=template.body_text,
            )
        return Response(EmailTemplateSerializer(template).data)

    def delete(self, request, pk):
        template, error = _template_writable(request, pk)
        if error:
            return error
        template.is_active = False
        template.save(update_fields=["is_active", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class EmailTemplateDuplicateView(APIView):
    permission_classes = (IsAuthenticated, HasOrgContext)

    @transaction.atomic
    def post(self, request, pk):
        source = get_object_or_404(_visible_templates(request.profile), pk=pk)
        scope = request.data.get("scope", EmailTemplate.SCOPE_PERSONAL)
        owner = _scope_owner(request.profile, scope)
        name = _unique_template_name(
            org=request.profile.org,
            scope=scope,
            owner=owner,
            requested_name=(
                request.data.get("name") or f"Kopie van {source.name}"
            ).strip(),
        )
        template = EmailTemplate.objects.create(
            org=request.profile.org,
            name=name,
            description=source.description,
            purpose=source.purpose,
            language=source.language,
            scope=scope,
            owner=owner,
            subject=source.subject,
            body_text=source.body_text,
        )
        EmailTemplateVersion.objects.create(
            org=template.org,
            template=template,
            version=1,
            subject=template.subject,
            body_text=template.body_text,
        )
        return Response(
            EmailTemplateSerializer(template).data,
            status=status.HTTP_201_CREATED,
        )


class EmailTemplatePreviewView(APIView):
    permission_classes = (IsAuthenticated, HasOrgContext)

    def post(self, request, pk):
        template = get_object_or_404(_visible_templates(request.profile), pk=pk)
        lead = get_object_or_404(
            Lead,
            pk=request.data.get("lead_id"),
            org=request.profile.org,
        )
        rendered = render_email(
            subject=template.subject,
            body_text=template.body_text,
            lead=lead,
            organization=request.profile.org,
            sender=request.profile,
        )
        return Response(
            {
                "subject": rendered.subject,
                "body_text": rendered.body_text,
                "body_html": rendered.body_html,
                "missing_variables": rendered.missing_variables,
                "unknown_variables": rendered.unknown_variables,
                "valid": rendered.valid,
            }
        )


class EmailTemplateVariableListView(APIView):
    permission_classes = (IsAuthenticated, HasOrgContext)

    def get(self, request):
        variables = [
            {"name": name, "description": description}
            for name, description in ALLOWED_VARIABLES.items()
        ]
        variables.append(
            {
                "name": "lead.custom.<field_key>",
                "description": "Een aangepast veld van de lead",
            }
        )
        return Response({"results": variables})


class LeadTemplateAssignmentListCreateView(APIView):
    permission_classes = (IsAuthenticated, HasOrgContext)

    def get(self, request, lead_id):
        get_object_or_404(Lead, pk=lead_id, org=request.profile.org)
        assignments = LeadEmailTemplateAssignment.objects.filter(
            org=request.profile.org, lead_id=lead_id
        ).select_related("template", "template__owner__user")
        return Response(
            {
                "results": LeadEmailTemplateAssignmentSerializer(
                    assignments, many=True
                ).data
            }
        )

    @transaction.atomic
    def post(self, request, lead_id):
        lead = get_object_or_404(Lead, pk=lead_id, org=request.profile.org)
        payload = LeadEmailTemplateAssignmentSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        template = get_object_or_404(
            _visible_templates(request.profile),
            pk=payload.validated_data["template_id"],
            is_active=True,
        )
        is_default = payload.validated_data.get("is_default", False)
        if is_default:
            LeadEmailTemplateAssignment.objects.filter(
                org=request.profile.org, lead=lead, is_default=True
            ).update(is_default=False)
        assignment, created = LeadEmailTemplateAssignment.objects.update_or_create(
            org=request.profile.org,
            lead=lead,
            template=template,
            defaults={"is_default": is_default},
        )
        return Response(
            LeadEmailTemplateAssignmentSerializer(assignment).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class LeadTemplateAssignmentDetailView(APIView):
    permission_classes = (IsAuthenticated, HasOrgContext)

    def delete(self, request, pk):
        assignment = get_object_or_404(
            LeadEmailTemplateAssignment, pk=pk, org=request.profile.org
        )
        assignment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class LeadDraftListCreateView(APIView):
    permission_classes = (IsAuthenticated, HasOrgContext)

    class InputSerializer(serializers.Serializer):
        mailbox_id = serializers.UUIDField()
        template_id = serializers.UUIDField(required=False, allow_null=True)
        subject = serializers.CharField(max_length=512, required=False)
        body_text = serializers.CharField(required=False)
        follow_up_days = serializers.IntegerField(
            required=False, default=5, min_value=1, max_value=30
        )

        def validate(self, attrs):
            if not attrs.get("template_id") and (
                not attrs.get("subject") or not attrs.get("body_text")
            ):
                raise serializers.ValidationError(
                    "Manual drafts require subject and body_text"
                )
            return attrs

    def get(self, request, lead_id):
        get_object_or_404(Lead, pk=lead_id, org=request.profile.org)
        drafts = EmailDraft.objects.filter(
            org=request.profile.org, lead_id=lead_id
        ).select_related("mailbox", "template_version")
        return Response({"results": EmailDraftSerializer(drafts, many=True).data})

    @transaction.atomic
    def post(self, request, lead_id):
        payload = self.InputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        lead = get_object_or_404(Lead, pk=lead_id, org=request.profile.org)
        if not lead.email:
            raise serializers.ValidationError({"lead": "Lead has no email address"})
        mailbox = get_object_or_404(
            MailboxConnection,
            pk=payload.validated_data["mailbox_id"],
            org=request.profile.org,
            is_active=True,
        )
        template_version = None
        source = EmailDraft.SOURCE_MANUAL
        if payload.validated_data.get("template_id"):
            template = get_object_or_404(
                _visible_templates(request.profile),
                pk=payload.validated_data["template_id"],
                is_active=True,
            )
            template_version = get_object_or_404(
                EmailTemplateVersion,
                org=request.profile.org,
                template=template,
                version=template.current_version,
            )
            rendered = render_email(
                subject=template_version.subject,
                body_text=template_version.body_text,
                lead=lead,
                organization=request.profile.org,
                sender=request.profile,
            )
            if not rendered.valid:
                raise serializers.ValidationError(
                    {
                        "missing_variables": rendered.missing_variables,
                        "unknown_variables": rendered.unknown_variables,
                    }
                )
            subject = rendered.subject
            body_text = rendered.body_text
            body_html = rendered.body_html
            source = EmailDraft.SOURCE_TEMPLATE
        else:
            subject = payload.validated_data["subject"].strip()
            body_text = payload.validated_data["body_text"].strip()
            body_html = text_to_html(body_text)
        draft = EmailDraft.objects.create(
            org=request.profile.org,
            lead=lead,
            mailbox=mailbox,
            template_version=template_version,
            recipient=lead.email.strip().lower(),
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            follow_up_days=payload.validated_data["follow_up_days"],
            source=source,
        )
        return Response(
            EmailDraftSerializer(draft).data, status=status.HTTP_201_CREATED
        )


class EmailDraftDetailView(APIView):
    permission_classes = (IsAuthenticated, HasOrgContext)

    def patch(self, request, pk):
        draft = get_object_or_404(EmailDraft, pk=pk, org=request.profile.org)
        if draft.status != EmailDraft.STATUS_DRAFT:
            return Response(
                {"detail": "Sent drafts are immutable"},
                status=status.HTTP_409_CONFLICT,
            )
        payload = EmailDraftSerializer(draft, data=request.data, partial=True)
        payload.is_valid(raise_exception=True)
        for field in ("subject", "body_text", "follow_up_days"):
            if field in payload.validated_data:
                setattr(draft, field, payload.validated_data[field])
        draft.body_html = text_to_html(draft.body_text)
        draft.save()
        return Response(EmailDraftSerializer(draft).data)

    def delete(self, request, pk):
        draft = get_object_or_404(EmailDraft, pk=pk, org=request.profile.org)
        if draft.status != EmailDraft.STATUS_DRAFT:
            return Response(
                {"detail": "Sent drafts are immutable"},
                status=status.HTTP_409_CONFLICT,
            )
        draft.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class EmailDraftSendView(APIView):
    permission_classes = (IsAuthenticated, HasOrgContext)

    @transaction.atomic
    def post(self, request, pk):
        idempotency_key = (
            request.headers.get("Idempotency-Key")
            or request.data.get("idempotency_key")
            or ""
        ).strip()
        if not idempotency_key or len(idempotency_key) > 128:
            raise serializers.ValidationError(
                {"idempotency_key": "A key of at most 128 characters is required"}
            )
        draft = get_object_or_404(
            EmailDraft.objects.select_for_update().select_related(
                "lead",
                "mailbox",
                "thread",
                "template_version__template",
                "sent_message",
            ),
            pk=pk,
            org=request.profile.org,
        )
        if draft.status == EmailDraft.STATUS_SENT:
            if draft.idempotency_key != idempotency_key:
                return Response(
                    {"detail": "Draft has already been sent"},
                    status=status.HTTP_409_CONFLICT,
                )
            return Response(EmailDraftSerializer(draft).data)
        if draft.recipient.lower() != (draft.lead.email or "").strip().lower():
            return Response(
                {"detail": "Lead email changed; create a new draft before sending"},
                status=status.HTTP_409_CONFLICT,
            )
        if (
            EmailDraft.objects.filter(
                org=request.profile.org, idempotency_key=idempotency_key
            )
            .exclude(pk=draft.pk)
            .exists()
        ):
            return Response(
                {"detail": "Idempotency key is already in use"},
                status=status.HTTP_409_CONFLICT,
            )
        draft.idempotency_key = idempotency_key
        draft.save(update_fields=["idempotency_key", "updated_at"])
        try:
            if draft.thread_id:
                message = reply_to_thread(
                    thread=draft.thread,
                    body_text=draft.body_text,
                    follow_up_days=draft.follow_up_days,
                )
            else:
                message = send_lead_email(
                    mailbox=draft.mailbox,
                    lead=draft.lead,
                    subject=draft.subject,
                    body_text=draft.body_text,
                    follow_up_days=draft.follow_up_days,
                )
        except ValueError as exc:
            raise serializers.ValidationError({"detail": str(exc)}) from exc
        draft.status = EmailDraft.STATUS_SENT
        draft.sent_message = message
        draft.sent_at = timezone.now()
        draft.save(update_fields=["status", "sent_message", "sent_at", "updated_at"])
        if draft.template_version_id:
            EmailTemplate.objects.filter(pk=draft.template_version.template_id).update(
                usage_count=F("usage_count") + 1
            )
        return Response(EmailDraftSerializer(draft).data)
