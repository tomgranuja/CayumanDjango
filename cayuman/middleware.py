import threading

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from django.shortcuts import redirect
from django.urls import resolve
from django.urls import Resolver404
from django.urls import reverse
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

        # Set member by default if user is authenticated and active
        request.member = None
        if request.user.is_authenticated and request.user.is_active:
            try:
                request.member = Member.objects.get(id=request.user.id)
            except Member.DoesNotExist:
                pass

        # Handle impersonation for all paths
        if request.member and getattr(request.user, "is_impersonate", False):
            try:
                request.impersonator = Member.objects.get(id=request.impersonator.id)
                request.member.is_impersonate = True
                request.member.impersonator = request.impersonator
                # If we're impersonating, ensure we're redirected to workshop-periods
                if request.path_info == "/":
                    return redirect(reverse("workshop_periods", kwargs={"period_id": 1}))
            except (Member.DoesNotExist, AttributeError):
                # If anything fails, ensure we're not impersonating
                request.member.is_impersonate = False
                request.impersonator = None
                if "_impersonate" in request.session:
                    del request.session["_impersonate"]
                    request.session.modified = True
        elif request.member:
            request.member.is_impersonate = False
            request.impersonator = None

        # Skip period handling for admin and impersonate paths
        if "/admin/" in request.path_info or "/impersonate/" in request.path_info:
            response = self.get_response(request)
            return response

        # Fill period
        try:
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
            if request.user.is_authenticated and request.user.is_active:
                if request.period.is_in_the_past():
                    msg = _("The period you are viewing has already ended. To choose a more recent one use the dropdown menu in the navbar.")
                elif request.period.is_in_the_future():
                    msg = _(
                        "The period you are viewing is not yet open. "
                        "Please come back later or choose another one from the dropdown menu in the navbar."
                    )
            if msg and msg not in [msg.message for msg in messages.get_messages(request)]:
                messages.warning(request, msg)

        except (Http404, Resolver404):
            # For paths that don't match any URL pattern
            request.period = Period.objects.current_or_last()

        # Continue processing the request
        response = self.get_response(request)

        # Clean up impersonation if user is not a superuser
        if getattr(settings, "IMPERSONATE_REQUIRE_SUPERUSER", False) and not request.user.is_superuser:
            if "_impersonate" in request.session:
                del request.session["_impersonate"]
                request.session.modified = True

        return response
