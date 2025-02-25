from typing import Callable

from cayuman.models import Member
from cayuman.models import Period

# dict to keep track of custom permissions
custom_permissions = {}


def register_permission(name: str) -> Callable:
    """
    Decorator to register a custom permission.
    """

    def decorator(func: Callable):
        custom_permissions[name] = func
        return func

    return decorator


@register_permission("cayuman.can_enroll")
def can_enroll(user: Member, obj: Period = None) -> bool:
    """
    Check if the user can enroll in the given period.
    """
    if obj is None:
        return False

    # if not obj.is_current():
    #    return False

    if not user.is_student:
        return False

    student_cycle = user.current_student_cycle
    if not student_cycle:
        return False

    # remember that impersonators (i.e. superadmins) can enroll in any moment during the period
    if hasattr(user, "impersonator") and hasattr(user, "is_impersonate"):
        if user.is_impersonate and user.impersonator.is_enabled_to_enroll(obj):
            return True

    return obj.is_enabled_to_enroll() and student_cycle.is_enabled_to_enroll(obj)


def can_impersonate(request):
    """
    Custom permission function for django-impersonate.
    Only superusers can impersonate other users.
    """
    return request.user.is_superuser
