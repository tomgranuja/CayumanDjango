from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from django.urls import resolve

from cayuman.models import Period


class PeriodMiddleware:
    """
    Django middleware to fill the `request.period` attribute
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Resolve the current path to access URL kwargs
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
            request.period = Period.objects.current() or Period.objects.last()

        # Continue processing the request
        response = self.get_response(request)
        return response
