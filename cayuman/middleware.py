import threading

from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from django.urls import resolve
from django.utils.translation import gettext as _

# Crear un objeto local para hilos
_thread_locals = threading.local()


def get_current_request():
    """
    Obtener la request actual almacenada en el espacio de almacenamiento local del hilo.
    Si no hay request almacenada, retorna None.
    """
    return getattr(_thread_locals, "request", None)


class ThreadLocalMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Almacenar la request actual en el espacio de almacenamiento local del hilo
        _thread_locals.request = request
        response = self.get_response(request)
        # Limpiar la request del almacenamiento local del hilo al finalizar la respuesta
        return response


class CayumanMiddleware:
    """
    Django middleware to fill several properties and do checks related to periods
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from cayuman.models import Period, Member

        # Resolve the current path to access URL kwargs
        if "/admin/" in request.path_info:
            # do nothing in django admin
            response = self.get_response(request)
            return response

        request.member = None  # default

        # Fill period
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

        # Add warnings if period is no longer active
        msg = None
        if request.period.is_in_the_past():
            msg = _("The period you are viewing has already ended. To choose a more recent one use the dropdown menu in the navbar.")
        elif request.period.is_in_the_future():
            msg = _("The period you are viewing is not yet open. Please come back later or choose another one from the dropdown menu in the navbar.")
        if msg and msg not in [msg.message for msg in messages.get_messages(request)]:
            messages.warning(request, msg)

        # Fill member if logged in
        if request.user.is_authenticated and request.user.is_active:
            request.member = Member.objects.get(id=request.user.id)
            if request.impersonator:
                request.member.is_impersonate = request.user.is_impersonate
                request.impersonator = Member.objects.get(id=request.impersonator.id)
            else:
                request.member.is_impersonate = False

        # Continue processing the request
        response = self.get_response(request)
        return response
