"""Security monitoring and auditing. OTP logic is in email_views.py."""
from datetime import timedelta

from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.shortcuts import render
from django.utils import timezone

from .models import SecurityEvent
from .signals import log_event
from .views import is_verification_staff


@login_required
def security_dashboard(request):
    if not is_verification_staff(request.user):
        log_event(SecurityEvent.Type.ACCESS_DENIED, actor=request.user, action="security_dashboard", request=request)
        raise PermissionDenied("Security overview is restricted to authorized staff.")
    cutoff = timezone.now() - timedelta(days=7)
    recent = SecurityEvent.objects.select_related("actor", "target_user")[:50]
    totals = {
        x["event_type"]: x["total"]
        for x in SecurityEvent.objects.filter(created_at__gte=cutoff)
        .values("event_type").annotate(total=Count("id"))
    }
    return render(request, "accounts/security_dashboard.html", {
        "recent_events": recent,
        "failed_logins": totals.get(SecurityEvent.Type.LOGIN_FAILURE, 0),
        "failed_mfa": totals.get(SecurityEvent.Type.MFA_FAILURE, 0),
        "denied_access": totals.get(SecurityEvent.Type.ACCESS_DENIED, 0),
        "approved_events": totals.get(SecurityEvent.Type.VOTER_APPROVED, 0),
    })


@login_required
def account_activity(request):
    """A user sees their own events; other users' events are never exposed."""
    user = request.user
    events = SecurityEvent.objects.filter(
        Q(actor=user) | Q(target_user=user)
    ).order_by('-created_at', '-id')[:40]
    last_success = (SecurityEvent.objects.filter(
        actor=user, event_type=SecurityEvent.Type.LOGIN_SUCCESS
    ).order_by('-created_at').first())
    recent_failures = SecurityEvent.objects.filter(
        Q(actor=user) | Q(target_user=user),
        event_type__in=[SecurityEvent.Type.LOGIN_FAILURE, SecurityEvent.Type.MFA_FAILURE]
    ).count()
    return render(request, 'accounts/account_activity.html', {
        'events': events,
        'last_success': last_success,
        'recent_failures': recent_failures,
    })


class AuditedPasswordChangeView(auth_views.PasswordChangeView):
    def form_valid(self, form):
        response = super().form_valid(form)
        from .models import EmailOTPChallenge
        EmailOTPChallenge.objects.filter(user=self.request.user).delete()
        log_event(SecurityEvent.Type.PASSWORD_CHANGED, actor=self.request.user,
                  request=self.request)
        # Django's PasswordChangeView deliberately preserves *this* authenticated
        # session via update_session_auth_hash. Other sessions are invalidated.
        return response
