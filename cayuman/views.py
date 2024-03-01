from datetime import datetime

from django import forms
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import render
from django.views import View

from .models import Member
from .models import Period
from .models import Schedule


def available_workshop_periods(user):
    now = datetime.now().date()
    try:
        p = Period.objects.get(enrollment_start__lte=now, date_end__gt=now)
    except Period.DoesNotExist:
        p = None

    ss = Schedule.objects.all()

    m = Member.objects.get(id=user.id)
    current_cycle = m.current_cycle.cycle if m.current_cycle else None

    wps_by_schedule = {}
    for s in ss:
        for wp in s.workshopperiod_set.filter(period=p):
            if current_cycle in wp.cycles.all():
                if s not in wps_by_schedule:
                    wps_by_schedule[s] = []
                wps_by_schedule[s].append(wp)

    return wps_by_schedule, p, m


class WorkshopSelectionForm(forms.Form):
    def __init__(self, *args, schedules_with_workshops=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.schedules_with_workshops = schedules_with_workshops
        if schedules_with_workshops:
            for schedule, workshops in schedules_with_workshops.items():
                workshop_choices = [(workshop.id, f"{workshop.workshop.name} with {workshop.teacher}") for workshop in workshops]
                self.fields[f"schedule_{schedule.id}"] = forms.ChoiceField(
                    choices=workshop_choices,
                    label=f"{schedule.day} {schedule.time_start}-{schedule.time_end}",
                    required=True,
                    widget=forms.RadioSelect,
                )

    def clean(self):
        cleaned_data = super().clean()
        # Ensure every schedule has a selected workshop
        schedules, _, _ = available_workshop_periods(self.user)
        for schedule in schedules:
            field_name = f"schedule_{schedule.id}"
            if field_name not in cleaned_data or not cleaned_data[field_name]:
                self.add_error(field_name, f"Please select a workshop for {schedule.day} {schedule.time_start}-{schedule.time_end}.")


class HomeView(LoginRequiredMixin, View):
    login_url = "/accounts/login/"
    redirect_field_name = "redirect_to"

    def get(self, request, *args, **kwargs):
        wps_by_schedule, p, m = available_workshop_periods(request.user)

        form = WorkshopSelectionForm(schedules_with_workshops=wps_by_schedule, user=request.user)
        return render(request, "home.html", {"form": form, "period": p, "member": m})

    def post(self, request, *args, **kwargs):
        wps_by_schedule, p, m = available_workshop_periods(request.user)

        # Pass schedules_with_workshops when instantiating the form for POST
        form = WorkshopSelectionForm(request.POST, schedules_with_workshops=wps_by_schedule, user=request.user)
        if form.is_valid():
            # Form is valid, proceed with saving data or other post-submission processes
            return HttpResponse("Form is valid and data has been processed.")
        else:
            # Form is not valid, re-render the page with form errors
            return render(request, "home.html", {"form": form, "period": p, "member": m})
