from functools import wraps
from html import escape
from typing import Dict
from typing import Optional

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse_lazy as reverse
from django.utils.decorators import method_decorator
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _
from django.views import View

from .models import Member
from .models import Period
from .models import Schedule
from .models import WorkshopPeriod


def period_required(view_func):
    """Decorator to ensure a view counts with a valid active Period"""

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        current_period = Period.objects.current()
        if not current_period:
            return HttpResponse("No active period")

        request.current_period = current_period

        return view_func(request, *args, **kwargs)

    return _wrapped_view


def student_required(view_func):
    """Decorator to ensure a view counts with a valid active student"""

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        try:
            member = Member.objects.get(id=request.user.id)
            if not member.is_student or not member.is_active:
                return HttpResponseRedirect(reverse("admin:login"))

            request.current_member = member
        except Member.DoesNotExist:
            return HttpResponseRedirect(reverse("login"))

        return view_func(request, *args, **kwargs)

    return _wrapped_view


def available_workshop_periods_by_schedule(member: Member) -> Dict[Schedule, WorkshopPeriod]:
    """Returns available workshop periods for a member given a period"""
    period = Period.objects.current()
    ss = Schedule.objects.ordered()

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
        self.period = Period.objects.current()
        self.schedules_with_workshops = schedules_with_workshops
        if schedules_with_workshops:
            for schedule, workshop_periods in schedules_with_workshops.items():
                workshop_choices = [(wp.id, mark_safe(self.choice_label(wp))) for wp in workshop_periods]
                self.fields[f"schedule_{schedule.id}"] = forms.ChoiceField(
                    choices=workshop_choices,
                    label=f"{schedule.get_day_display()} {schedule.time_start.strftime('%H:%M')} - {schedule.time_end.strftime('%H:%M')}",
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
        popover = (
            f'<a href="#/" data-bs-toggle="popover" data-bs-trigger="focus" data-bs-title="{escape(workshop_period.workshop.name)}" data-bs-content="{escape(workshop_period.workshop.description)}">(?)</a>'  # noqa E501
            if workshop_period.workshop.description
            else ""
        )
        output = _("%(wp_name)s with %(teacher)s") % {"wp_name": workshop_period.workshop.name, "teacher": workshop_period.teacher.get_full_name()}
        return f"{output} {badge} {popover}"

    def clean(self) -> None:
        cleaned_data = super().clean()

        # get available workshops for this user
        schedules = available_workshop_periods_by_schedule(self.member)
        schedules_by_wp_id = dict()

        # walk through all expected schedules
        for schedule in schedules:
            field_name = f"schedule_{schedule.id}"
            # ensure every schedule has an associated response
            if field_name not in cleaned_data or not cleaned_data[field_name]:
                self.add_error(
                    field_name,
                    _("Please select a workshop for %(day)s %(start_time)s-%(end_time)s")
                    % {
                        "day": schedule.get_day_display(),
                        "start_time": schedule.time_start.strftime("%H:%M"),
                        "end_time": schedule.time_end.strftime("%H:%M"),
                    },
                )

            # save workshop period id
            wp_id = str(cleaned_data[field_name])
            if wp_id not in schedules_by_wp_id:
                schedules_by_wp_id[wp_id] = []
            schedules_by_wp_id[wp_id].append(schedule)

        # one query to get all workshop period objects
        workshop_periods = WorkshopPeriod.objects.filter(id__in=schedules_by_wp_id.keys())

        # The following check tries to understand if no hacking attempts were done
        # It does it by checking each workshop was given their right schedules and not arbitrary values (form tampering)
        for wp in workshop_periods:
            # ensure each workshop_period lives in the correct schedules
            if set(wp.schedules.all()) != set(schedules_by_wp_id[str(wp.id)]):
                raise ValidationError(_("Workshop period %(wp)s has not been assigned the correct schedules") % {"wp": wp.workshop.name})


@method_decorator(login_required, name="dispatch")
@method_decorator(period_required, name="dispatch")
@method_decorator(student_required, name="dispatch")
class EnrollmentView(LoginRequiredMixin, View):
    login_url = reverse("login")
    redirect_field_name = "redirect_to"

    def get(self, request, *args, **kwargs):
        """GET view for the enrollment form"""
        wps_by_schedule = available_workshop_periods_by_schedule(request.current_member)
        student_cycle = request.current_member.current_student_cycle

        if not request.GET.get("force") and student_cycle.is_schedule_full(request.current_period):
            return HttpResponseRedirect(reverse("weekly_schedule"))

        # current data
        data = {f"schedule_{sched.id}": wp.id for sched, wp in student_cycle.workshop_periods_by_schedule(period=request.current_period).items()}
        form = WorkshopSelectionForm(initial=data, schedules_with_workshops=wps_by_schedule, member=request.current_member)

        return render(request, "enrollment.html", {"form": form, "period": request.current_period, "member": request.current_member})

    def post(self, request, *args, **kwargs):
        """Save workshop periods for current student cycle"""
        wps_by_schedule = available_workshop_periods_by_schedule(request.current_member)
        student_cycle = request.current_member.current_student_cycle

        # Pass schedules_with_workshops when instantiating the form for POST
        form = WorkshopSelectionForm(request.POST, schedules_with_workshops=wps_by_schedule, member=request.current_member)
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
                return render(request, "enrollment.html", {"form": form, "period": request.current_period, "member": request.current_member})
            else:
                messages.success(request, _("Your workshops have been saved"))
                return HttpResponseRedirect(reverse("weekly_schedule"))
        else:
            # Form is not valid, re-render the page with form errors
            return render(request, "enrollment.html", {"form": form, "period": request.current_period, "member": request.current_member})


@login_required(login_url=reverse("login"))
@period_required
@student_required
def home(request):
    """Home view showing the list of all available workshops for the given logger in student"""
    # This view is only visible if GET force is defined or if the student is not enrolled yet for the current period
    if not request.GET.get("force") and request.current_member.current_student_cycle.is_schedule_full(request.current_period):
        return HttpResponseRedirect(reverse("weekly_schedule"))

    # Get all available workshop periods for this student and return
    wps = {wp for sublist in available_workshop_periods_by_schedule(request.current_member).values() for wp in sublist}
    return render(request, "home.html", {"period": request.current_period, "member": request.current_member, "workshop_periods": wps})


@login_required(login_url=reverse("login"))
@period_required
@student_required
def weekly_schedule(request):
    """Show users their weekly schedule with enrolled workshops"""
    schedules = Schedule.objects.ordered()
    this_user_wps = request.current_member.current_student_cycle.workshop_periods_by_schedule()
    data = {sched: this_user_wps.get(sched) for sched in schedules}
    days = [t for t in Schedule.CHOICES]
    raw_blocks = [(block.time_start, block.time_end) for block in schedules]
    blocks = []
    [blocks.append(item) for item in raw_blocks if item not in blocks]

    return render(
        request,
        "weekly_schedule.html",
        {"period": request.current_period, "member": request.current_member, "data": data, "days": days, "blocks": blocks},
    )


@period_required
def workshop_period(request, workshop_period_id: int):
    """View detailed information about a workshop period"""
    try:
        wp = WorkshopPeriod.objects.get(id=workshop_period_id, period=request.current_period)
    except WorkshopPeriod.DoesNotExist:
        raise Http404

    days = [t for t in Schedule.CHOICES]
    schedules = Schedule.objects.ordered()
    raw_blocks = [(block.time_start, block.time_end) for block in schedules]
    blocks = []
    [blocks.append(item) for item in raw_blocks if item not in blocks]

    return render(request, "workshop_period.html", {"wp": wp, "days": days, "blocks": blocks, "schedules": schedules})
