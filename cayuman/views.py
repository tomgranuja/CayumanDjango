from typing import Dict
from typing import Optional

from django import forms
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.views import View

from .models import Member
from .models import Period
from .models import Schedule
from .models import WorkshopPeriod


def available_workshop_periods(member: Member) -> Dict[Schedule, WorkshopPeriod]:
    """Returns available workshop periods for a member given a period"""
    period = Period.current()
    ss = Schedule.ordered()

    current_student_cycle = member.current_student_cycle.cycle if member.current_student_cycle else None

    wps_by_schedule = {}
    for s in ss:
        for wp in s.workshopperiod_set.filter(period=period):
            if current_student_cycle in wp.cycles.all():
                if s not in wps_by_schedule:
                    wps_by_schedule[s] = []
                wps_by_schedule[s].append(wp)

    return wps_by_schedule


class WorkshopSelectionForm(forms.Form):
    def __init__(self, *args, schedules_with_workshops: Optional[Dict[Schedule, WorkshopPeriod]] = None, member=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.member = member
        self.period = Period.current()
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

        # get available workshops for this user
        schedules = available_workshop_periods(self.member)

        schedules_by_wp_id = dict()

        # walk through responses
        for schedule in schedules:
            field_name = f"schedule_{schedule.id}"
            # ensure every schedule has an associated response
            if field_name not in cleaned_data or not cleaned_data[field_name]:
                self.add_error(field_name, f"Please select a workshop for {schedule.day} {schedule.time_start}-{schedule.time_end}.")

            # save workshop period id
            wp_id = str(cleaned_data[field_name])
            if wp_id not in schedules_by_wp_id:
                schedules_by_wp_id[wp_id] = []
            schedules_by_wp_id[wp_id].append(schedule)

        # one query to get all workshop period objects
        workshop_periods = WorkshopPeriod.objects.filter(id__in=schedules_by_wp_id.keys())

        # Security/Consistency checks:
        for wp in workshop_periods:
            # ensure each workshop_period lives in the correct schedules
            if set(wp.schedules.all()) != set(schedules_by_wp_id[str(wp.id)]):
                raise ValidationError(f"Workshop period {wp.workshop.name} has not been assigned the correct schedules")

            # ensure each workshop is accesible to this user's cycle
            # if self.member.current_student_cycle.cycle not in wp.cycles.all():
            #    raise ValidationError(f"Workshop {wp.workshop.name} is not available to cycle {self.member.current_student_cycle.cycle.name}")

            # check if there are available spots for each workshop
            # if wp.max_students > 0:
            #    # Count students in this cycle without counting current student
            #    # curr_count = wp.studentcycle_set.filter(student__id__ne=instance.student.id).count()
            #    curr_count = wp.studentcycle_set.exclude(student__id=self.member.id).count()
            #    if wp.max_students <= curr_count:
            #        raise ValidationError(f"Workshop period {wp.workshop.name} is already full")

            # ensure no collisions between workshops
            # for wp2 in workshop_periods:
            #    if wp.id != wp2.id and wp & wp2:
            #        raise ValidationError(f"Two chosen workshops are colliding: {wp.workshop.name} and {wp2.workshop.name}")


class HomeView(LoginRequiredMixin, View):
    login_url = "/accounts/login/"
    redirect_field_name = "redirect_to"

    def get(self, request, *args, **kwargs):
        p = Period.current()
        if not p:
            return HttpResponse("No active period")
        m = Member.objects.get(id=request.user.id)

        wps_by_schedule = available_workshop_periods(m)
        student_cycle = m.current_student_cycle

        data = {f"schedule_{sched.id}": wp.id for sched, wp in student_cycle.workshop_periods_by_schedule().items()}

        form = WorkshopSelectionForm(initial=data, schedules_with_workshops=wps_by_schedule, member=m)
        return render(request, "home.html", {"form": form, "period": p, "member": m})

    def post(self, request, *args, **kwargs):
        p = Period.current()
        if not p:
            return HttpResponse("No active period")
        m = Member.objects.get(id=request.user.id)

        wps_by_schedule = available_workshop_periods(m)

        # Pass schedules_with_workshops when instantiating the form for POST
        form = WorkshopSelectionForm(request.POST, schedules_with_workshops=wps_by_schedule, member=m)
        if form.is_valid():
            # Form is valid, proceed with saving data or other post-submission processes
            student_cycle = m.current_student_cycle

            workshop_period_ids = set()
            for schedule in wps_by_schedule:
                field_name = f"schedule_{schedule.id}"
                wp = form.cleaned_data[field_name]
                workshop_period_ids.add(wp)

            workshop_periods = list(WorkshopPeriod.objects.filter(id__in=workshop_period_ids))

            # Associate workshop periods with student cycle
            # Wrap the operations in a transaction.atomic block
            try:
                with transaction.atomic():
                    # Clear existing workshop periods
                    student_cycle.workshop_periods.clear()

                    # Attempt to associate new workshop periods with student cycle
                    student_cycle.workshop_periods.add(*workshop_periods)
            except ValidationError as e:
                # If a ValidationError occurs, the transaction will be rolled back automatically
                form.add_error(None, e)

            if form.errors:
                return render(request, "home.html", {"form": form, "period": p, "member": m})
            else:
                return HttpResponseRedirect("/weekly-schedule/")
        else:
            # Form is not valid, re-render the page with form errors
            return render(request, "home.html", {"form": form, "period": p, "member": m})


@login_required(login_url="/accounts/login/")
def weekly_schedule(request):
    p = Period.current()
    if not p:
        return HttpResponse("No active period")
    m = Member.objects.get(id=request.user.id)

    schedules = Schedule.ordered()
    this_user_wps = m.current_student_cycle.workshop_periods_by_schedule()
    data = dict()

    for sched in schedules:
        if sched not in this_user_wps:
            data[sched] = None
        else:
            data[sched] = this_user_wps[sched]

    days = [t for t in Schedule.CHOICES]
    raw_blocks = [(block.time_start, block.time_end) for block in schedules]
    blocks = []
    [blocks.append(item) for item in raw_blocks if item not in blocks]

    return render(request, "weekly_schedule.html", {"period": p, "member": m, "data": data, "days": days, "blocks": blocks})
