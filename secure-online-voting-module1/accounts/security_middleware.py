"""Require email verification + email OTP for ALL users and Django admin.

Old pre-upgrade sessions are invalidated once, on their first next request.
"""
from django.contrib.auth import logout
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import reverse

from .email_otp import email_login_passed
from .models import User


class EmailMFAMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # The built-in /admin/login/ MUST NOT bypass the password + email OTP flow.
        if request.path.startswith(reverse("admin:index").rstrip("/") + "/"):
            if not email_login_passed(request):
                if request.user.is_authenticated:
                    logout(request)
                return redirect("accounts:login")
            if request.user.role == User.Role.VOTER or not (
                request.user.is_superuser
                or (
                    request.user.is_staff
                    and request.user.role in {
                        User.Role.SYSTEM_ADMIN,
                        User.Role.ELECTION_ADMIN,
                    }
                )
            ):
                return HttpResponseForbidden("You are not authorized to access the admin site.")
        if request.user.is_authenticated and not email_login_passed(request):
            logout(request)
            return redirect("accounts:login")
        return self.get_response(request)
