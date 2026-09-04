from django.contrib import admin

from communications.models import (
    EmailDraft,
    EmailSignature,
    EmailSuppression,
    EmailTemplate,
    EmailTemplateVersion,
    EmailThread,
    LeadEmailMessage,
    LeadEmailTemplateAssignment,
    MailboxConnection,
    ThreadReadState,
)


@admin.register(MailboxConnection)
class MailboxConnectionAdmin(admin.ModelAdmin):
    list_display = (
        "email_address",
        "org",
        "provider",
        "is_active",
        "last_synced_at",
    )
    exclude = ("credentials_encrypted",)


admin.site.register(EmailThread)
admin.site.register(LeadEmailMessage)
admin.site.register(EmailSuppression)
admin.site.register(EmailTemplate)
admin.site.register(EmailTemplateVersion)
admin.site.register(LeadEmailTemplateAssignment)
admin.site.register(EmailDraft)
admin.site.register(EmailSignature)
admin.site.register(ThreadReadState)
