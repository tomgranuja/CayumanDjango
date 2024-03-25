from datetime import datetime
from functools import cached_property
from functools import lru_cache
from typing import Dict
from typing import Optional
from typing import Set

from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from django.contrib.auth.models import UserManager
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Case
from django.db.models import IntegerField
from django.db.models import Value
from django.db.models import When
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _


class Member(User):
    """
    User model holding information for members of the community.
    At the time of writing this we have STUDENTS, TEACHERS and regular users outside both groups
    """

    # use manager from User model
    objects = UserManager()

    @property
    def is_student(self):
        return self.groups.filter(name=settings.STUDENTS_GROUP).exists()

    @property
    def is_teacher(self):
        return self.groups.filter(name=settings.TEACHERS_GROUP).exists()

    @property
    def current_student_cycle(self):
        return StudentCycle.objects.filter(student=self).order_by("-date_joined").first()

    def __str__(self):
        return self.get_full_name()

    def __repr__(self):
        return f"{self.__class__.__name__}(username='{self.username}', first_name='{self.first_name}', last_name='{self.last_name}')"

    class Meta:
        proxy = True
        verbose_name = _("Member")
        verbose_name_plural = _("Members")


@receiver(m2m_changed, sender=Member.groups.through)
def member_groups_changed(sender, instance, action, *args, **kwargs):
    if action == "pre_add":
        # Get all groups associated with current member, including previous ones
        groups = set()
        for g in instance.groups.all():
            groups.add(g)
        for g in Group.objects.filter(id__in=kwargs.get("pk_set")):
            if g in groups:
                raise ValidationError(_("Group is already assigned to this member"))
            groups.add(g)

        try:
            is_teacher = Group.objects.get(name=settings.TEACHERS_GROUP) in groups
        except Group.DoesNotExist:
            is_teacher = False
        try:
            is_student = Group.objects.get(name=settings.STUDENTS_GROUP) in groups
        except Group.DoesNotExist:
            is_student = False

        if not instance.is_staff:
            if not is_student and not is_teacher:
                raise ValidationError(_("User must be either Student or Teacher, or a staff member"))
        else:
            if is_student:
                raise ValidationError(_("Student cannot be staff member"))

        if is_student and is_teacher:
            raise ValidationError(_("User must not be both Student and Teacher"))


class Workshop(models.Model):
    name = models.CharField(max_length=50, verbose_name=_("Name"))
    full_name = models.TextField(blank=True, verbose_name=_("Full Name"))
    description = models.TextField(blank=True, verbose_name=_("Description"))

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"{self.__class__.__name__}(name='{self.name}')"

    class Meta:
        verbose_name = _("Workshop")
        verbose_name_plural = _("Workshops")


class Cycle(models.Model):
    name = models.CharField(max_length=50, verbose_name=_("Name"))
    description = models.TextField(blank=True, verbose_name=_("Description"))

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"{self.__class__.__name__}(name='{self.name}')"

    class Meta:
        verbose_name = _("Cycle")
        verbose_name_plural = _("Cycles")


class ScheduleManager(models.Manager):
    def ordered(self):
        """Returns schedules ordered by week day and time_start"""
        ordering = Case(
            When(day="monday", then=Value(1)),
            When(day="tuesday", then=Value(2)),
            When(day="wednesday", then=Value(3)),
            When(day="thursday", then=Value(4)),
            When(day="friday", then=Value(5)),
            default=Value(6),
            output_field=IntegerField(),
        )

        return self.get_queryset().annotate(day_ordering=ordering).order_by("day_ordering", "time_start")


