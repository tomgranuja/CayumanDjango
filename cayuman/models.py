from datetime import datetime

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import m2m_changed
from django.dispatch import receiver


class Member(models.Model):
    """
    User model holding information for members of the community.
    At the time of writing this we have STUDENTS, TEACHERS and regular users outside both groups
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE)

    @property
    def is_student(self):
        return self.user.groups.filter(name=settings.STUDENTS_GROUP).exists()

    @property
    def is_teacher(self):
        return self.user.groups.filter(name=settings.TEACHERS_GROUP).exists()

    @property
    def current_cycle(self):
        return StudentCycle.objects.filter(student=self).order_by("-date_joined").first()

    def __str__(self):
        return f"{self.__class__.__name__}(username={self.user.username})"

    def save(self, *args, **kwargs):
        if not self.is_student and not self.is_teacher and not self.user.is_staff:
            raise ValueError("Non students and teachers should be staff members. Get sure to check that box.")

        if self.is_student and self.is_teacher:
            raise ValueError("Member cannot be both a student and a teacher")

        if self.is_student and self.user.is_staff:
            raise ValueError("Member cannot be both a student and a staff member")

        super().save(*args, **kwargs)


class Workshop(models.Model):
    name = models.CharField(max_length=50)
    description = models.TextField()

    def __str__(self):
        return self.name


class Cycle(models.Model):
    name = models.CharField(max_length=50)
    description = models.TextField()

    def __str__(self):
        return self.name


class Schedule(models.Model):
    """Represent weekly time blocks"""

    day = models.CharField(max_length=10)
    time_start = models.TimeField()
    time_end = models.TimeField()

    def save(self, *args, **kwargs):
        # normalize times
        if isinstance(self.time_start, datetime):
            self.time_start = self.time_start.time()
        if isinstance(self.time_end, datetime):
            self.time_end = self.time_end.time()

        # Validate times
        if self.time_start >= self.time_end:
            raise ValueError("Start time must be before end time")

        # Validate no collisions for the same day
        for schedule in Schedule.objects.filter(day=self.day):
            if self.id and schedule.id == self.id:
                # do not compare against self
                continue
            if self & schedule:
                raise ValueError("There's already another schedule overlapping with current one")

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
        return f"{self.__class__.__name__}({self.day}, {self.time_start}, {self.time_end})"


class WorkshopPeriod(models.Model):
    workshop = models.ForeignKey(Workshop, on_delete=models.CASCADE)
    date_start = models.DateTimeField()
    date_end = models.DateTimeField()
    teacher = models.ForeignKey(Member, on_delete=models.CASCADE)
    cycles = models.ManyToManyField(Cycle)
    schedules = models.ManyToManyField(Schedule)
    max_students = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.workshop.name} @ {self.date_start} - {self.date_end}"

    def save(self, *args, **kwargs):
        if self.date_start >= self.date_end:
            raise ValueError("Start date must be before end date")

        if not self.teacher.is_teacher:
            raise ValueError(f"Teacher must be a member of the `{settings.TEACHERS_GROUP}` group")

        super().save(*args, **kwargs)

    def __and__(self, other):
        """
        Workshop period overlapping is defined based on intersection between their date_start and date_end and their schedules
        """
        # check if date_start and date_end do not overlap
        if self.date_start >= other.date_end or self.date_end <= other.date_start:
            return False

        # check overlapping due to schedules
        for schedule in self.schedules.all():
            for other_schedule in other.schedules.all():
                if schedule & other_schedule:
                    return True

        return False


class StudentCycle(models.Model):
    """Represents the relationship between students and their cycles and chosen workshop_periods"""

    student = models.ForeignKey(Member, on_delete=models.CASCADE)
    cycle = models.ForeignKey(Cycle, on_delete=models.CASCADE)
    date_joined = models.DateTimeField(auto_now_add=True)
    workshop_periods = models.ManyToManyField(WorkshopPeriod)

    def __str__(self):
        return f"{self.student} @ {self.cycle} on {self.date_joined.year}"

    def save(self, *args, **kwargs):
        if not self.student.is_student:
            raise ValueError(f"Student must be a member of the `{settings.STUDENTS_GROUP}` group")

        super().save(*args, **kwargs)

    class Meta:
        ordering = ["date_joined"]  # Order the results by cycle name in ascending order
        get_latest_by = "date_joined"  # Get the latest cycle for each student


@receiver(m2m_changed, sender=StudentCycle.workshop_periods.through)
def student_cycle_workshop_period_changed(sender, instance, action, *args, **kwargs):
    if action == "pre_add":
        # Get all workshop periods for this student's cycle, including incoming ones
        wps = set()
        for wp in instance.workshop_periods.all():
            wps.add(wp)
        for wp in WorkshopPeriod.objects.filter(id__in=kwargs.get("pk_set")):
            if wp in wps:
                raise ValueError(f"Workshop period is already assigned to this student cycle: `{wp}`")
            wps.add(wp)

        # check that max_students for each workshop period is not exceeded
        for wp in wps:
            if wp.max_students > 0 and wp.max_students <= wp.studentcycle_set.count():
                raise ValueError(f"Workshop period is already full: `{wp}`")

        # check for collitions between this student's cycle's workshop_period's schedules and incoming workshop_period's schedules
        for wp_1 in wps:
            for wp_2 in wps:
                if wp_1 == wp_2:
                    continue
                if wp_1 & wp_2:
                    raise ValueError(f"Workshop periods are overlapping: `{wp_1}` and `{wp_2}`")

        # validating this student's cycle is part of the workshop period's cycles
        # gather all cycles from workshop periods, including incoming one
        cycles = set()
        for wp in wps:
            for cycle in wp.cycles.all():
                cycles.add(cycle)
        if instance.cycle not in cycles:
            raise ValueError(f"StudentCycle must be in one of the workshop period's cycles: `{instance.cycle}`")
