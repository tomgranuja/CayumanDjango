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
from django.utils.translation import gettext_lazy as _

from cayuman.models import Member
from smiles.models import MemberGroupAssignment
from smiles.models import SubjectOffering
from smiles.models import Term
from smiles.models import TimeSlot


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


class AdminSubjectOfferingForm(ModelForm):
    """
    Admin form for SubjectOffering model

    Validates that the teacher is not assigned to multiple subject offerings
    with the same time slot in the same term.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "time_slots" in self.fields:
            self.fields["time_slots"].help_text = _("Select the time slots for this subject offering")

    def clean_time_slots(self):
        # Get time slots for same teacher and term
        time_slots = self.cleaned_data.get("time_slots", [])
        teacher = self.cleaned_data.get("teacher")
        term = self.cleaned_data.get("term")

        if not teacher or not term or not time_slots:
            return time_slots

        # Get all subject offerings for this teacher and term
        teacher_offerings = SubjectOffering.objects.filter(teacher=teacher, term=term)

        # Exclude current instance if it exists
        if self.instance and self.instance.pk:
            teacher_offerings = teacher_offerings.exclude(pk=self.instance.pk)

        # Check for conflicts
        for offering in teacher_offerings:
            for time_slot in offering.time_slots.all():
                if time_slot in time_slots:
                    raise ValidationError(
                        _("Teacher %(teacher)s is already assigned to %(offering)s during %(time_slot)s")
                        % {
                            "teacher": teacher,
                            "offering": offering,
                            "time_slot": time_slot,
                        }
                    )

        return time_slots

    class Meta:
        fields = "__all__"
        model = SubjectOffering


class AdminMemberGroupAssignmentForm(ModelForm):
    """
    Admin form for MemberGroupAssignment model

    Validates that the member is not enrolled in subject offerings with conflicting time slots.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "subject_offerings" in self.fields:
            self.fields["subject_offerings"].help_text = _("Select the subject offerings for this member")

    def save(self, commit=True):
        """
        Save the form and clear caches
        """
        instance = super().save(commit=False)

        # Save the instance if commit is True
        if commit:
            instance.save()

        # Save many-to-many relationships if commit is True
        if commit and hasattr(self, "save_m2m"):
            self.save_m2m()

        return instance

    def clean_subject_offerings(self):
        """
        Validate that the member is not enrolled in subject offerings with conflicting time slots
        """
        subject_offerings = self.cleaned_data.get("subject_offerings", [])

        if not subject_offerings:
            return subject_offerings

        # Check for time slot conflicts
        time_slots_dict = {}

        for offering in subject_offerings:
            for time_slot in offering.time_slots.all():
                if time_slot in time_slots_dict:
                    raise ValidationError(
                        _("Time slot conflict: %(time_slot)s is used by both %(offering1)s and %(offering2)s")
                        % {
                            "time_slot": time_slot,
                            "offering1": time_slots_dict[time_slot],
                            "offering2": offering,
                        }
                    )
                time_slots_dict[time_slot] = offering

        return subject_offerings

    class Meta:
        fields = "__all__"
        model = MemberGroupAssignment


class StudentLoginForm(AuthenticationForm):
    """Students login form showing `RUT` as `username` field"""

    username = UsernameField(
        label=_("RUT"),
        widget=forms.TextInput(attrs={"class": "form-control", "autofocus": True}),
        help_text=_("Use dash, no point (ex. 23456789-k)"),
    )
    password = forms.CharField(label=_("Password"), strip=False, widget=forms.PasswordInput(attrs={"class": "form-control"}))

    def clean_username(self):
        """Clean username field to ensure it's in the correct format"""
        username = self.cleaned_data["username"]
        return username.lower().replace(".", "")

    def get_invalid_login_error(self):
        """Return a custom error message for invalid login"""
        return ValidationError(
            _("Please enter a correct RUT and password. Note that both fields may be case-sensitive."),
            code="invalid_login",
        )