class Schedule(models.Model):
    """Represent weekly time blocks"""

    CHOICES = (
        ("monday", _("Monday")),
        ("tuesday", _("Tuesday")),
        ("wednesday", _("Wednesday")),
        ("thursday", _("Thursday")),
        ("friday", _("Friday")),
    )

    day = models.CharField(max_length=10, choices=CHOICES, verbose_name=_("Day"))
    time_start = models.TimeField(verbose_name=_("Start time"))
    time_end = models.TimeField(verbose_name=_("End time"))

    objects = ScheduleManager()

    def clean(self):
        # normalize times
        if isinstance(self.time_start, datetime):
            self.time_start = self.time_start.time()
        if isinstance(self.time_end, datetime):
            self.time_end = self.time_end.time()

        # Validate times
        if self.time_start >= self.time_end:
            raise ValidationError(_("Start time must be before end time"))

        # Validate no collisions for the same day
        for schedule in Schedule.objects.filter(day=self.day):
            if self.id and schedule.id == self.id:
                # do not compare against self
                continue
            if self & schedule:
                raise ValidationError(_("There's already another schedule colliding with current one"))

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __and__(self, other):
        """
        Returns True if the schedules overlap, False otherwise
        """
        if self.day != other.day:
            return False

        if self.time_start >= other.time_end or self.time_end <= other.time_start:
            return False

        return True

    def __repr__(self):
        return f"{self.__class__.__name__}(day='{self.day}', time_start='{self.time_start}', time_end='{self.time_end}')"

    def __str__(self):
        return f'{self.get_day_display()} @ {self.time_start.strftime("%H:%M")} - {self.time_end.strftime("%H:%M")}'

    class Meta:
        verbose_name = _("Schedule")
        verbose_name_plural = _("Schedules")


class PeriodManager(models.Manager):
    @lru_cache(maxsize=None)
    def current(self):
        now = datetime.now().date()
        try:
            return self.get_queryset().get(enrollment_start__lte=now, date_end__gt=now)
        except self.model.DoesNotExist:
            return None


class Period(models.Model):
    """Represent a period of time"""

    name = models.CharField(max_length=50, verbose_name=_("Name"))
    description = models.TextField(blank=True, verbose_name=_("Description"))
    enrollment_start = models.DateField(blank=True, verbose_name=_("Enrollment start date"))
    date_start = models.DateField(verbose_name=_("Start date"))
    date_end = models.DateField(verbose_name=_("End date"))

    objects = PeriodManager()

    def __str__(self):
        return _("%(name)s from %(d1)s to %(d2)s") % {"name": self.name, "d1": str(self.date_start), "d2": str(self.date_end)}

    def __repr__(self):
        return f"{self.__class__.__name__}(name='{self.name}', date_start='{self.date_start}', date_end='{self.date_end}')"

    @cached_property
    def human_name(self):
        """Returns a more human name for the period"""
        from django.utils.formats import date_format

        return f"{self.name} ({date_format(self.date_start, format='F')}-{date_format(self.date_end, format='F')})"

    @cached_property
    def count_weeks(self):
        """Count total weeks this period lasts."""
        from datetime import timedelta

        # Trick is done by counting the number of mondays
        days_until_monday = (7 - self.date_start.weekday() + 0) % 7  # 0 is Monday
        first_monday = self.date_start + timedelta(days=days_until_monday)

        # Count the Mondays
        monday_count = 0
        current_date = first_monday
        while current_date <= self.date_end:
            monday_count += 1
            current_date += timedelta(days=7)  # Move to the next Monday

        return monday_count

    def clean(self):
        if self.date_start >= self.date_end:
            raise ValidationError({"start": _("Start date must be before end date")})

        if self.enrollment_start and self.enrollment_start > self.date_start:
            raise ValidationError({"enrollment": _("Enrollment start date must be before start date")})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
        Period.objects.current.cache_clear()

    class Meta:
        verbose_name = _("Period")
        verbose_name_plural = _("Periods")


