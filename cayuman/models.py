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
    day = models.CharField(max_length=10)
    time_start = models.TimeField()
    time_end = models.TimeField()


class WorkshopPeriod(models.Model):
    workshop = models.ForeignKey(Workshop, on_delete=models.CASCADE)
    date_start = models.DateTimeField()
    date_end = models.DateTimeField()
    teacher = models.ForeignKey(Member, on_delete=models.CASCADE)
    cycles = models.ManyToManyField(Cycle)
    schedules = models.ManyToManyField(Schedule)

    def __str__(self):
        return f"{self.workshop.name} @ {self.date_start} - {self.date_end}"

    def save(self, *args, **kwargs):
        if self.date_start >= self.date_end:
            raise ValueError("Start date must be before end date")

        if not self.teacher.is_teacher:
            raise ValueError(f"Teacher must be a member of the `{settings.TEACHERS_GROUP}` group")

        super().save(*args, **kwargs)


class StudentCycle(models.Model):
    student = models.ForeignKey(Member, on_delete=models.CASCADE)
    cycle = models.ForeignKey(Cycle, on_delete=models.CASCADE)
    date_joined = models.DateTimeField(auto_now_add=True)
    workshop_periods = models.ManyToManyField(WorkshopPeriod)

    def __str__(self):
        return f"{self.student.user.first_name} {self.student.user.last_name} @ {self.cycle} on {self.date_joined.year}"

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
        # validating this student's cycle is part of the workshop period's cycles
        if instance.cycle not in instance.workshop_periods.cycles.all():
            raise ValueError("StudentCycle must be in one of the workshop period's cycles")

        # checking for collitions between this student cycle's workshop_period's schedules
