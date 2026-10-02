from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.debug import sensitive_post_parameters

from .forms import LoginForm, PreferencesForm, ProfileForm, SignUpForm, UserNameForm


@sensitive_post_parameters("password1", "password2")
def signup(request):
    if request.user.is_authenticated:
        return redirect("dashboard:home")
    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user, backend="accounts.backends.EmailOrUsernameBackend")
        messages.success(request, f"Welcome to PrepAI, {user.display_name}!")
        next_url = request.POST.get("next") or request.GET.get("next")
        if next_url and url_has_allowed_host_and_scheme(next_url, {request.get_host()},
                                                        require_https=request.is_secure()):
            return redirect(next_url)
        return redirect("dashboard:home")
    return render(request, "accounts/signup.html", {"form": form})


class LoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


@login_required
def profile(request):
    return render(request, "accounts/profile.html", {"profile": request.user.profile})


@login_required
def profile_edit(request):
    profile = request.user.profile
    user_form = UserNameForm(request.POST or None, instance=request.user)
    profile_form = ProfileForm(request.POST or None, request.FILES or None, instance=profile)
    if request.method == "POST" and user_form.is_valid() and profile_form.is_valid():
        user_form.save()
        profile_form.save()
        messages.success(request, "Your profile has been updated.")
        return redirect("accounts:profile")
    return render(request, "accounts/profile_edit.html",
                  {"user_form": user_form, "profile_form": profile_form})


@login_required
def preferences(request):
    form = PreferencesForm(request.POST or None, instance=request.user.profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Preferences saved.")
        return redirect("accounts:preferences")
    return render(request, "accounts/preferences.html", {"form": form})


class PasswordChangeView(auth_views.PasswordChangeView):
    template_name = "accounts/password_change_form.html"
    success_url = reverse_lazy("accounts:password_change_done")

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for field in form.fields.values():
            field.widget.attrs["class"] = "form-control"
        return form


class PasswordResetView(auth_views.PasswordResetView):
    template_name = "accounts/password_reset_form.html"
    email_template_name = "accounts/emails/password_reset_email.txt"
    subject_template_name = "accounts/emails/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password_reset_done")

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["email"].widget.attrs["class"] = "form-control"
        return form


class PasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"
    success_url = reverse_lazy("accounts:password_reset_complete")

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for field in form.fields.values():
            field.widget.attrs["class"] = "form-control"
        return form
