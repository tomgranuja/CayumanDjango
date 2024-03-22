from functools import wraps

from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse_lazy as reverse

from .models import Member
from .models import Period


def period_required(view_func):
    """Decorator to ensure a view counts with a valid active Period"""

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        current_period = Period.objects.current()
        if not current_period:
            return render(request, "no-period.html", status=404)

        request.current_period = current_period

        return view_func(request, *args, **kwargs)

    return _wrapped_view


def student_required(view_func):
    """Decorator to ensure a view counts with a valid active student"""

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        try:
            member = Member.objects.get(id=request.user.id)
            if not member.is_student or not member.is_active:
                return HttpResponseRedirect(reverse("admin:login"))

            request.current_member = member
        except Member.DoesNotExist:
            return HttpResponseRedirect(reverse("login"))

        return view_func(request, *args, **kwargs)

    return _wrapped_view
