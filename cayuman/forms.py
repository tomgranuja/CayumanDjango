from html import escape
from typing import Dict
from typing import Optional

from django import forms
from django.conf import settings
from django.contrib.auth.admin import UserChangeForm
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.forms import UsernameField
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.forms import ModelForm
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from .models import Member
from .models import Period
from .models import Schedule
from .models import StudentCycle
from .models import WorkshopPeriod


class AdminMemberChangeForm(UserChangeForm):
    """Admin form to validate groups assigned to a member"""

    def clean_groups(self):
        try:
            is_student = Group.objects.get(name=settings.STUDENTS_GROUP) in self.cleaned_data["groups"]
        except Group.DoesNotExist:
            is_student = False
        try:
            is_teacher = Group.objects.get(name=settings.TEACHERS_GROUP) in self.cleaned_data["groups"]
        except Group.DoesNotExist:
            is_teacher = False

        if not self.cleaned_data["is_staff"]:
            if not is_student and not is_teacher:
                raise ValidationError(_("User must be either Student or Teacher, or a staff member"))
        else:
            if is_student:
                raise ValidationError(_("Student cannot be staff member"))

        if is_student and is_teacher:
            raise ValidationError(_("User must not be both Student and Teacher"))

        return self.cleaned_data["groups"]


class AdminWorkshopPeriodForm(ModelForm):
    """
    Admin form to customize workshop period form showing only actual teachers as options for `teacher` field
    and getting sure teachers won't have colliding schedules with their other workshop periods for the given period
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        teachers_group = Group.objects.get(name=settings.TEACHERS_GROUP)
        if "teacher" in self.fields:
            self.fields["teacher"].queryset = Member.objects.filter(groups=teachers_group)

    def clean_schedules(self):
        # Get schedules for same teacher and period
        if self.cleaned_data["teacher"] and self.cleaned_data["period"]:
            other_wps = WorkshopPeriod.objects.filter(teacher=self.cleaned_data["teacher"], period=self.cleaned_data["period"])
            other_schedules = set()
            for wp in other_wps:
                if self.instance:
                    if self.instance.id == wp.id:
                        continue
                for sched in wp.schedules.all():
                    other_schedules.add(sched)

            # check overlapping due to schedules
            if any(sched in other_schedules for sched in self.cleaned_data["schedules"]):
                raise ValidationError(_("There's already another workshop period overlapping with current one"))

        return self.cleaned_data["schedules"]

    class Meta:
        fields = "__all__"
        model = WorkshopPeriod


class AdminStudentCycleForm(ModelForm):
    """
    Admin form to show only actual students in the `student` field and validating assigned workshop periods
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        students_group = Group.objects.get(name=settings.STUDENTS_GROUP)
        if "student" in self.fields:
            self.fields["student"].queryset = Member.objects.filter(groups=students_group)

    def save(self, commit=True):
        """clear model's cached methods"""
        # Save the instance as usual
        instance = super().save(commit=commit)

        # Clear the cache for the relevant methods
        if commit:
            # instance.available_workshop_periods_by_schedule.cache_clear()
            instance.workshop_periods_by_schedule.cache_clear()
            instance.is_schedule_full.cache_clear()
            instance.workshop_periods_by_period.cache_clear()
            instance.is_enabled_to_enroll.cache_clear()

        return instance

    def clean_workshop_periods(self):
        # clean workshop_periods m2m relation
        # this breaks DRY principle with respect to m2m_changed signal handler for model StudentCycle
        # but it's necessary so validation works ok in django admin as well as directly using the model
        # {'student': Member(...), 'cycle': <Cycle: ...>, 'workshop_periods': <QuerySet [<WorkshopPeriod: ...>, <WorkshopPeriod: ...>]>}
        student = self.cleaned_data.get("student") or self.instance.student
        cycle = self.cleaned_data.get("cycle") or self.instance.cycle

        for wp in self.cleaned_data["workshop_periods"]:
            # Count students in this cycle without counting current student
            curr_count = wp.studentcycle_set.exclude(student__id=student.id).count()
            # curr_count = wp.studentcycle_set.filter(student__id__ne=self.cleaned_data['student'].id).count()
            if wp.max_students > 0 and wp.max_students <= curr_count:
                raise ValidationError(_("Workshop period `%s` has reached its quota of students") % (wp.workshop.name))

            if cycle not in wp.cycles.all():
                raise ValidationError(
                    _("Student `%(st)s` cannot be associated with workshop period `%(wp)s` because they belong to the same cycle.")
                    % {"st": student.get_full_name(), "wp": wp.workshop.name}
                )

            for wp_2 in self.cleaned_data["workshop_periods"]:
                if wp == wp_2:
                    continue

                if wp & wp_2:
                    raise ValidationError(
                        _("Workshop periods `%(w1)s` and `%(w2)s` have colliding schedules.") % {"w1": wp.workshop.name, "w2": wp_2.workshop.name}
                    )

        return self.cleaned_data["workshop_periods"]

    class Meta:
        fields = "__all__"
        model = StudentCycle


