from django.db import models
from django.contrib.auth.models import User
from django.conf import settings


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


class Period(models.Model):
    date_start = models.DateTimeField()
    date_end = models.DateTimeField()

    def __str__(self):
        return f"{self.date_start} - {self.date_end}"


class WorkshopPeriod(models.Model):
    workshop = models.ForeignKey(Workshop, on_delete=models.CASCADE)
    period = models.ForeignKey(Period, on_delete=models.CASCADE)
    teacher = models.ForeignKey(Member, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.workshop.name} @ {self.period}"


class StudentWorkshopPeriod(models.Model):
    workshop_period = models.ForeignKey(WorkshopPeriod, on_delete=models.CASCADE)
    student = models.ForeignKey(Member, on_delete=models.CASCADE)
    date_joined = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.user.first_name} {self.student.user.last_name} @ {self.workshop_period}"

    class Meta:
        unique_together = ('workshop_period', 'student')  # Unique constraint

