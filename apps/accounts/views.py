from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.core.permissions import role_required

from . import services
from .forms import (
    LoginForm,
    PasswordChangeBootstrapForm,
    ProfileForm,
    StaffUserCreateForm,
    StaffUserEditForm,
)

User = get_user_model()
admin_only = role_required("admin")


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard:home")
    form = LoginForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        next_url = request.POST.get("next") or request.GET.get("next") or ""
        # Only follow `next` if it points back to OUR site (prevents open-redirect attacks).
        if next_url and url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ):
            return redirect(next_url)
        return redirect("dashboard:home")
    if request.method == "POST":
        # Inactive + correct password usually means "email not verified yet".
        user = User.objects.filter(username=request.POST.get("username", "")).first()
        if user and not user.is_active and user.is_customer and user.check_password(
            request.POST.get("password", "")
        ):
            messages.warning(request, "Please verify your email first. Check your inbox.")
    return render(request, "accounts/login.html", {"form": form, "next": request.GET.get("next", "")})


@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("dashboard:landing")


def verify_email_view(request, token):
    user = services.verify_email(token)
    if user:
        messages.success(request, "Email verified! You can log in now.")
        return redirect("accounts:login")
    messages.error(request, "That verification link is invalid or has expired.")
    return redirect("accounts:resend_verification")


def resend_verification_view(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        user = User.objects.filter(email__iexact=email, is_active=False, role="customer").first()
        if user:
            services.send_verification_email(request, user)
        # Same message either way so attackers cannot discover which emails exist.
        messages.info(request, "If an unverified account exists, a new link has been sent.")
        return redirect("accounts:login")
    return render(request, "accounts/resend_verification.html")


@login_required
def profile_view(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile updated.")
        return redirect("accounts:profile")
    return render(request, "accounts/profile.html", {"form": form})


@login_required
def change_password_view(request):
    form = PasswordChangeBootstrapForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)  # keep the user logged in
        messages.success(request, "Password changed.")
        return redirect("accounts:profile")
    return render(request, "accounts/change_password.html", {"form": form})


# ---------------------------------------------------------------- user management (admin)
@admin_only
def user_list_view(request):
    users = User.objects.all()
    role = request.GET.get("role")
    if role:
        users = users.filter(role=role)
    page = Paginator(users, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "accounts/user_list.html",
        {"page": page, "roles": User.Role.choices, "current_role": role},
    )


@admin_only
def user_create_view(request):
    form = StaffUserCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        _sync_role_profiles(user)
        messages.success(request, f"User {user} created.")
        return redirect("accounts:user_list")
    return render(request, "accounts/user_form.html", {"form": form, "title": "New user"})


@admin_only
def user_edit_view(request, pk):
    user = get_object_or_404(User, pk=pk)
    form = StaffUserEditForm(request.POST or None, instance=user)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        _sync_role_profiles(user)
        messages.success(request, "User updated.")
        return redirect("accounts:user_list")
    return render(request, "accounts/user_form.html", {"form": form, "title": f"Edit {user}"})


@admin_only
@require_POST
def user_toggle_active_view(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user == request.user:
        messages.error(request, "You cannot deactivate your own account.")
    else:
        user.is_active = not user.is_active
        user.save(update_fields=["is_active"])
        messages.success(request, f"{user} is now {'active' if user.is_active else 'inactive'}.")
    return redirect("accounts:user_list")


def _sync_role_profiles(user):
    """Workers need a WorkerProfile; customers need a Customer record."""
    if user.role == User.Role.WORKER:
        from apps.workforce.services import ensure_worker_profile

        ensure_worker_profile(user)
    elif user.role == User.Role.CUSTOMER:
        from apps.customers.services import ensure_customer_for_user

        ensure_customer_for_user(user)
