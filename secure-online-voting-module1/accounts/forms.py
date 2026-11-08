import re
from datetime import date

from django.utils import timezone

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction
from .models import User, VoterProfile


def validate_date_of_birth(value):
    """Validate a real birth date; under-18 voters may register but cannot vote."""
    if value > timezone.localdate():
        raise forms.ValidationError("Date of birth cannot be in the future.")
    # Avoid mistaken extreme dates in our academic prototype.
    if value.year < timezone.localdate().year - 120:
        raise forms.ValidationError("Please enter a valid date of birth.")
    return value


class VoterRegistrationForm(UserCreationForm):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    institutional_id = forms.CharField(max_length=30, help_text="Your university/club ID")
    department = forms.CharField(max_length=100, required=False)
    date_of_birth = forms.DateField(
        label="Date of birth", widget=forms.DateInput(attrs={"type": "date"}),
        help_text="You must be at least 18 years old to vote."
    )

    def clean_date_of_birth(self):
        return validate_date_of_birth(self.cleaned_data["date_of_birth"])

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email", "institutional_id", "department", "date_of_birth", "password1", "password2")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("This email is already registered.")
        return email

    def clean_institutional_id(self):
        value = self.cleaned_data["institutional_id"].strip().upper()
        if not re.fullmatch(r"[A-Z0-9-]{3,30}", value):
            raise forms.ValidationError("Use 3-30 letters, numbers or hyphens.")
        if VoterProfile.objects.filter(institutional_id=value).exists():
            raise forms.ValidationError("This ID is already registered.")
        return value

    @transaction.atomic
    def save(self, commit=True):
        if not commit:
            raise ValueError("Registration requires commit=True")
        user = super().save(commit=False)
        user.role = User.Role.VOTER  # Never accept the role from a public form.
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.save()
        VoterProfile.objects.create(
            user=user,
            institutional_id=self.cleaned_data["institutional_id"],
            department=self.cleaned_data["department"],
            date_of_birth=self.cleaned_data["date_of_birth"],
        )
        return user


class VoterProfileEditForm(forms.Form):
    """Edit only a few identity fields; re-approval is required after a change."""

    first_name = forms.CharField(max_length=150, label="First name")
    last_name = forms.CharField(max_length=150, label="Last name")
    department = forms.CharField(max_length=100, required=False, label="Department")
    date_of_birth = forms.DateField(
        label="Date of birth", widget=forms.DateInput(attrs={"type": "date"}),
        help_text="Date of birth is required. Changing it requires another approval."
    )

    def clean_date_of_birth(self):
        return validate_date_of_birth(self.cleaned_data["date_of_birth"])

    def clean_first_name(self):
        return self.cleaned_data["first_name"].strip()

    def clean_last_name(self):
        return self.cleaned_data["last_name"].strip()

    def clean_department(self):
        return self.cleaned_data["department"].strip()
