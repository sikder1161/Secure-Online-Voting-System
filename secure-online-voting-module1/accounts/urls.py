from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy
from . import views, security_views, email_views, password_recovery

app_name = "accounts"
urlpatterns = [
    path("register/", views.register, name="register"),
    path("login/", email_views.PasswordThenEmailLoginView.as_view(), name="login"),
    path("email/verify/", email_views.verification_code, name="verify_email"),
    path("email/login-code/", email_views.verification_code, name="verify_login_email"),
    path("email/resend/", email_views.resend_email_code, name="resend_email_code"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("profile/edit/", views.edit_profile, name="edit_profile"),
    path("password/change/", security_views.AuditedPasswordChangeView.as_view(
        template_name="accounts/change_password.html",
        success_url=reverse_lazy("accounts:password_change_done"),
    ), name="password_change"),
    path("password/change/done/", auth_views.PasswordChangeDoneView.as_view(
        template_name="accounts/password_change_done.html"
    ), name="password_change_done"),
    path("staff/voters/", views.voter_list, name="voter_list"),
    path("staff/voters/<int:pk>/review/", views.review_voter, name="review_voter"),
    path("security/events/", security_views.security_dashboard, name="security_dashboard"),
    path("security/activity/", security_views.account_activity, name="account_activity"),
    path("password/reset/", password_recovery.SecurePasswordResetView.as_view(), name="password_reset"),
    path("password/reset/sent/", auth_views.PasswordResetDoneView.as_view(
        template_name="accounts/password_reset_done.html"), name="password_reset_done"),
    path("password/reset/<uidb64>/<token>/", password_recovery.SecurePasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("password/reset/complete/", auth_views.PasswordResetCompleteView.as_view(
        template_name="accounts/password_reset_complete.html"), name="password_reset_complete"),
]
