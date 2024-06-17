from functools import wraps

from django.http import HttpResponseRedirect
from django.urls import reverse_lazy as reverse


def student_required(view_func):
    """Decorator to ensure a view counts with a valid active student"""
    from cayuman.models import Member

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        try:
            member = Member.objects.get(id=request.user.id)
            if not member.is_student or not member.is_active:
                return HttpResponseRedirect(reverse("admin:login"))

            request.member = member
        except Member.DoesNotExist:
            return HttpResponseRedirect(reverse("login"))

        return view_func(request, *args, **kwargs)

    return _wrapped_view


def studentcycle_required(view_func):
    """Decorator to ensure a view counts with a valid active studentcycle"""
    from django.utils.translation import gettext as _
    from django.contrib import messages

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        student_cycle = request.member.current_student_cycle
        if not student_cycle:
            messages.warning(request, _("Your student account is not associated with any Cycle. Please ask your teachers to fix this."))
            return HttpResponseRedirect(reverse("workshop_periods", kwargs={"period_id": request.period.id}))

        return view_func(request, *args, **kwargs)

    return _wrapped_view
