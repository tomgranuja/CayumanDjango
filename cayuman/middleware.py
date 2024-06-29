from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from django.urls import resolve
from django.utils.translation import gettext as _

from cayuman.models import Period


class PeriodMiddleware:
    """
    Django middleware to fill several properties and do checks related to periods
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Resolve the current path to access URL kwargs
        if "/admin/" in request.path_info or "/login/" in request.path_info:
            # do nothing in django admin
            response = self.get_response(request)
            return response

        resolved = resolve(request.path_info)
        period_id = resolved.kwargs.get("period_id")

        # If period_id is found, try to set it to the specific Period
        if period_id:
            try:
                request.period = Period.objects.get(pk=period_id)
            except ObjectDoesNotExist:
                raise Http404
        else:
            # if not period_id then fill with current or last period
            request.period = Period.objects.current_or_last()

        # Now get list of other periods (using cached method)
        request.other_periods = Period.objects.other_periods(request.period)

        msg = None
        if request.period.is_in_the_past():
            msg = _("The period you are viewing has already ended. To choose a more recent one use the dropdown menu in the navbar.")
        elif request.period.is_in_the_future():
            msg = _("The period you are viewing is not yet open. Please come back later or choose another one from the dropdown menu in the navbar.")

        if msg and msg not in [msg.message for msg in messages.get_messages(request)]:
            messages.warning(request, msg)

        # Continue processing the request
        response = self.get_response(request)
        return response
