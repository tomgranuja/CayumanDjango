import datetime
from functools import lru_cache
from typing import Dict
from typing import ForwardRef
from typing import Set
from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from cayuman.models import Member

# Import Member from cayuman instead of defining a new one

# Use forward references to prevent circular imports
if TYPE_CHECKING:
    from .models import TimeSlot, SubjectOffering
else:
    TimeSlot = ForwardRef("TimeSlot")
    SubjectOffering = ForwardRef("SubjectOffering")


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

    @property
    def human_name(self):
        """
        Returns a more human-readable name for the term.

        Returns:
            str: A formatted name including month and year information
        """
        from django.utils.formats import date_format
        from django.utils import timezone

        now = timezone.now()

        month_1 = date_format(self.date_start, format="F")
        month_2 = date_format(self.date_end, format="F")

        if month_1 != month_2:
            name = f"{self.name} ({month_1}-{month_2})"
        else:
            name = f"{self.name} ({month_1} {self.date_start.year})"

        if now.year != self.date_start.year:
            name = f"{name} {self.date_start.year}"

        return name

    @property
    def count_weeks(self):
        """
        Count the total number of weeks this term lasts.

        Returns:
            int: The number of weeks in the term
        """
        from datetime import timedelta

        # Count the number of Mondays in the term
        days_until_monday = (7 - self.date_start.weekday() + 0) % 7  # 0 is Monday
        first_monday = self.date_start + timedelta(days=days_until_monday)

        # Count the Mondays
        monday_count = 0
        current_date = first_monday
        while current_date <= self.date_end:
            monday_count += 1
            current_date += timedelta(days=7)  # Move to the next Monday

        return monday_count

    def is_current(self):
        """
        Check if this is the current term.

        Returns:
            bool: True if this is the current term
        """
        from django.utils import timezone

        now = timezone.now().date()
        return self.date_start <= now <= self.date_end

    def is_in_the_past(self):
        """
        Check if this term is in the past.

        Returns:
            bool: True if this term is in the past
        """
        from django.utils import timezone

        now = timezone.now().date()
        return self.date_end < now

    def is_in_the_future(self):
        """
        Check if this term is in the future.

        Returns:
            bool: True if this term is in the future
        """
        from django.utils import timezone

        now = timezone.now().date()
        preview_date = self.get_preview_date()
        return now < preview_date if preview_date else False

    def get_preview_date(self):
        """
        Get the preview date for this term.

        Returns:
            date: The preview date, or None if not set
        """
        import dateutil.parser

        # First try to find enrollment events
        enrollment_events = self.events.filter(type__name="Enrollment", is_active=True).order_by("preview_date")

        # Use the earliest preview date from enrollment events
        if enrollment_events.exists():
            earliest_event = enrollment_events.first()
            if earliest_event.preview_date:
                return earliest_event.preview_date.date()

        # Fall back to metadata if no events found
        preview_date = self.metadata.get("preview_date")
        if preview_date:
            if isinstance(preview_date, str):
                return dateutil.parser.parse(preview_date).date()
            return preview_date

        # If no preview date is set, use the start date of the first enrollment period
        enrollment_periods = self.get_enrollment_periods()
        if enrollment_periods:
            first_period = enrollment_periods[0]
            start_date = first_period.get("start_date")
            if start_date:
                if isinstance(start_date, str):
                    return dateutil.parser.parse(start_date).date()
                return start_date

        return None

    def is_enabled_to_preview(self):
        """
        Check if this term is enabled for preview.

        Returns:
            bool: True if this term is enabled for preview
        """
        from django.utils import timezone

        now = timezone.now().date()

        # First check for enrollment events
        enrollment_events = self.events.filter(type__name="Enrollment", is_active=True)

        for event in enrollment_events:
            if event.is_preview_enabled():
                return True

        # Fall back to direct fields if no events
        preview_date = self.get_preview_date()

        if preview_date:
            return preview_date <= now <= self.date_end

        # If no preview date, check if enrollment has started
        enrollment_periods = self.get_enrollment_periods()
        if enrollment_periods:
            first_period = enrollment_periods[0]
            start_date = first_period.get("start_date")
            if start_date:
                if isinstance(start_date, str):
                    import dateutil.parser

                    start_date = dateutil.parser.parse(start_date)
                return start_date <= timezone.now() and self.date_end >= now

        return False

    def is_enabled_to_enroll(self):
        """
        Check if this term is enabled for enrollment.

        Returns:
            bool: True if this term is enabled for enrollment
        """
        from django.utils import timezone

        now = timezone.now()
        now_date = now.date()

        # It's never possible to enroll after the term ends
        if now_date > self.date_end:
            return False

        # First check for enrollment events
        enrollment_events = self.events.filter(type__name="Enrollment", is_active=True)

        for event in enrollment_events:
            if event.is_enrollment_open():
                return True

        # Check if any enrollment period is active
        enrollment_periods = self.get_enrollment_periods()
        for period in enrollment_periods:
            start_date = period.get("start_date")
            end_date = period.get("end_date")

            if not start_date or not end_date:
                continue

            if isinstance(start_date, str):
                import dateutil.parser

                start_date = dateutil.parser.parse(start_date)

            if isinstance(end_date, str):
                import dateutil.parser

                end_date = dateutil.parser.parse(end_date).date()

            if start_date <= now and now_date <= end_date:
                return True

        return False

    def get_enrollment_period(self, name):
        """
        Get a specific enrollment period by name.

        Args:
            name: The name of the enrollment period to get

        Returns:
            dict: The enrollment period, or None if not found
        """
        enrollment_periods = self.get_enrollment_periods()
        for period in enrollment_periods:
            if period.get("name") == name:
                return period
        return None

    def get_enrollment_periods(self):
        """
        Returns a list of enrollment periods defined for this term.
        Enrollment periods can be defined in the metadata JSON field.

        Returns:
            List of dicts with enrollment period info
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
        enrollment_event: Event that controls enrollment for this offering
        metadata: Flexible storage for offering-specific attributes
    """

    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="offerings")
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name="subject_offerings")
    teacher = models.ForeignKey(Member, on_delete=models.SET_NULL, null=True, blank=True, related_name="teaching_offerings")
    max_students = models.PositiveIntegerField(default=0, help_text=_("0 means unlimited"))
    eligible_groups = models.ManyToManyField(Group, related_name="eligible_offerings")

    # The enrollment event manages all enrollment periods
    enrollment_event = models.ForeignKey(
        "Event",
        null=True,
        blank=True,
        related_name="subject_offerings",
        help_text=_("Enrollment event associated with this offering"),
        on_delete=models.SET_NULL,
    )

    metadata = models.JSONField(default=dict, blank=True, help_text=_("Offering-specific attributes"))

    def __str__(self):
        return f"{self.subject.name} ({self.term.name})"

    def count_classes(self):
        """
        Count the total number of class sessions for this offering.

        Returns:
            int: The number of class sessions
        """
        num_weeks = self.term.count_weeks
        return num_weeks * self.activities.aggregate(total_slots=models.Count("schedule_assignments__time_slot", distinct=True))["total_slots"] or 0

    def count_students(self, exclude_member=None):
        """
        Count the number of students enrolled in this offering.

        Args:
            exclude_member: Optional member to exclude from count

        Returns:
            int: The number of enrolled students
        """
        assignments = MemberGroupAssignment.objects.filter(subject_offerings=self)
        if exclude_member:
            assignments = assignments.exclude(member=exclude_member)
        return assignments.count()

    def remaining_quota(self, include_member=None):
        """
        Calculate remaining enrollment quota for this offering.

        Args:
            include_member: Optional member to include in available quota
                           (e.g., if they're already enrolled and we're checking
                            if they could be re-enrolled)

        Returns:
            int: Number of spots left, or -1 if unlimited
        """
        if self.max_students == 0:  # Unlimited
            return -1

        current = self.count_students(exclude_member=include_member)
        return self.max_students - current

    def is_open_for_enrollment(self):
        """
        Check if this offering is currently open for enrollment.

        Returns:
            bool: True if enrollment is open
        """
        if not self.enrollment_event:
            return False

        return self.enrollment_event.is_enrollment_open()

    def is_preview_enabled(self):
        """
        Check if preview is enabled for this offering.

        Returns:
            bool: True if preview is enabled
        """
        if not self.enrollment_event:
            return False

        return self.enrollment_event.is_preview_enabled()


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

    @lru_cache(maxsize=None)
    def subject_offerings_by_time_slot(self, time_slot=None, term=None) -> Dict[TimeSlot, "SubjectOffering"]:
        """
        Return this member's subject offerings given a time slot, or all of them if no time slot given.

        Args:
            time_slot: Optional TimeSlot to filter by
            term: Optional Term to filter by

        Returns:
            Dict[TimeSlot, SubjectOffering]: Dictionary mapping time slots to subject offerings
        """
        output = {}
        for offering in self.subject_offerings.all():
            if term and offering.term != term:
                continue
            for activity in offering.activities.all():
                for assignment in activity.schedule_assignments.all():
                    if time_slot is None or assignment.time_slot == time_slot:
                        output[assignment.time_slot] = offering
        return output

    @lru_cache(maxsize=None)
    def subject_offerings_by_term(self, term) -> Set:
        """
        Return this member's subject offerings for a given term.

        Args:
            term: The Term to filter by

        Returns:
            Set[SubjectOffering]: Set of subject offerings for the term
        """
        offerings_by_time_slot = self.subject_offerings_by_time_slot(term=term)
        return {offering for offering in offerings_by_time_slot.values()}

    def is_current(self):
        """
        Check if this is the current active group assignment for the member.

        Returns:
            bool: True if this is the current active assignment
        """
        if self.member.current_student_cycle:
            return self.id == self.member.current_student_cycle.id
        return False

    @lru_cache(maxsize=None)
    def is_schedule_full(self, term) -> bool:
        """
        Check if the member's schedule is full for the given term.

        Args:
            term: The Term to check

        Returns:
            bool: True if all available time slots are filled
        """
        # Count all available time slots for this term
        time_slot_count = (
            TimeSlot.objects.filter(
                schedule_assignments__activity__subject_offering__term=term,
                schedule_assignments__activity__subject_offering__eligible_groups=self.group,
            )
            .distinct()
            .count()
        )

        # Count how many time slots this member has filled
        filled_slots = len(self.subject_offerings_by_time_slot(term=term))

        return time_slot_count == filled_slots

    def is_enabled_to_enroll(self, term) -> bool:
        """
        Check if the member is enabled to enroll in the given term.

        Args:
            term: The Term to check

        Returns:
            bool: True if the member can enroll in the term
        """
        from django.utils import timezone

        now = timezone.now()
        now_date = now.date()

        # It's never possible to enroll before enrollment_start and after date_end
        if not term.is_enabled_to_enroll():
            return False

        # Get the enrollment period
        enrollment_period = term.get_enrollment_period("Regular")
        if not enrollment_period:
            return False

        enrollment_start = enrollment_period.get("start_date")
        enrollment_end = enrollment_period.get("end_date")

        if not enrollment_start or not enrollment_end:
            return False

        # Students with full schedule can only re-enroll between enrollment_start and enrollment_end
        if self.is_schedule_full(term):
            if enrollment_start <= now and now_date <= enrollment_end:
                return True
        else:
            # Students without full schedule can enroll anytime until date_end
            if now_date <= term.date_end:
                return True

        return False

    def save(self, *args, **kwargs):
        """Override save to clear caches"""
        # Clear caches before saving
        if hasattr(self, "subject_offerings_by_time_slot"):
            self.subject_offerings_by_time_slot.cache_clear()
        if hasattr(self, "is_schedule_full"):
            self.is_schedule_full.cache_clear()
        if hasattr(self, "subject_offerings_by_term"):
            self.subject_offerings_by_term.cache_clear()

        super().save(*args, **kwargs)


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

        now = datetime.datetime.now()

        # Get offerings with active enrollment events
        offerings = SubjectOffering.objects.filter(
            subject__type__is_selectable=True,
            term=term,
            eligible_groups__in=member_groups,
            enrollment_event__is_active=True,
            enrollment_event__date_start__lte=now,
            enrollment_event__date_end__gte=now,
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
        if not offering.subject.type.is_selectable:
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
    Represents a scheduled event in the institution.

    Events can be of different types: enrollments, evaluations,
    ceremonies, meetings, etc.
    """

    name = models.CharField(max_length=100)
    type = models.ForeignKey(EventType, on_delete=models.PROTECT, related_name="events")
    term = models.ForeignKey(
        Term, on_delete=models.CASCADE, related_name="events", null=True, blank=True, help_text=_("Term this event is associated with")
    )
    preview_date = models.DateTimeField(null=True, blank=True, help_text=_("When information about this event becomes visible"))
    date_start = models.DateTimeField()
    date_end = models.DateTimeField()
    affects_groups = models.ManyToManyField(Group, blank=True, related_name="events")
    affects_subjects = models.ManyToManyField(Subject, blank=True, related_name="events")
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.name} ({self.date_start} to {self.date_end})"

    def is_current(self):
        """Check if the event is currently in progress"""
        from django.utils import timezone

        now = timezone.now()
        return self.date_start <= now <= self.date_end

    def is_preview_enabled(self):
        """Check if preview is currently enabled for this event"""
        from django.utils import timezone

        now = timezone.now()
        if self.preview_date:
            return self.preview_date <= now <= self.date_end
        return self.date_start <= now <= self.date_end

    def is_enrollment_open(self):
        """Check if enrollment is currently open for this event"""
        from django.utils import timezone

        now = timezone.now()
        return self.date_start <= now <= self.date_end
