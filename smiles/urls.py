from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("term/<int:term_id>/enrollment/", views.EnrollmentView.as_view(), name="enrollment"),
    path("term/<int:term_id>/schedule/", views.weekly_schedule, name="weekly_schedule"),
    path("term/<int:term_id>/subjects/", views.subject_offerings, name="subject_offerings"),
    path("subject-offering/<int:subject_offering_id>/", views.subject_offering, name="subject_offering"),
]
