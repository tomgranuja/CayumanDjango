from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse_lazy as reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views import View

from .decorators import period_required
from .decorators import student_required
from .forms import StudentLoginForm
from .forms import WorkshopSelectionForm
from .models import Schedule
from .models import WorkshopPeriod


class StudentLoginView(LoginView):
    """Django Login View but with our custom form to control each message and label"""

    form_class = StudentLoginForm


@method_decorator(login_required, name="dispatch")
@method_decorator(period_required, name="dispatch")
@method_decorator(student_required, name="dispatch")
class EnrollmentView(LoginRequiredMixin, View):
    """Enrollment form view, where students can choose their workshops"""

    login_url = reverse("login")
    redirect_field_name = "redirect_to"

    def get(self, request, *args, **kwargs):
        """GET view for the enrollment form"""
        student_cycle = request.current_member.current_student_cycle

        # check if student is enabled to enroll, otherwise redirect to weekly-schedule with a warning message
        if not student_cycle.is_enabled_to_enroll():
            messages.warning(request, _("Online enrollment is no longer enabled. If you need to change your workshops please contact your teachers."))
            return HttpResponseRedirect(reverse("weekly_schedule"))

        if not request.GET.get("force") and student_cycle.is_schedule_full():
            return HttpResponseRedirect(reverse("weekly_schedule"))

        # current data
        wps_by_schedule = student_cycle.available_workshop_periods_by_schedule()
        data = {f"schedule_{sched.id}": wp.id for sched, wp in student_cycle.workshop_periods_by_schedule(period=request.current_period).items()}
        form = WorkshopSelectionForm(initial=data, schedules_with_workshops=wps_by_schedule, member=request.current_member)

        return render(request, "enrollment.html", {"form": form, "period": request.current_period, "member": request.current_member})

    def post(self, request, *args, **kwargs):
        """Save workshop periods for current student cycle"""
        student_cycle = request.current_member.current_student_cycle

        # check if student is enabled to enroll, otherwise redirect to weekly-schedule with a warning message
        if not student_cycle.is_enabled_to_enroll():
            messages.warning(request, _("Online enrollment is no longer enabled. If you need to change your workshops please contact your teachers."))
            return HttpResponseRedirect(reverse("weekly_schedule"))

        # Pass schedules_with_workshops when instantiating the form for POST
        wps_by_schedule = student_cycle.available_workshop_periods_by_schedule()
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
    wps_by_schedule = request.current_member.current_student_cycle.available_workshop_periods_by_schedule()
    wps = {wp for sublist in wps_by_schedule.values() for wp in sublist}
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
