# from django.contrib import admin
from django.contrib import admin
from django.urls import include
from django.urls import path

from .views import HomeView
from .views import weekly_schedule
from .views import workshop_period

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("weekly-schedule/", weekly_schedule, name="weekly_schedule"),
    path("workshop-period/<int:workshop_period_id>/", workshop_period, name="workshop_period"),
    path("", HomeView.as_view(), name="home"),
]
