from django.contrib import admin
from django.urls import include
from django.urls import path

from .views import HomeView
from .views import weekly_schedule

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("weekly-schedule/", weekly_schedule, name="weekly_schedule"),
    path("", HomeView.as_view(), name="home"),
]
