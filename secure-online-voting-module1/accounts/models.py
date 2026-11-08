from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.utils import timezone


class VotingUserManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields["role"] = self.model.Role.SYSTEM_ADMIN
        return super().create_superuser(username, email=email, password=password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        VOTER = "VOTER", "Voter"
        ELECTION_ADMIN = "ELECTION_ADMIN", "Election administrator"
        SYSTEM_ADMIN = "SYSTEM_ADMIN", "System administrator"
        AUTHORITY = "AUTHORITY", "Election authority"

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.VOTER)
    objects = VotingUserManager()
    REQUIRED_FIELDS = ["email"]

    def __str__(self):
        return self.username


class VoterProfile(models.Model):
    class Verification(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="voter_profile")
    institutional_id = models.CharField(max_length=30, unique=True)
    department = models.CharField(max_length=100, blank=True)
    # NULL is required for existing voters who registered before the DOB feature.
    date_of_birth = models.DateField(null=True, blank=True)
    verification_status = models.CharField(
        max_length=10, choices=Verification.choices, default=Verification.PENDING
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name="reviewed_profiles", null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def identity_approved(self):
        return self.user.is_active and self.verification_status == self.Verification.APPROVED

    def age_on(self, on_date=None):
        """Age in complete years at local date; None if DOB has not been provided."""
        if self.date_of_birth is None:
            return None
        on_date = on_date or timezone.localdate()
        dob = self.date_of_birth
        return on_date.year - dob.year - ((on_date.month, on_date.day) < (dob.month, dob.day))

    @property
    def age(self):
        return self.age_on()

    def meets_age_requirement(self, on_date=None):
        age = self.age_on(on_date)
        return age is not None and age >= 18

    @property
    def can_vote(self):
        """Basic account clearance only. Module 2 must additionally check election rules."""
        from .email_otp import email_is_verified
        return self.identity_approved and self.meets_age_requirement() and email_is_verified(self.user)

    def __str__(self):
        return f"{self.institutional_id} ({self.user.username})"


class EmailVerification(models.Model):
    """Proof that the current email address is owned by this user."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="email_verification")
    verified_email = models.EmailField(blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)


class EmailOTPChallenge(models.Model):
    """Single outstanding code per user and purpose. OTP plaintext is never stored."""
    class Purpose(models.TextChoices):
        VERIFY_EMAIL = "VERIFY", "Email ownership verification"
        LOGIN = "LOGIN", "Sign-in verification"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="email_challenges")
    purpose = models.CharField(max_length=10, choices=Purpose.choices)
    nonce = models.CharField(max_length=32, blank=True)
    code_digest = models.CharField(max_length=64, blank=True)
    session_binding = models.CharField(max_length=64, blank=True)
    expires_at = models.DateTimeField()
    failed_attempts = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    last_sent_at = models.DateTimeField(null=True, blank=True)
    sent_in_hour = models.PositiveSmallIntegerField(default=0)
    hour_started_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "purpose"], name="one_email_challenge_per_purpose")
        ]


class SecurityEvent(models.Model):
    """Minimal security audit trail; tamper-evident signing is a Module 3 goal."""
    class Type(models.TextChoices):
        EMAIL_CODE_SENT = "EMAIL_CODE_SENT", "Email verification code sent"
        EMAIL_VERIFIED = "EMAIL_VERIFIED", "Email verified"
        LOGIN_SUCCESS = "LOGIN_SUCCESS", "Login successful"
        LOGIN_FAILURE = "LOGIN_FAILURE", "Login failed"
        LOGOUT = "LOGOUT", "Logout"
        MFA_ENROLLED = "MFA_ENROLLED", "MFA enrolled"
        MFA_FAILURE = "MFA_FAILURE", "MFA failed"
        MFA_SUCCESS = "MFA_SUCCESS", "MFA verified"
        ACCESS_DENIED = "ACCESS_DENIED", "Access denied"
        VOTER_APPROVED = "VOTER_APPROVED", "Voter approved"
        VOTER_REJECTED = "VOTER_REJECTED", "Voter rejected"
        PROFILE_UPDATED = "PROFILE_UPDATED", "Profile updated"
        PASSWORD_CHANGED = "PASSWORD_CHANGED", "Password changed"
        PASSWORD_RESET_REQUEST = "PASSWORD_RESET_REQ", "Password recovery requested"
        PASSWORD_RESET_DONE = "PASSWORD_RESET_DONE", "Password recovered"
        NEW_SIGNIN_CONTEXT = "NEW_SIGNIN_CONTEXT", "New sign-in context"

    event_type = models.CharField(max_length=30, choices=Type.choices, db_index=True)
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                              blank=True, related_name="security_events")
    target_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                    blank=True, related_name="targeted_security_events")
    details = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    device_summary = models.CharField(max_length=80, blank=True)
    context_hash = models.CharField(max_length=64, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.event_type} at {self.created_at}"
