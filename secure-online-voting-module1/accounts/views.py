from functools import wraps

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import VoterRegistrationForm, VoterProfileEditForm
from .email_otp import email_is_verified, issue_code
from .models import EmailOTPChallenge
from .models import VoterProfile, SecurityEvent
from .signals import log_event

User = get_user_model()


def home(request):
    return redirect("accounts:dashboard" if request.user.is_authenticated else "accounts:login")


def register(request):
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")
    if request.method == "POST":
        form = VoterRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            status = issue_code(request, user, EmailOTPChallenge.Purpose.VERIFY_EMAIL)
            if status == "sent":
                messages.success(request, "Account created. Check your email for a verification code.")
                return redirect("accounts:verify_email")
            messages.warning(request, "Account created, but we could not send a code. Set up email delivery, then sign in to request verification.")
            return redirect("accounts:login")
    else:
        form = VoterRegistrationForm()
    return render(request, "accounts/register.html", {"form": form})


def is_verification_staff(user):
    return user.is_superuser or (
        user.is_staff and user.role in {User.Role.SYSTEM_ADMIN, User.Role.ELECTION_ADMIN}
    )


def verification_staff_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapped(request, *args, **kwargs):
        if not is_verification_staff(request.user):
            log_event(SecurityEvent.Type.ACCESS_DENIED, actor=request.user, action="voter_management", request=request)
            raise PermissionDenied("You are not authorized to verify voters.")
        return view_func(request, *args, **kwargs)
    return wrapped


@login_required
def dashboard(request):
    if is_verification_staff(request.user):
        pending_count = VoterProfile.objects.filter(
            verification_status=VoterProfile.Verification.PENDING
        ).count()
        return render(request, "accounts/admin_dashboard.html", {
            "pending_count": pending_count,
            "total_voters": VoterProfile.objects.count(),
            "approved_count": VoterProfile.objects.filter(
                verification_status=VoterProfile.Verification.APPROVED
            ).count(),
            "rejected_count": VoterProfile.objects.filter(
                verification_status=VoterProfile.Verification.REJECTED
            ).count(),
            "recent_pending": VoterProfile.objects.select_related("user").filter(
                verification_status=VoterProfile.Verification.PENDING
            ).order_by("-created_at")[:5],
        })

    profile = None
    if request.user.role == User.Role.VOTER:
        profile = VoterProfile.objects.filter(user=request.user).first()
    return render(request, "accounts/voter_dashboard.html", {"profile": profile})


@login_required
def edit_profile(request):
    """Keep voter identity changes auditable through repeat administrator review."""
    if request.user.role != User.Role.VOTER or request.user.is_staff:
        raise PermissionDenied("Only voters can edit voter profiles here.")

    profile = get_object_or_404(VoterProfile, user=request.user)
    if request.method == "POST":
        form = VoterProfileEditForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                # The row lock protects the approval state from concurrent edits.
                profile = VoterProfile.objects.select_for_update().get(pk=profile.pk)
                user = User.objects.select_for_update().get(pk=request.user.pk)
                first_name = form.cleaned_data["first_name"]
                last_name = form.cleaned_data["last_name"]
                department = form.cleaned_data["department"]
                date_of_birth = form.cleaned_data["date_of_birth"]
                changed = (
                    user.first_name != first_name
                    or user.last_name != last_name
                    or profile.department != department
                    or profile.date_of_birth != date_of_birth
                )
                if changed:
                    user.first_name = first_name
                    user.last_name = last_name
                    user.save(update_fields=["first_name", "last_name"])
                    profile.department = department
                    profile.date_of_birth = date_of_birth
                    profile.verification_status = VoterProfile.Verification.PENDING
                    profile.reviewed_at = None
                    profile.reviewed_by = None
                    profile.save(update_fields=[
                        "department", "date_of_birth", "verification_status", "reviewed_at", "reviewed_by"
                    ])
            if changed:
                log_event(SecurityEvent.Type.PROFILE_UPDATED, actor=request.user, request=request)
                messages.warning(
                    request, "Profile updated. Your identity approval is now pending a new review."
                )
            else:
                messages.info(request, "No profile information was changed.")
            return redirect("accounts:dashboard")
    else:
        form = VoterProfileEditForm(initial={
            "first_name": request.user.first_name,
            "last_name": request.user.last_name,
            "department": profile.department,
            "date_of_birth": profile.date_of_birth,
        })
    return render(request, "accounts/edit_profile.html", {"form": form, "profile": profile})


@verification_staff_required
def voter_list(request):
    status = request.GET.get("status", "PENDING").upper()
    allowed = {choice for choice, _ in VoterProfile.Verification.choices}
    if status not in allowed and status != "ALL":
        status = "PENDING"
    queryset = VoterProfile.objects.select_related("user", "reviewed_by").order_by("-created_at")
    if status != "ALL":
        queryset = queryset.filter(verification_status=status)
    return render(request, "accounts/voter_list.html", {"profiles": queryset, "status_filter": status})


@require_POST
@verification_staff_required
@transaction.atomic
def review_voter(request, pk):
    action = request.POST.get("decision")
    if action not in {VoterProfile.Verification.APPROVED, VoterProfile.Verification.REJECTED}:
        messages.error(request, "Invalid decision.")
        return redirect("accounts:voter_list")
    profile = get_object_or_404(VoterProfile.objects.select_for_update(), pk=pk)
    if profile.user.role != User.Role.VOTER:
        raise PermissionDenied("Only voter profiles can be reviewed.")
    if action == VoterProfile.Verification.APPROVED and not email_is_verified(profile.user):
        messages.error(request, "Cannot approve: voter must verify their email first.")
        return redirect("accounts:voter_list")
    if action == VoterProfile.Verification.APPROVED and not profile.meets_age_requirement():
        messages.error(
            request,
            "Cannot approve: voter must have a verified date of birth and be at least 18 years old."
        )
        return redirect("accounts:voter_list")
    profile.verification_status = action
    profile.reviewed_at = timezone.now()
    profile.reviewed_by = request.user
    profile.save(update_fields=["verification_status", "reviewed_at", "reviewed_by"])
    log_event(
        SecurityEvent.Type.VOTER_APPROVED if action == "APPROVED" else SecurityEvent.Type.VOTER_REJECTED,
        actor=request.user, target_id=profile.user_id, request=request,
    )
    messages.success(request, f"Voter {profile.institutional_id}: {profile.get_verification_status_display()}.")
    return redirect("accounts:voter_list")
