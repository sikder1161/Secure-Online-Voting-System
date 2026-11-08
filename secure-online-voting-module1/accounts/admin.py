from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, VoterProfile


@admin.register(User)
class VotingUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("Voting system", {"fields": ("role",)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("Voting system", {"fields": ("email", "role")}),)
    list_display = ("username", "email", "role", "is_staff", "is_superuser")
    list_filter = UserAdmin.list_filter + ("role",)


@admin.register(VoterProfile)
class VoterProfileAdmin(admin.ModelAdmin):
    list_display = ("institutional_id", "user", "date_of_birth", "verification_status", "reviewed_by", "reviewed_at")
    list_filter = ("verification_status",)
    search_fields = ("institutional_id", "user__username", "user__email")
    readonly_fields = ("reviewed_at", "reviewed_by", "date_of_birth")

    def get_readonly_fields(self, request, obj=None):
        # Verification decisions should happen through the staff review screen.
        return self.readonly_fields + ("verification_status",)

from .models import SecurityEvent, EmailVerification, EmailOTPChallenge


@admin.register(SecurityEvent)
class SecurityEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "event_type", "actor", "target_user")
    list_filter = ("event_type", "created_at")
    readonly_fields = ("event_type", "actor", "target_user", "details", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(EmailVerification)
class EmailVerificationAdmin(admin.ModelAdmin):
    list_display = ("user", "verified_email", "verified_at")
    readonly_fields = ("user", "verified_email", "verified_at")
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(EmailOTPChallenge)
class EmailOTPChallengeAdmin(admin.ModelAdmin):
    list_display = ("user", "purpose", "expires_at", "failed_attempts", "locked_until")
    readonly_fields = ("user", "purpose", "expires_at", "failed_attempts", "locked_until", "sent_in_hour")
    exclude = ("code_digest", "nonce", "session_binding")
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False
