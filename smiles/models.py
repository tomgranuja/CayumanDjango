import datetime

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


class BaseModel(models.Model):
    """
    Abstract base model providing common fields for all models.

    Attributes:
        created_at: DateTime when the record was created
        updated_at: DateTime when the record was last updated
    """

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Member(BaseModel):
    """
    Extension of the User model for the school management system.

    This model extends Django's User model to add school-specific information.
    It represents any individual in the system (students, teachers, staff, etc.).

    Attributes:
        user: The Django User this Member extends
        metadata: Flexible JSON field for storing additional member data such as:
            - special_conditions (ASD, ADHD, etc.)
            - educational_accommodations
            - emotional_support_plan
            - other custom attributes
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="member_profile")
    metadata = models.JSONField(default=dict, blank=True, help_text=_("Flexible attributes for this member"))

    def __str__(self):
        return self.user.get_full_name() or self.user.username


class Group(BaseModel):
    """
    Represents a specific group within the school.

    Groups can represent any type of grouping used in the school, such as
    grades, cycles, teams, houses, etc.

    Attributes:
        name: Name of this specific group
        group_type: The type of group (e.g., "Grade", "Cycle", "Team")
        description: Detailed description
        is_primary: Whether members must belong to one group of this type
        properties: Flexible JSON field for type-specific properties
        metadata: Flexible storage for this specific group's attributes
        parent: Optional parent group (for hierarchical structures)
    """

    name = models.CharField(max_length=100)
    group_type = models.CharField(max_length=50, help_text=_("The type of group (e.g., Grade, Cycle, Team)"))
    description = models.TextField(blank=True)
    is_primary = models.BooleanField(default=False, help_text=_("Whether members must belong to exactly one group of this type"))
    properties = models.JSONField(default=dict, blank=True, help_text=_("Properties specific to this type of group"))
    metadata = models.JSONField(default=dict, blank=True, help_text=_("Attributes specific to this group instance"))
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="child_groups")

    class Meta:
        unique_together = [["name", "group_type"]]

    def __str__(self):
        return f"{self.name} ({self.group_type})"


class Term(BaseModel):
    """
    Represents a specific time period in the school calendar.

    Terms can represent any type of time period used in the school, such as
    semesters, quarters, workshop periods, academic years, etc.

    Attributes:
        name: Name of this specific term
        term_type: The type of term (e.g., "Semester", "Quarter", "Workshop Period")
        description: Detailed description
        has_enrollment_period: Whether this term type has enrollment periods
        properties: Flexible JSON field for type-specific properties
        date_start: When this term begins
        date_end: When this term ends
        metadata: Flexible storage for term-specific attributes, which may include:
            - enrollment_start: When enrollment begins
            - enrollment_end: When enrollment ends
            - preview_date: When information becomes visible
    """

    name = models.CharField(max_length=100)
    term_type = models.CharField(max_length=50, help_text=_("The type of term (e.g., Semester, Quarter)"))
    description = models.TextField(blank=True)
    has_enrollment_period = models.BooleanField(default=False, help_text=_("Whether this term type has enrollment periods"))
    properties = models.JSONField(default=dict, blank=True, help_text=_("Properties specific to this type of term"))
    date_start = models.DateField()
    date_end = models.DateField()
    metadata = models.JSONField(default=dict, blank=True, help_text=_("Attributes specific to this term instance"))

    def clean(self):
        if self.date_start >= self.date_end:
            raise ValidationError(_("Start date must be before end date"))

        # Check for overlapping terms of the same type
        overlapping = Term.objects.filter(term_type=self.term_type, date_start__lt=self.date_end, date_end__gt=self.date_start)
        if self.pk:
            overlapping = overlapping.exclude(pk=self.pk)
        if overlapping.exists():
            raise ValidationError(_("This term overlaps with another term of the same type"))

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    class Meta:
        ordering = ["-date_start"]

    def __str__(self):
        return f"{self.name} ({self.term_type}: {self.date_start} to {self.date_end})"

    def get_enrollment_periods(self):
        """
        Returns a list of enrollment periods defined for this term.
        Enrollment periods can be defined in the metadata JSON field.

        Returns:
            List of dicts with enrollment period info (name, start, end, groups)
        """
        return self.metadata.get("enrollment_periods", [])

    def add_enrollment_period(self, name, start_date, end_date, group_types=None):
        """
        Adds an enrollment period to this term.

        Args:
            name: Name of the enrollment period (e.g., "Early enrollment", "Regular")
            start_date: When this enrollment period starts
            end_date: When this enrollment period ends
            group_types: Optional list of group types this applies to

        Returns:
            Self for method chaining
        """
        if "enrollment_periods" not in self.metadata:
            self.metadata["enrollment_periods"] = []

        self.metadata["enrollment_periods"].append(
            {
                "name": name,
                "start_date": start_date.isoformat() if isinstance(start_date, datetime.date) else start_date,
                "end_date": end_date.isoformat() if isinstance(end_date, datetime.date) else end_date,
                "group_types": group_types,
            }
        )

        self.save()
        return self


class SubjectType(BaseModel):
    """
    Defines a type of subject offered in the school.

    This allows schools to define their own subject classifications without
    being limited to predefined concepts like "workshop" or "academic subject".

    Examples: Workshop, Academic Subject, Extracurricular, Club, etc.

    Attributes:
        name: Name of this subject type
        description: Detailed description
        is_selectable: Whether students can choose subjects of this type
        properties: Flexible JSON field for properties specific to this subject type
    """

    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    is_selectable = models.BooleanField(default=False, help_text=_("Whether students can choose subjects of this type"))
    properties = models.JSONField(default=dict, blank=True, help_text=_("Define properties specific to this subject type"))

    def __str__(self):
        return self.name


class Subject(BaseModel):
    """
    Represents a specific subject taught at the school.

    Subjects are concrete instances of SubjectTypes. For example, if "Academic Subject" is a SubjectType,
    "Mathematics" would be a Subject.

    Attributes:
        name: Name of this specific subject
        type: The SubjectType this subject belongs to
        description: Detailed description
        metadata: Flexible storage for subject-specific attributes, which may include:
            - curriculum_links: URLs to official curriculum
            - learning_objectives: Key learning goals
            - required_materials: Materials needed
    """

    name = models.CharField(max_length=100)
    type = models.ForeignKey(SubjectType, on_delete=models.PROTECT, related_name="subjects")
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True, help_text=_("Subject-specific attributes like curriculum links"))

    class Meta:
        unique_together = [["name", "type"]]

    def __str__(self):
        return f"{self.name} ({self.type.name})"


class SubjectOffering(BaseModel):
    """
    Represents a specific offering of a subject during a term.

    This is the equivalent of a course instance - a specific time when a subject
    is taught by a specific teacher to specific groups.

    Attributes:
        subject: The subject being offered
        term: When this subject is being offered
        teacher: Who is teaching this subject (optional)
        max_students: Maximum enrollment (0 = unlimited)
        eligible_groups: Which groups can take this subject
        preview_date: When this offering becomes visible to students (default: term start)
        enrollment_start: When enrollment begins for this offering
        enrollment_end: When enrollment ends for this offering
        metadata: Flexible storage for offering-specific attributes
        enrollment_event: Evento de inscripción asociado
    """

    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="offerings")
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name="subject_offerings")
    teacher = models.ForeignKey(Member, on_delete=models.SET_NULL, null=True, blank=True, related_name="teaching_offerings")
    max_students = models.PositiveIntegerField(default=0, help_text=_("0 means unlimited"))
    eligible_groups = models.ManyToManyField(Group, related_name="eligible_offerings")

    # Enrollment period fields
    preview_date = models.DateField(null=True, blank=True, help_text=_("When this offering becomes visible to members"))
    enrollment_start = models.DateTimeField(null=True, blank=True, help_text=_("When enrollment begins for this offering"))
    enrollment_end = models.DateField(null=True, blank=True, help_text=_("When enrollment ends for this offering"))

    metadata = models.JSONField(default=dict, blank=True, help_text=_("Offering-specific attributes"))

    enrollment_event = models.ForeignKey(
        "Event", null=True, blank=True, related_name="subject_offerings", help_text=_("Evento de inscripción asociado")
    )

    def __str__(self):
        return f"{self.subject.name} ({self.term.name})"

    def clean(self):
        # Only apply enrollment validations if the subject is selectable
        if self.subject.is_selectable:
            # Default preview_date to term start if not provided
            if not self.preview_date:
                self.preview_date = self.term.date_start

            # Default enrollment_start to preview_date if not provided
            if not self.enrollment_start:
                self.enrollment_start = datetime.datetime.combine(self.preview_date, datetime.time(0, 0))

            # Default enrollment_end to term start if not provided
            if not self.enrollment_end:
                self.enrollment_end = self.term.date_start

            # Validate date sequence
            if self.preview_date and self.enrollment_start and self.preview_date > self.enrollment_start.date():
                raise ValidationError(_("Preview date must be before enrollment start date"))

            if self.enrollment_start and self.enrollment_end and self.enrollment_start.date() > self.enrollment_end:
                raise ValidationError(_("Enrollment start date must be before enrollment end date"))

            if self.enrollment_end and self.term.date_start and self.enrollment_end > self.term.date_start:
                raise ValidationError(_("Enrollment end date must be before or on term start date"))
        else:
            # If not selectable, clear enrollment fields to avoid confusion
            self.preview_date = None
            self.enrollment_start = None
            self.enrollment_end = None

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def count_students(self):
        """Returns the number of students enrolled in this offering"""
        return self.enrolled_members.count()

    def remaining_quota(self):
        """Returns the remaining available slots, or None if unlimited"""
        if self.max_students == 0:
            return None
        return self.max_students - self.count_students()

    def is_visible_for_preview(self):
        """Returns True if the offering is visible for preview"""
        if not self.subject.is_selectable:
            return True

        today = datetime.date.today()
        return self.preview_date is not None and self.preview_date <= today

    def is_open_for_enrollment(self):
        """Returns True if enrollment is currently open for this offering"""
        if not self.subject.is_selectable:
            return False

        if self.enrollment_event:
            return self.enrollment_event.is_current()
        else:
            now = datetime.datetime.now()
            today = now.date()

            enrollment_started = self.enrollment_start is not None and self.enrollment_start <= now
            enrollment_not_ended = self.enrollment_end is None or self.enrollment_end >= today
            term_not_ended = self.term.date_end >= today

            return enrollment_started and enrollment_not_ended and term_not_ended


class MemberGroupAssignment(BaseModel):
    """
    Associates a member with a group and tracks the enrollment history.

    This model handles both the group membership (like what grade or cycle a student belongs to)
    and subject enrollment (what courses they're taking).

    Attributes:
        member: The member being assigned
        group: The group they're assigned to
        date_assigned: When this assignment happened
        subject_offerings: What subjects they're taking within this group
        is_active: Whether this assignment is currently active
        metadata: Flexible storage for assignment-specific attributes
    """

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="group_assignments")
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="member_assignments")
    date_assigned = models.DateField(auto_now_add=True)
    subject_offerings = models.ManyToManyField(SubjectOffering, blank=True, related_name="enrolled_members")
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True, help_text=_("Assignment-specific attributes"))

    class Meta:
        unique_together = [["member", "group", "is_active"]]

    def __str__(self):
        return f"{self.member} in {self.group}"


class ActivityType(BaseModel):
    """
    Defines a type of activity that can be scheduled.

    This allows for classifying different kinds of scheduled activities, whether
    they are classes, breaks, assemblies, etc.

    Examples: Class Session, Lunch, Break, Assembly, Field Trip

    Attributes:
        name: Name of this activity type
        description: Detailed description
        is_selectable: Whether students can choose activities of this type
        requires_attendance: Whether attendance should be tracked
        metadata: Flexible attributes for this activity type
    """

    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    is_selectable = models.BooleanField(default=False, help_text=_("Whether students can choose activities of this type"))
    requires_attendance = models.BooleanField(default=True, help_text=_("Whether attendance should be tracked"))
    metadata = models.JSONField(default=dict, blank=True, help_text=_("Activity type-specific attributes"))

    def __str__(self):
        return self.name


class Activity(BaseModel):
    """
    Represents a specific activity that can be scheduled.

    Activities are concrete instances of ActivityTypes. For example, if "Class Session" is an ActivityType,
    "Math Class" would be an Activity.

    Attributes:
        name: Name of this specific activity
        type: The ActivityType this activity belongs to
        description: Detailed description
        subject_offering: Optional link to a subject offering
        applicable_groups: Which groups this activity applies to
        metadata: Flexible storage for activity-specific attributes
    """

    name = models.CharField(max_length=100)
    type = models.ForeignKey(ActivityType, on_delete=models.PROTECT, related_name="activities")
    description = models.TextField(blank=True)
    subject_offering = models.ForeignKey(SubjectOffering, on_delete=models.SET_NULL, null=True, blank=True, related_name="activities")
    applicable_groups = models.ManyToManyField(Group, related_name="applicable_activities")
    metadata = models.JSONField(default=dict, blank=True, help_text=_("Activity-specific attributes"))

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Activities"


class TimeSlot(BaseModel):
    """
    Represents a recurring time slot in a schedule.

    Time slots define when activities can take place during a standard week.

    Attributes:
        name: Name of this time slot
        day_of_week: Which day of the week
        time_start: Starting time
        time_end: Ending time
        metadata: Flexible storage for time slot-specific attributes
    """

    DAY_CHOICES = (
        ("monday", _("Monday")),
        ("tuesday", _("Tuesday")),
        ("wednesday", _("Wednesday")),
        ("thursday", _("Thursday")),
        ("friday", _("Friday")),
        ("saturday", _("Saturday")),
        ("sunday", _("Sunday")),
    )

    name = models.CharField(max_length=100)
    day_of_week = models.CharField(max_length=10, choices=DAY_CHOICES)
    time_start = models.TimeField()
    time_end = models.TimeField()
    metadata = models.JSONField(default=dict, blank=True, help_text=_("Time slot-specific attributes"))

    def clean(self):
        if self.time_start >= self.time_end:
            raise ValidationError(_("Start time must be before end time"))

        # Check for overlapping time slots on the same day
        overlapping = TimeSlot.objects.filter(day_of_week=self.day_of_week, time_start__lt=self.time_end, time_end__gt=self.time_start)
        if self.pk:
            overlapping = overlapping.exclude(pk=self.pk)
        if overlapping.exists():
            raise ValidationError(_("This time slot overlaps with another time slot on the same day"))

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name}: {self.get_day_of_week_display()} {self.time_start.strftime('%H:%M')} - {self.time_end.strftime('%H:%M')}"


class ScheduleTemplate(BaseModel):
    """
    Defines a template for a schedule that can be applied to groups.

    Schedule templates provide the default scheduling pattern for groups.

    Attributes:
        name: Name of this schedule template
        description: Detailed description
        applicable_groups: Which groups use this template
        applicable_terms: During which terms this template applies
        metadata: Flexible storage for template-specific attributes
    """

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    applicable_groups = models.ManyToManyField(Group, related_name="schedule_templates")
    applicable_terms = models.ManyToManyField(Term, related_name="schedule_templates")
    metadata = models.JSONField(default=dict, blank=True, help_text=_("Template-specific attributes"))

    def __str__(self):
        return self.name


class ScheduleAssignment(BaseModel):
    """
    Maps time slots to activities within a schedule template.

    This defines what activity happens during each time slot in a schedule template.

    Attributes:
        template: The schedule template this assignment belongs to
        time_slot: When the activity happens
        activity: What activity happens during this time slot
        metadata: Flexible storage for assignment-specific attributes
    """

    template = models.ForeignKey(ScheduleTemplate, on_delete=models.CASCADE, related_name="assignments")
    time_slot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE, related_name="template_assignments")
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name="schedule_assignments")
    metadata = models.JSONField(default=dict, blank=True, help_text=_("Assignment-specific attributes"))

    class Meta:
        unique_together = [["template", "time_slot"]]

    def __str__(self):
        return f"{self.activity} at {self.time_slot} in {self.template}"


class MemberSchedule(BaseModel):
    """
    Represents an individual member's schedule for a term.

    This is derived from a schedule template but can be customized for the individual.

    Attributes:
        member: The member this schedule is for
        term: During which term this schedule applies
        template: The base template this schedule derives from
        is_custom: Whether this has been customized from the template
        metadata: Flexible storage for schedule-specific attributes
    """

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="schedules")
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name="member_schedules")
    template = models.ForeignKey(ScheduleTemplate, on_delete=models.PROTECT, related_name="member_schedules")
    is_custom = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True, help_text=_("Schedule-specific attributes"))

    class Meta:
        unique_together = [["member", "term"]]

    def __str__(self):
        return f"{self.member}'s schedule for {self.term}"


class MemberScheduleOverride(BaseModel):
    """
    Represents an override to a member's schedule.

    This allows for individual customization of schedules or one-time exceptions.

    Attributes:
        member_schedule: The schedule being overridden
        date: Specific date this override applies to (null means recurring)
        time_slot: Which time slot is being overridden
        activity: The activity replacing the default one
        reason: Why this override exists
        metadata: Flexible storage for override-specific attributes
    """

    member_schedule = models.ForeignKey(MemberSchedule, on_delete=models.CASCADE, related_name="overrides")
    date = models.DateField(null=True, blank=True, help_text=_("Specific date (blank means recurring every week)"))
    time_slot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE, related_name="member_overrides")
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name="schedule_overrides")
    reason = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True, help_text=_("Override-specific attributes"))

    class Meta:
        unique_together = [["member_schedule", "date", "time_slot"]]

    def __str__(self):
        date_str = f" on {self.date}" if self.date else " (recurring)"
        return f"{self.activity} for {self.member_schedule.member}{date_str}"


class SpecialDay(BaseModel):
    """
    Represents a special day in the school calendar.

    Special days can override regular schedules for specific dates (holidays, events, etc.).

    Attributes:
        name: Name of this special day
        date: When this special day occurs
        affects_groups: Which groups are affected by this special day
        is_school_closed: Whether school is closed on this day
        alternate_schedule: Optional alternative schedule to use
        metadata: Flexible storage for special day-specific attributes
    """

    name = models.CharField(max_length=100)
    date = models.DateField()
    affects_groups = models.ManyToManyField(Group, related_name="special_days", blank=True, help_text=_("Empty means all groups are affected"))
    is_school_closed = models.BooleanField(default=False)
    alternate_schedule = models.ForeignKey(ScheduleTemplate, on_delete=models.SET_NULL, null=True, blank=True, related_name="special_days")
    metadata = models.JSONField(default=dict, blank=True, help_text=_("Special day-specific attributes"))

    class Meta:
        unique_together = [["name", "date"]]

    def __str__(self):
        return f"{self.name} ({self.date})"


class Attendance(BaseModel):
    """
    Tracks attendance for scheduled activities.

    This model records whether members attended specific activities and can
    track early dismissals or late arrivals.

    Attributes:
        member: The member whose attendance is being recorded
        date: Which date this attendance record is for
        time_slot: Which time slot this attendance record is for
        activity: Which activity this attendance record is for
        attended: Whether the member attended
        early_dismissal_time: When the member left early (if applicable)
        late_arrival_time: When the member arrived late (if applicable)
        notes: Additional notes about this attendance record
        recorded_by: Who recorded this attendance
        metadata: Flexible storage for attendance-specific attributes
    """

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="attendance_records")
    date = models.DateField()
    time_slot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE, related_name="attendance_records")
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name="attendance_records")
    attended = models.BooleanField(default=True)
    early_dismissal_time = models.TimeField(null=True, blank=True)
    late_arrival_time = models.TimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(Member, on_delete=models.SET_NULL, null=True, related_name="recorded_attendance")
    metadata = models.JSONField(default=dict, blank=True, help_text=_("Attendance-specific attributes"))

    class Meta:
        unique_together = [["member", "date", "time_slot"]]

    def __str__(self):
        status = "attended" if self.attended else "absent from"
        return f"{self.member} {status} {self.activity} on {self.date}"


class EnrollmentService:
    """
    Service class for handling enrollment-related operations.
    This centralizes enrollment business logic outside of models.
    """

    @staticmethod
    def get_available_offerings(member, term=None):
        """
        Returns subject offerings available for enrollment for a member.

        Args:
            member: The member who is enrolling
            term: Optional specific term to check (default: current term)

        Returns:
            QuerySet of SubjectOffering objects available for enrollment
        """
        # Get member's groups
        member_groups = Group.objects.filter(member_assignments__member=member, member_assignments__is_active=True)

        # Get current term if not specified
        if not term:
            today = datetime.date.today()
            term = Term.objects.filter(date_start__lte=today, date_end__gte=today).first()
            if not term:
                return SubjectOffering.objects.none()

        # Get offerings that:
        # 1. Are for selectable subjects
        # 2. Are in the specified term
        # 3. Are eligible for the member's groups
        # 4. Are within enrollment period
        # 5. Have available space (or unlimited)
        now = datetime.datetime.now()

        offerings = SubjectOffering.objects.filter(
            subject__is_selectable=True,
            term=term,
            eligible_groups__in=member_groups,
            enrollment_start__lte=now,
            enrollment_end__gte=now.date(),
        ).distinct()

        # Filter by available space - have to do this in Python since it depends on a calculated field
        return [o for o in offerings if o.max_students == 0 or o.remaining_quota() > 0]

    @staticmethod
    def can_enroll(member, offering):
        """
        Checks if a member can enroll in a specific offering.

        Args:
            member: The member who wants to enroll
            offering: The SubjectOffering to check

        Returns:
            (bool, str): (Can enroll, reason if can't)
        """
        # Check if subject is selectable
        if not offering.subject.is_selectable:
            return False, "This subject is not selectable"

        # Check if enrollment is open
        if not offering.is_open_for_enrollment():
            return False, "Enrollment is not currently open for this offering"

        # Check if member belongs to eligible groups
        member_groups = Group.objects.filter(member_assignments__member=member, member_assignments__is_active=True)

        if not offering.eligible_groups.filter(id__in=member_groups.values_list("id", flat=True)).exists():
            return False, "You are not in an eligible group for this subject"

        # Check if offering has space
        if offering.max_students > 0 and offering.remaining_quota() <= 0:
            return False, "This offering has reached its maximum enrollment"

        # Check for schedule conflicts - simplified example
        # In a real implementation, this would be more sophisticated
        member_schedule = MemberSchedule.objects.filter(member=member, term=offering.term).first()
        if member_schedule:
            # Check for conflicts with existing activities
            # This is a simplified check - real implementation would be more detailed
            for activity in offering.activities.all():
                for time_slot in activity.schedule_assignments.all().values_list("time_slot_id", flat=True):
                    if activity.schedule_assignments.filter(time_slot_id=time_slot).exists():
                        return False, "This offering conflicts with your schedule"

        return True, ""


class EventType(BaseModel):
    """
    Define tipos de eventos en el calendario académico.
    """

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return self.name


class Event(BaseModel):
    """
    Representa un evento calendarizado en la institución.

    Los eventos pueden ser de diferentes tipos: inscripciones, evaluaciones,
    ceremonias, reuniones, etc.
    """

    name = models.CharField(max_length=100)
    type = models.ForeignKey(EventType, on_delete=models.PROTECT, related_name="events")
    date_start = models.DateTimeField()
    date_end = models.DateTimeField()
    affects_groups = models.ManyToManyField(Group, blank=True, related_name="events")
    affects_subjects = models.ManyToManyField(Subject, blank=True, related_name="events")
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.name} ({self.date_start} a {self.date_end})"

    def is_current(self):
        """Verifica si el evento está actualmente en curso"""
        now = datetime.datetime.now()
        return self.date_start <= now <= self.date_end
