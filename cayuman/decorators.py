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


def enrollment_access_required(view_func):
    """Decorator protecting enrollment view"""
    from django.utils.translation import gettext as _
    from django.contrib import messages

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.impersonator:
            return view_func(request, *args, **kwargs)

        student_cycle = request.member.current_student_cycle

        # check if student is enabled to enroll, otherwise redirect to weekly-schedule with a warning message
        if request.period.is_enabled_to_enroll():
            if not student_cycle.is_enabled_to_enroll(request.period):
                messages.warning(
                    request, _("Online enrollment is no longer enabled. If you need to change your workshops please contact your teachers.")
                )
                return HttpResponseRedirect(reverse("weekly_schedule", kwargs={"period_id": request.period.id}))
        else:
            # Go back to workshop periods and no feedback as it will be handled by the middleware
            if request.period.is_in_the_past():
                return HttpResponseRedirect(reverse("weekly_schedule", kwargs={"period_id": request.period.id}))
            else:
                return HttpResponseRedirect(reverse("workshop_periods", kwargs={"period_id": request.period.id}))

        if not request.GET.get("force") and student_cycle.is_schedule_full(request.period):
            return HttpResponseRedirect(reverse("weekly_schedule", kwargs={"period_id": request.period.id}))

        return view_func(request, *args, **kwargs)

    return _wrapped_view
