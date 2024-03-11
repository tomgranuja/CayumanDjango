from django.template.context_processors import csrf
from django.template.defaultfilters import date
from django.urls import reverse
from django.urls import reverse_lazy
from jinja2 import Environment


def environment(**options):
    env = Environment(**options)
    env.globals.update({"url": reverse, "url_lazy": reverse_lazy, "csrf_token": lambda request: csrf(request)["csrf_token"]})
    env.filters["date"] = date
    return env