class SubjectSelectionForm(forms.Form):
    """Form for students to select subject offerings for a term"""

    def __init__(
        self,
        *args,
        timeslots_with_offerings: Optional[Dict[TimeSlot, SubjectOffering]] = None,
        term: Optional[Term] = None,
        member: Optional[Member] = None,
        **kwargs,
    ) -> None:
        """
        Initialize the form with timeslots and their available subject offerings

        Args:
            timeslots_with_offerings: Dictionary mapping time slots to lists of available subject offerings
            term: The term for which subject offerings are being selected
            member: The member who is selecting subject offerings
        """
        super().__init__(*args, **kwargs)

        self.term = term
        self.member = member

        if timeslots_with_offerings:
            for time_slot, offerings in timeslots_with_offerings.items():
                field_name = f"timeslot_{time_slot.id}"

                # Create choices for the field
                choices = [(None, _("-- No selection --"))]
                for offering in offerings:
                    choices.append((offering.id, self.choice_label(offering)))

                # Create the field
                self.fields[field_name] = forms.ChoiceField(
                    choices=choices,
                    required=False,
                    label=f"{time_slot.get_day_of_week_display()} {time_slot.time_start.strftime('%H:%M')} - {time_slot.time_end.strftime('%H:%M')}",
                    widget=forms.Select(attrs={"class": "form-control"}),
                )

    def choice_label(self, subject_offering: SubjectOffering) -> str:
        """
        Generate a label for a subject offering choice

        Args:
            subject_offering: The subject offering to generate a label for

        Returns:
            A string label for the subject offering
        """
        # Get the number of students enrolled in this subject offering
        num_students = subject_offering.count_students()

        # Get the maximum number of students allowed in this subject offering
        max_students = subject_offering.max_students

        # Get the remaining quota
        remaining = subject_offering.remaining_quota()

        # Create the label
        label = f"{subject_offering.subject.name}"

        if subject_offering.teacher:
            label += f" ({subject_offering.teacher.get_full_name()})"

        # Add enrollment information
        label += f" [{num_students}/{max_students}]"

        # Add a warning if the subject offering is almost full
        if remaining <= 3 and remaining > 0:
            label += f" ({_('Only %d spots left!') % remaining})"

        # Add a warning if the subject offering is full
        if remaining <= 0:
            label += f" ({_('FULL')})"

        return label

    def clean(self) -> None:
        """
        Validate the form

        Checks that:
        - The member is not enrolled in subject offerings with conflicting time slots
        - The member is not enrolled in more than one subject offering per time slot
        - The subject offerings are not full
        """
        cleaned_data = super().clean()

        # Get the selected subject offerings
        selected_offerings = {}

        for field_name, value in cleaned_data.items():
            if field_name.startswith("timeslot_") and value:
                time_slot_id = int(field_name.split("_")[1])
                offering_id = int(value)

                # Get the time slot and subject offering
                try:
                    time_slot = TimeSlot.objects.get(id=time_slot_id)
                    offering = SubjectOffering.objects.get(id=offering_id)
                except (TimeSlot.DoesNotExist, SubjectOffering.DoesNotExist):
                    self.add_error(field_name, _("Invalid selection"))
                    continue

                # Check if the subject offering is full
                if offering.remaining_quota() <= 0:
                    self.add_error(field_name, _("This subject offering is full"))

                # Add the time slot and subject offering to the selected offerings
                selected_offerings[time_slot] = offering

        # Check for time slot conflicts
        time_slots_dict = {}

        for time_slot, offering in selected_offerings.items():
            if time_slot in time_slots_dict:
                self.add_error(
                    f"timeslot_{time_slot.id}",
                    _("Time slot conflict: %(time_slot)s is used by both %(offering1)s and %(offering2)s")
                    % {
                        "time_slot": time_slot,
                        "offering1": time_slots_dict[time_slot].subject.name,
                        "offering2": offering.subject.name,
                    },
                )
            time_slots_dict[time_slot] = offering

        return cleaned_data