class WorkshopPeriod(models.Model):
    workshop = models.ForeignKey(Workshop, on_delete=models.CASCADE, verbose_name=_("Workshop"))
    period = models.ForeignKey(Period, on_delete=models.CASCADE, verbose_name=_("Period"))
    teacher = models.ForeignKey(Member, on_delete=models.CASCADE, verbose_name=_("Teacher"))
    max_students = models.PositiveIntegerField(default=0, verbose_name=_("Max Students"))
    cycles = models.ManyToManyField(Cycle, verbose_name=_("Cycles"))
    schedules = models.ManyToManyField(Schedule, verbose_name=_("Schedules"))

    def __str__(self):
        cycles_list = ", ".join(c.name for c in self.cycles.all())
        return f"{self.workshop.name} ({cycles_list}) @ {self.period}"

    def __repr__(self):
        cycles_list = ", ".join(c.name for c in self.cycles.all())
        return f"{self.__class__.__name__}(workshop='{self.workshop.name}', period='{self.period}', teacher='{self.teacher}', cycles='{cycles_list}')"

    def clean(self):
        if not self.teacher.is_teacher:
            raise ValidationError({"teacher": _("Teacher must belong to the `%(g)s` group.") % {"g": settings.TEACHERS_GROUP}})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def count_classes(self):
        num_weeks = self.period.count_weeks
        return num_weeks * self.schedules.count()

    def count_students(self, member: Optional[Member] = None) -> int:
        """Counts the number of students associated to self. If `member` is given counts students but excludes `member`"""
        if member:
            return self.studentcycle_set.exclude(student__id=member.id).count()
        else:
            return self.studentcycle_set.count()

    def remaining_quota(self, member: Optional[Member] = None) -> int:
        """Returns the remaining quota for self. If `member` is given, excludes member. Return None if no max quota."""
        if self.max_students == 0:
            return None

        if member:
            return self.max_students - self.count_students(member)
        else:
            return self.max_students - self.count_students()

    def __and__(self, other):
        """
        Workshop period overlapping is defined based on intersection between their date_start and date_end and their schedules
        """
        # check if date_start and date_end do not overlap
        if not self.id or not other.id:
            return False

        if self.period != other.period:
            return False

        self_schedules = self.schedules.all()
        other_schedules = other.schedules.all()

        # check overlapping due to schedules
        # To-do check based on date_start and end
        for schedule in self_schedules:
            for other_schedule in other_schedules:
                if schedule & other_schedule:
                    return True

        return False

    class Meta:
        verbose_name = _("Workshop's Period")
        verbose_name_plural = _("Workshops' Periods")


