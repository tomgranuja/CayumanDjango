from datetime import datetime

from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from django.contrib.auth.models import UserManager
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from django.utils.translation import gettext as _


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
    def current_cycle(self):
        return StudentCycle.objects.filter(student=self).order_by("-date_joined").first()

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

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
                raise ValidationError("Group is already assigned to this member")
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
                raise ValidationError("User must be either Student or Teacher, or a staff member")
        else:
            if is_student:
                raise ValidationError("Student cannot be staff member")

        if is_student and is_teacher:
            raise ValidationError("User must not be both Student and Teacher")


class Workshop(models.Model):
    name = models.CharField(max_length=50)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"{self.__class__.__name__}(name='{self.name}')"

    class Meta:
        verbose_name = _("Workshop")
        verbose_name_plural = _("Workshops")


class Cycle(models.Model):
    name = models.CharField(max_length=50)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"{self.__class__.__name__}(name='{self.name}')"

    class Meta:
        verbose_name = _("Cycle")
        verbose_name_plural = _("Cycles")


class Schedule(models.Model):
    """Represent weekly time blocks"""

    CHOICES = (
        ("monday", _("Monday")),
        ("tuesday", _("Tuesday")),
        ("wednesday", _("Wednesday")),
        ("thursday", _("Thursday")),
        ("friday", _("Friday")),
    )

    day = models.CharField(max_length=10, choices=CHOICES)
    time_start = models.TimeField()
    time_end = models.TimeField()

    def clean(self):
        # normalize times
        if isinstance(self.time_start, datetime):
            self.time_start = self.time_start.time()
        if isinstance(self.time_end, datetime):
            self.time_end = self.time_end.time()

        # Validate times
        if self.time_start >= self.time_end:
            raise ValidationError("Start time must be before end time")

        # Validate no collisions for the same day
        for schedule in Schedule.objects.filter(day=self.day):
            if self.id and schedule.id == self.id:
                # do not compare against self
                continue
            if self & schedule:
                raise ValidationError("There's already another schedule overlapping with current one")

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
        return f"{self.day} @ {self.time_start} - {self.time_end}"

    class Meta:
        verbose_name = _("Schedule")
        verbose_name_plural = _("Schedules")


class Period(models.Model):
    """Represent a period of time"""

    name = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    enrollment_start = models.DateField(blank=True)
    date_start = models.DateField()
    date_end = models.DateField()

    def __str__(self):
        return f"{self.name} from {self.date_start} to {self.date_end}"

    def __repr__(self):
        return f"{self.__class__.__name__}(name='{self.name}', date_start='{self.date_start}', date_end='{self.date_end}')"

    def clean(self):
        if self.date_start >= self.date_end:
            raise ValidationError({"start": "Start date must be before end date"})

        if self.enrollment_start and self.enrollment_start > self.date_start:
            raise ValidationError({"enrollment": "Enrollment start date must be before start date"})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = _("Period")
        verbose_name_plural = _("Periods")


class WorkshopPeriod(models.Model):
    workshop = models.ForeignKey(Workshop, on_delete=models.CASCADE)
    period = models.ForeignKey(Period, on_delete=models.CASCADE)
    teacher = models.ForeignKey(Member, on_delete=models.CASCADE)
    max_students = models.PositiveIntegerField(default=0)
    cycles = models.ManyToManyField(Cycle)
    schedules = models.ManyToManyField(Schedule)

    def __str__(self):
        return f"{self.workshop.name} @ {self.period}"

    def clean(self):
        if not self.teacher.is_teacher:
            raise ValidationError({"teacher": "Teacher must be a teacher"})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

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
        # unique_together = [["workshop", "period"], ["workshop", "period", "teacher"]]
        verbose_name = _("Workshop's Period")
        verbose_name_plural = _("Workshops' Periods")


class StudentCycle(models.Model):
    """Represents the relationship between students and their cycles and chosen workshop_periods"""

    student = models.ForeignKey(Member, on_delete=models.CASCADE)
    cycle = models.ForeignKey(Cycle, on_delete=models.CASCADE)
    date_joined = models.DateField(auto_now_add=True)
    workshop_periods = models.ManyToManyField(WorkshopPeriod, blank=True)

    def __str__(self):
        return f"{self.student} @ {self.cycle} {self.date_joined.year}"

    def clean(self):
        if not self.student.is_student:
            raise ValidationError({"student": f"Student must be a member of the `{settings.STUDENTS_GROUP}` group"})

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
    if action == "pre_add":
        # Get all workshop periods for this student's cycle, including incoming ones
        wps = set()
        for wp in instance.workshop_periods.all():
            wps.add(wp)
        for wp in WorkshopPeriod.objects.filter(id__in=kwargs.get("pk_set")):
            if wp in wps:
                raise ValidationError(f"Workshop period is already assigned to this student cycle: `{wp}`")
            wps.add(wp)

        # apply validations
        for wp in wps:
            # check if workshop period is full
            if wp.max_students > 0:
                # Count students in this cycle without counting current student
                # curr_count = wp.studentcycle_set.filter(student__id__ne=instance.student.id).count()
                curr_count = wp.studentcycle_set.exclude(student__id=instance.student.id).count()
                if wp.max_students <= curr_count:
                    raise ValidationError(f"Workshop period is already full: `{wp}`")

            # check if workshop periods' cycles all belong to the same student cycle's cycle
            if instance.cycle not in wp.cycles.all():
                raise ValidationError(f"StudentCycle cycle not in workshop period's cycles: `{instance.cycle}` not in {wp.cycles.all()}")

            # check for collitions between this student's cycle's workshop_period's schedules and incoming workshop_period's schedules
            for wp_2 in wps:
                if wp == wp_2:
                    continue
                if wp & wp_2:
                    raise ValidationError(f"Workshop periods are overlapping: `{wp}` and `{wp_2}`")
