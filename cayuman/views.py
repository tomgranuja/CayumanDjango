from typing import Dict
from typing import Optional

from django import forms
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.utils.safestring import mark_safe
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
    def __init__(self, *args, schedules_with_workshops: Optional[Dict[Schedule, WorkshopPeriod]] = None, member: Member = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.member = member
        self.period = Period.current()
        self.schedules_with_workshops = schedules_with_workshops
        if schedules_with_workshops:
            for schedule, workshop_periods in schedules_with_workshops.items():
                workshop_choices = [(wp.id, mark_safe(self.choice_label(wp))) for wp in workshop_periods]
                self.fields[f"schedule_{schedule.id}"] = forms.ChoiceField(
                    choices=workshop_choices,
                    label=f"{schedule.day} {schedule.time_start.strftime('%H:%M')} - {schedule.time_end.strftime('%H:%M')}",
                    required=True,
                    widget=forms.RadioSelect,
                )

    def choice_label(self, workshop_period: WorkshopPeriod) -> str:
        """Returns a label for a workshop period"""
        remaining_quota = workshop_period.remaining_quota()
        badge = (
            f'<span class="badge rounded-pill text-bg-secondary">{remaining_quota}</span>'
            if remaining_quota is not None and remaining_quota >= 0
            else ""
        )
        return f"{workshop_period.workshop.name} with {workshop_period.teacher} {badge}"

    def clean(self) -> None:
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

        # Security/Consistency checks
        for wp in workshop_periods:
            # ensure each workshop_period lives in the correct schedules
            if set(wp.schedules.all()) != set(schedules_by_wp_id[str(wp.id)]):
                raise ValidationError(f"Workshop period {wp.workshop.name} has not been assigned the correct schedules")


class HomeView(LoginRequiredMixin, View):
    login_url = "/accounts/login/"
    redirect_field_name = "redirect_to"

    def get(self, request, *args, **kwargs):
        """GET view for the enrollment form"""
        p = Period.current()
        if not p:
            return HttpResponse("No active period")
        m = Member.objects.get(id=request.user.id)

        # Check if student or not
        if not m.is_student:
            return HttpResponseRedirect("/admin/")

        wps_by_schedule = available_workshop_periods(m)
        student_cycle = m.current_student_cycle

        if not request.GET.get("force") and student_cycle.is_schedule_full(p):
            return HttpResponseRedirect("/weekly-schedule/")

        # current data
        data = {f"schedule_{sched.id}": wp.id for sched, wp in student_cycle.workshop_periods_by_schedule(period=p).items()}
        form = WorkshopSelectionForm(initial=data, schedules_with_workshops=wps_by_schedule, member=m)

        return render(request, "home.html", {"form": form, "period": p, "member": m})

    def post(self, request, *args, **kwargs):
        """Save workshop periods for current student cycle"""
        p = Period.current()
        if not p:
            return HttpResponse("No active period")
        m = Member.objects.get(id=request.user.id)

        wps_by_schedule = available_workshop_periods(m)
        student_cycle = m.current_student_cycle

        # Pass schedules_with_workshops when instantiating the form for POST
        form = WorkshopSelectionForm(request.POST, schedules_with_workshops=wps_by_schedule, member=m)
        if form.is_valid():
            # Form is valid, proceed with saving data or other post-submission processes
            workshop_period_ids = set()
            for schedule in wps_by_schedule:
                field_name = f"schedule_{schedule.id}"
                wp = form.cleaned_data[field_name]
                workshop_period_ids.add(wp)

            workshop_periods = list(WorkshopPeriod.objects.filter(id__in=workshop_period_ids))

            # Associate workshop periods with student cycle
            # Wrap the operations in a transaction.atomic block to rollback db operation if it fails due to additional validation
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
                return HttpResponseRedirect("/weekly-schedule/?saved=true")
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
    data = {sched: this_user_wps.get(sched) for sched in schedules}
    days = [t for t in Schedule.CHOICES]
    raw_blocks = [(block.time_start, block.time_end) for block in schedules]
    blocks = []
    [blocks.append(item) for item in raw_blocks if item not in blocks]

    # feedback in case GET['saved'] exists
    feedback = None
    if request.GET.get("saved"):
        feedback = "Your preferences have been saved"

    return render(request, "weekly_schedule.html", {"period": p, "member": m, "data": data, "days": days, "blocks": blocks, "feedback": feedback})


def workshop_period(request, workshop_period_id):
    """View for a workshop period"""
    p = Period.current()
    if not p:
        return HttpResponse("No active period")
    try:
        wp = WorkshopPeriod.objects.get(id=workshop_period_id, period=p)
    except WorkshopPeriod.DoesNotExist:
        raise Http404

    days = [t for t in Schedule.CHOICES]
    schedules = Schedule.ordered()
    raw_blocks = [(block.time_start, block.time_end) for block in schedules]
    blocks = []
    [blocks.append(item) for item in raw_blocks if item not in blocks]

    return render(request, "workshop_period.html", {"wp": wp, "days": days, "blocks": blocks, "schedules": schedules})