class StudentCycle(models.Model):
    """Represents the relationship between students and their cycles and chosen workshop_periods"""

    student = models.ForeignKey(Member, on_delete=models.CASCADE, verbose_name=_("Student"))
    cycle = models.ForeignKey(Cycle, on_delete=models.CASCADE, verbose_name=_("Cycle"))
    date_joined = models.DateField(auto_now_add=True, verbose_name=_("Date joined"))
    workshop_periods = models.ManyToManyField(WorkshopPeriod, blank=True, verbose_name=_("Workshop Periods"))

    def __str__(self):
        return f"{self.student} @ {self.cycle}"

    def __repr__(self):
        return f"{self.__class__.__name__}(student='{self.student}', cycle='{self.cycle}')"

    def clean(self):
        if not self.student.is_student:
            raise ValidationError({"student": _("Student must belong to the `%(g)s` group") % {"g": settings.STUDENTS_GROUP}})

    @lru_cache(maxsize=None)
    def available_workshop_periods_by_schedule(self, period: Optional[Period] = None) -> Dict[Schedule, WorkshopPeriod]:
        """Returns available workshop periods for a student cycle"""
        if period is None:
            period = Period.objects.current()
        if period is None:
            return {}
        ss = Schedule.objects.ordered()

        current_student_cycle = self.cycle if self.cycle else None

        wps_by_schedule = {}
        for s in ss:
            for wp in s.workshopperiod_set.filter(period=period):
                if current_student_cycle in wp.cycles.all():
                    if s not in wps_by_schedule:
                        wps_by_schedule[s] = []
                    wps_by_schedule[s].append(wp)

        return wps_by_schedule

    @lru_cache(maxsize=None)
    def workshop_periods_by_schedule(self, schedule: Optional[Schedule] = None, period: Optional[Period] = None) -> Dict[Schedule, "WorkshopPeriod"]:
        """Return this student's workshop_periods given a schedule, or all of them if no schedule given"""
        output = dict()
        for wp in self.workshop_periods.all():
            if period and wp.period != period:
                continue
            for sched in wp.schedules.all():
                if schedule is None or sched == schedule:
                    output[sched] = wp
        return output

    @lru_cache(maxsize=None)
    def workshop_periods_by_period(self, period: Optional[Period] = None) -> Set:
        """Return this student's workshop_periods given a period, or all of them if no period given"""
        if period is None:
            period = Period.objects.current()
        if period is None:
            return set()

        wps_by_schedule = self.workshop_periods_by_schedule(period=period)
        return {wp for wp in wps_by_schedule.values()}

    def is_schedule_full(self, period: Optional[Period] = None) -> bool:
        """Returns True or False depending if current student has a full schedule"""
        if not period:
            period = Period.objects.current()

        if not period:
            return False

        scount = Schedule.objects.all().count()
        lwps = len(self.workshop_periods_by_schedule(period=period))
        return scount == lwps

    def is_enabled_to_enroll(self, period: Optional[Period] = None) -> bool:
        """Returns True or False depending if current student is enabled to enroll"""
        if not period:
            period = Period.objects.current()

        if not period:
            return False

        now = datetime.now().date()

        # It's never possible to enroll before `enrollment_start` and after `date_end`
        if now > period.date_end or now < period.enrollment_start:
            return False

        # students with full schedule can only re-enroll between `enrollment_start` and `date_start`
        if self.is_schedule_full(period):
            if period.enrollment_start <= now < period.date_start:
                return True
        else:
            # students without full schedule can enroll anytime until `date_end`
            return True

        return False

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    class Meta:
        ordering = ["date_joined"]  # Order the results by cycle name in ascending order
        get_latest_by = "date_joined"  # Get the latest cycle for each student
        verbose_name = _("Students Cycle")
        verbose_name_plural = _("Students Cycles")


@receiver(m2m_changed, sender=StudentCycle.workshop_periods.through)
def student_cycle_workshop_period_changed(sender, instance, action, *args, **kwargs):
    """Validation procedure for the StudentCycle.workshop_periods m2m relation"""
    if action == "pre_add":
        instance.available_workshop_periods_by_schedule.cache_clear()
        instance.workshop_periods_by_schedule.cache_clear()
        instance.workshop_periods_by_period.cache_clear()

        # Get all workshop periods for this student's cycle, including incoming ones
        wps = set()
        for wp in instance.workshop_periods.all():
            wps.add(wp)
        for wp in WorkshopPeriod.objects.filter(id__in=kwargs.get("pk_set")):
            if wp in wps:
                raise ValidationError(_("Workshop period `%(wp)s` is already associated with this student") % {"wp": wp.workshop.name})
            wps.add(wp)

        # apply validations
        for wp in wps:
            # check if workshop period is full
            if wp.max_students > 0:
                # Count students in this cycle without counting current student
                curr_count = wp.studentcycle_set.exclude(student__id=instance.student.id).count()
                if wp.max_students <= curr_count:
                    raise ValidationError(_("Workshop period `%s` has reached its quota of students") % (wp.workshop.name))

            # check if workshop periods' cycles all belong to the same student cycle's cycle
            if instance.cycle not in wp.cycles.all():
                raise ValidationError(
                    _("Student `%(st)s` cannot be associated with workshop period `%(wp)s` because they belong to the same cycle.")
                    % {"st": instance.student.get_full_name(), "wp": wp.workshop.name}
                )

            # check for collitions between this student's cycle's workshop_period's schedules and incoming workshop_period's schedules
            for wp_2 in wps:
                if wp == wp_2:
                    continue
                if wp & wp_2:
                    raise ValidationError(
                        _("Workshop periods `%(w1)s` and `%(w2)s` have colliding schedules.") % {"w1": wp.workshop.name, "w2": wp_2.workshop.name}
                    )
