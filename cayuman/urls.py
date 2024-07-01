# from django.contrib import admin
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include
from django.urls import path

from .views import EnrollmentView
from .views import home
from .views import StudentLoginView
from .views import weekly_schedule
from .views import workshop_period
from .views import workshop_periods

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/login/", StudentLoginView.as_view(), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(next_page="login"), name="logout"),
    path("weekly-schedule/<int:period_id>/", weekly_schedule, name="weekly_schedule"),
    path("workshop-period/<int:workshop_period_id>/", workshop_period, name="workshop_period"),
    path("workshop-periods/<int:period_id>/", workshop_periods, name="workshop_periods"),
    path("enrollment/<int:period_id>/", EnrollmentView.as_view(), name="enrollment"),
    path("impersonate/", include("impersonate.urls")),
    path("", home, name="home"),
]
