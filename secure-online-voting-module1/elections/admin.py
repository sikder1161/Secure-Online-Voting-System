from django.contrib import admin
from .models import Election, Candidate, VoterEligibility, VoterParticipation, EncryptedVote

# Manage through role-protected election views instead of permitting sensitive votes
# to be inspected or modified using Django's broad superuser admin tools.
@admin.register(Election)
class ElectionAdmin(admin.ModelAdmin):
    list_display = ('title', 'starts_at', 'ends_at', 'status')
    readonly_fields = ('created_by', 'created_at')
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