class StudentLoginForm(AuthenticationForm):
    """Students login form showing `RUT` as `username` field"""

    username = UsernameField(
        label=_("RUT"),
        widget=forms.TextInput(attrs={"class": "form-control", "autofocus": True}),
        help_text=_("Use dash, no point (ex. 23456789-k)"),
    )
    password = forms.CharField(label=_("Password"), strip=False, widget=forms.PasswordInput(attrs={"class": "form-control"}))

    def clean_username(self):
        """Turn username to lowercase and strip it"""
        username = self.cleaned_data.get("username")
        return username.lower().strip()

    def get_invalid_login_error(self):
        return ValidationError(
            self.error_messages["invalid_login"],
            code="invalid_login",
            params={"username": _("RUT")},
        )


class WorkshopSelectionForm(forms.Form):
    """Form used by students to enroll in workshops during a given period"""

    def __init__(
        self,
        *args,
        schedules_with_workshops: Optional[Dict[Schedule, WorkshopPeriod]] = None,
        period: Optional[Period] = None,
        member: Optional[Member] = None,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)

        self.submission = False if not bool(self.data) else True  # Flag telling this form has been submitted (True) or just shown (False)
        self.member = member
        self.period = period
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
        """Returns a label for a workshop period radio, returning name, teacher, remaining quota badge and workshop description popover"""
        # Get form's field name for current workshop_period being rendered
        choice_name = (
            None  # store radio field name value == workshop_period.id, on incoming data or initial data. If workshop was not selected then None
        )
        for sched in self.schedules_with_workshops:
            if str(workshop_period.id) in (str(self.data.get(f"schedule_{sched.id}")), str(self.initial.get(f"schedule_{sched.id}"))):
                choice_name = f"schedule_{sched.id}"
                break

        # Get flag telling if the this form field's value has changed (True), or is the same (False) or it's not been selected before (None)
        choice_value_changed = (
            None  # True if value of field changed, False if it didn't change, None if workshop has not been selected on initial or incoming data
        )
        if choice_name is not None:
            choice_value_changed = (
                False if workshop_period.id == self.initial.get(choice_name) else True
            )  # tells whether this value is incoming (being saved) or being replaced

        # Prepare vars to render this field's label
        # Calc `remaining_quota`: if field value has changed substract 1. If it's the same add 1. If it's not been selected before keep DB value
        remaining_quota = workshop_period.remaining_quota()
        if (
            remaining_quota is not None and self.submission and choice_value_changed is not None
        ):  # if form was just submitted and form field value has been selected before or after
            if choice_value_changed:  # this field value was just selected
                remaining_quota -= 1  # -1 because quota is reduced by 1 when user selected this value
            else:  # this field value was de-selected
                remaining_quota += 1  # +1 because quota was increased by 1 when user de-selected this value
        human_remaining_quota = remaining_quota if remaining_quota is not None and remaining_quota >= 0 else 0  # never show quota < 0
        if remaining_quota is not None:
            badge = f'<span class="badge rounded-pill text-bg-secondary" data-value="{remaining_quota}">{human_remaining_quota}</span>'
        else:
            # if no max_students then set quota to 100 and make it invisible so it works ok in the UI
            badge = f'<span class="badge rounded-pill text-bg-secondary d-none" data-value="100">{human_remaining_quota}</span>'
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
        schedules = self.member.current_student_cycle.available_workshop_periods_by_schedule(self.period)
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
