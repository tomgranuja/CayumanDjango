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

from .decorators import student_required
from .decorators import studentcycle_required
from .forms import StudentLoginForm
from .forms import WorkshopSelectionForm
from .models import WorkshopPeriod


class StudentLoginView(LoginView):
    """Django Login View but with our custom form to control each message and label"""

    form_class = StudentLoginForm


@method_decorator(login_required, name="dispatch")
@method_decorator(student_required, name="dispatch")
@method_decorator(studentcycle_required, name="dispatch")
class EnrollmentView(LoginRequiredMixin, View):
    """Enrollment form view, where students can choose their workshops"""

    login_url = reverse("login")
    redirect_field_name = "redirect_to"

    def get(self, request, period_id: int):
        """GET view for the enrollment form"""
        student_cycle = request.member.current_student_cycle

        # check if student is enabled to enroll, otherwise redirect to weekly-schedule with a warning message
        if not student_cycle.is_enabled_to_enroll(request.period):
            messages.warning(request, _("Online enrollment is no longer enabled. If you need to change your workshops please contact your teachers."))
            return HttpResponseRedirect(reverse("weekly_schedule", kwargs={"period_id": request.period.id}))

        if not request.GET.get("force") and student_cycle.is_schedule_full(request.period):
            return HttpResponseRedirect(reverse("weekly_schedule", kwargs={"period_id": request.period.id}))

        # current data
        wps_by_schedule = student_cycle.available_workshop_periods_by_schedule(request.period)
        data = {f"schedule_{sched.id}": wp.id for sched, wp in student_cycle.workshop_periods_by_schedule(period=request.period).items()}
        form = WorkshopSelectionForm(initial=data, schedules_with_workshops=wps_by_schedule, member=request.member)

        return render(request, "enrollment.html", {"form": form})

    def post(self, request, period_id: int):
        """Save workshop periods for current student cycle"""
        student_cycle = request.member.current_student_cycle

        # check if student is enabled to enroll, otherwise redirect to weekly-schedule with a warning message
        if not student_cycle.is_enabled_to_enroll(request.period):
            messages.warning(request, _("Online enrollment is no longer enabled. If you need to change your workshops please contact your teachers."))
            return HttpResponseRedirect(reverse("weekly_schedule", kwargs={"period_id": request.period.id}))

        # Pass schedules_with_workshops when instantiating the form for POST
        wps_by_schedule = student_cycle.available_workshop_periods_by_schedule(request.period)
        form = WorkshopSelectionForm(request.POST, schedules_with_workshops=wps_by_schedule, member=request.member, period=request.period)
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
                    # Get workshop_periods only in current period
                    workshop_periods_to_remove = student_cycle.workshop_periods.filter(period=request.period)

                    # Remove these workshop periods from the student_cycle
                    student_cycle.workshop_periods.remove(*workshop_periods_to_remove)

                    # Attempt to associate new workshop periods with student cycle
                    student_cycle.workshop_periods.add(*workshop_periods)

                    # Clear caches
                    # student_cycle.available_workshop_periods_by_schedule.cache_clear()
                    student_cycle.workshop_periods_by_schedule.cache_clear()
                    student_cycle.is_schedule_full.cache_clear()
                    student_cycle.workshop_periods_by_period.cache_clear()
                    student_cycle.is_enabled_to_enroll.cache_clear()
            except ValidationError as e:
                # If a ValidationError occurs, the transaction will be rolled back automatically
                form.add_error(None, e)

            if form.errors:
                return render(request, "enrollment.html", {"form": form})
            else:
                messages.success(request, _("Your workshops have been saved"))
                return HttpResponseRedirect(reverse("weekly_schedule", kwargs={"period_id": request.period.id}))
        else:
            # Form is not valid, re-render the page with form errors
            return render(request, "enrollment.html", {"form": form})


@login_required(login_url=reverse("login"))
@student_required
def home(request):
    """
    Home view

    - if studentcycle.is_full_schedule(request.period) - redirect to schedule view
    - else - redirect to workshops view
    """
    if request.member.is_schedule_full(request.period):
        return HttpResponseRedirect(reverse("weekly_schedule", kwargs={"period_id": request.period.id}))
    else:
        return HttpResponseRedirect(reverse("workshop_periods", kwargs={"period_id": request.period.id}))


@login_required(login_url=reverse("login"))
@student_required
@studentcycle_required
def weekly_schedule(request, period_id: int):
    """Show users their weekly time table for the given period"""
    wps = request.member.current_student_cycle.workshop_periods.filter(period=request.period)
    return render(
        request,
        "weekly_schedule.html",
        {"workshop_periods": wps},
    )


def workshop_period(request, workshop_period_id: int):
    """View detailed information about a workshop period"""
    try:
        wp = WorkshopPeriod.objects.get(id=workshop_period_id)
    except WorkshopPeriod.DoesNotExist:
        raise Http404

    return render(request, "workshop_period.html", {"wp": wp})


@login_required(login_url=reverse("login"))
@student_required
def workshop_periods(request, period_id: int):
    """View showing the list of all available workshops for the given logged in student"""
    # Period middleware guarantees request.period won't be null but it's still necessary to analyze if it's an active period or not
    wps = set()

    current_student_cycle = request.member.current_student_cycle
    if not request.period.can_be_previewed():
        messages.warning(request, _("It is still not the time to visualize workshops for the upcoming period. Please return later."))
    else:
        # Get all available workshop periods for this student and return
        if current_student_cycle:
            wps_by_schedule = current_student_cycle.available_workshop_periods_by_schedule(request.period)
            wps = {wp for sublist in wps_by_schedule.values() for wp in sublist}
        else:
            messages.warning(request, _("Your student account is not associated with any Cycle. Please ask your teachers to fix this."))
    return render(request, "workshop_periods.html", {"workshop_periods": wps})
