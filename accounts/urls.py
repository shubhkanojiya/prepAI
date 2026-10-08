from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .ratelimit import rate_limit

# Per-IP limits: failed logins, sign-ups and reset emails (see accounts/ratelimit.py).
login_limit = rate_limit("login", limit=10, window=15 * 60, failures_only=True)
signup_limit = rate_limit("signup", limit=10, window=60 * 60)
reset_limit = rate_limit("password_reset", limit=5, window=60 * 60)

app_name = "accounts"

urlpatterns = [
    path("signup/", signup_limit(views.signup), name="signup"),
    path("login/", login_limit(views.LoginView.as_view()), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("profile/", views.profile, name="profile"),
    path("profile/edit/", views.profile_edit, name="profile_edit"),
    path("preferences/", views.preferences, name="preferences"),
    path("password/change/", views.PasswordChangeView.as_view(), name="password_change"),
    path("password/change/done/",
         auth_views.PasswordChangeDoneView.as_view(template_name="accounts/password_change_done.html"),
         name="password_change_done"),
    path("password/reset/", reset_limit(views.PasswordResetView.as_view()), name="password_reset"),
    path("password/reset/done/",
         auth_views.PasswordResetDoneView.as_view(template_name="accounts/password_reset_done.html"),
         name="password_reset_done"),
    path("reset/<uidb64>/<token>/", views.PasswordResetConfirmView.as_view(),
         name="password_reset_confirm"),
    path("reset/done/",
         auth_views.PasswordResetCompleteView.as_view(
             template_name="accounts/password_reset_complete.html"),
         name="password_reset_complete"),
]
