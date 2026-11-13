from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("resend-verification/", views.resend_verification_view, name="resend_verification"),
    path("verify/<str:token>/", views.verify_email_view, name="verify_email"),
    path("profile/", views.profile_view, name="profile"),
    path("change-password/", views.change_password_view, name="change_password"),
    path("users/", views.user_list_view, name="user_list"),
    path("users/new/", views.user_create_view, name="user_create"),
    path("users/<int:pk>/edit/", views.user_edit_view, name="user_edit"),
    path("users/<int:pk>/toggle-active/", views.user_toggle_active_view, name="user_toggle_active"),
]
