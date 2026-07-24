from django.contrib import admin

from communications.models import (
    EmailSuppression,
    EmailThread,
    LeadEmailMessage,
    MailboxConnection,
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
