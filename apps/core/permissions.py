"""
Role-based access control in one place.

Usage on a view:

    @role_required("admin", "manager")
    def my_view(request): ...

Anonymous users go to the login page; logged-in users with the wrong role
get a 403 page. Keeping this in ONE file means a student can read the whole
security policy of the site in a minute.
"""
from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

STAFF_ROLES = ("admin", "manager")


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if request.user.role not in roles:
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


staff_required = role_required(*STAFF_ROLES)
worker_or_staff_required = role_required("admin", "manager", "worker")
customer_required = role_required("customer")
