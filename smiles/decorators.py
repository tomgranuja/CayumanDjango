from functools import wraps

from django.conf import settings
from django.contrib.auth.models import Group
from django.http import Http404
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse

from smiles.models import Term


def student_required(view_func):
    """
    Decorator for views that checks that the user is a student.
    """

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        try:
            students_group = Group.objects.get(name=settings.STUDENTS_GROUP)
        except Group.DoesNotExist:
            return HttpResponseRedirect(reverse("login"))

        if not request.user.is_authenticated or not request.user.groups.filter(id=students_group.id).exists():
            return HttpResponseRedirect(reverse("login"))

        return view_func(request, *args, **kwargs)

    return _wrapped_view


def teacher_required(view_func):
    """
    Decorator for views that checks that the user is a teacher.
    """

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        try:
            teachers_group = Group.objects.get(name=settings.TEACHERS_GROUP)
        except Group.DoesNotExist:
            return HttpResponseRedirect(reverse("login"))

        if not request.user.is_authenticated or not request.user.groups.filter(id=teachers_group.id).exists():
            return HttpResponseRedirect(reverse("login"))

        return view_func(request, *args, **kwargs)

    return _wrapped_view


def membergroup_required(view_func):
    """
    Decorator for views that checks that the user has a MemberGroupAssignment.
    """

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not hasattr(request.member, "current_group_assignment") or not request.member.current_group_assignment:
            return HttpResponseRedirect(reverse("login"))

        return view_func(request, *args, **kwargs)

    return _wrapped_view


def term_middleware(get_response):
    """
    Middleware that adds the current term to the request.
    """

    def middleware(request):
        # Get term_id from URL if it exists
        term_id = None
        if hasattr(request, "resolver_match") and request.resolver_match:
            term_id = request.resolver_match.kwargs.get("term_id")

        # Get the term
        if term_id:
            try:
                request.term = get_object_or_404(Term, id=term_id)
            except Http404:
                request.term = Term.objects.current()
        else:
            request.term = Term.objects.current()

        return get_response(request)

    return middleware


def enrollment_access_required(view_func):
    """
    Decorator for views that checks that the user is allowed to enroll in the given term.
    """

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # Get term_id from URL
        term_id = kwargs.get("term_id")
        if not term_id:
            return HttpResponseRedirect(reverse("home"))

        # Get the term
        try:
            term = Term.objects.get(id=term_id)
        except Term.DoesNotExist:
            return HttpResponseRedirect(reverse("home"))

        # Check if the term is enabled for enrollment
        if not term.is_enabled_to_enroll():
            return HttpResponseRedirect(reverse("home"))

        # Check if the member is enabled to enroll
        if not request.member.is_enabled_to_enroll(term):
            return HttpResponseRedirect(reverse("home"))

        return view_func(request, *args, **kwargs)

    return _wrapped_view
