from datetime import datetime

import pytest
from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from django.utils import timezone

from cayuman.models import Cycle
from cayuman.models import Member
from cayuman.models import Schedule
from cayuman.models import Workshop
from cayuman.models import WorkshopPeriod


pytestmark = pytest.mark.django_db


@pytest.fixture()
def create_student():
    """Fixture to create a student"""
    user = User.objects.create_user(username="XXXXXXXX", password="12345")
    group, _ = Group.objects.get_or_create(name=settings.STUDENTS_GROUP)
    user.groups.add(group)
    m = Member(user=user)
    m.save()
    return m


@pytest.fixture
def create_teacher():
    """Fixture to create a teacher"""
    user = User.objects.create_user(username="XXXXXXXX", password="12345")
    group, _ = Group.objects.get_or_create(name=settings.TEACHERS_GROUP)
    user.groups.add(group)
    m = Member(user=user)
    m.save()
    return m


@pytest.fixture
def create_structure():
    """Fixture to create Cycles, Schedules and Workshops"""
    # Cycles
    for cycle_name in ("Avellanos", "Ulmos", "Coigües", "Canelos", "Mañios"):
        cycle = Cycle.objects.create(name=cycle_name)
        cycle.save()

    # Schedules
    for day in ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes"):
        for time_start, time_end in (("09:00", "10:15"), ("10:30", "11:45"), ("12:00", "13:15")):
            schedule = Schedule.objects.create(day=day, time_start=time_start, time_end=time_end)
            schedule.save()

    # Workshops
    for name in ("Fractangulos", "Comics", "Ingles"):
        ws = Workshop.objects.create(name=name)
        ws.save()

    return (Cycle.objects.all(), Schedule.objects.all(), Workshop.objects.all())


def test_ok_workshop_period_with_teacher(create_teacher, create_structure):
    """
    Test creating a WorkshopPeriod with a teacher
    """
    # fetch teacher and workshops data
    teacher = create_teacher
    _, _, workshops = create_structure

    # create workshop
    date_start = timezone.make_aware(datetime(2024, 3, 13), timezone.get_default_timezone())
    date_end = timezone.make_aware(datetime(2024, 6, 1), timezone.get_default_timezone())
    wp = WorkshopPeriod.objects.create(workshop=workshops[0], date_start=date_start, date_end=date_end, teacher=teacher)
    wp.save()

    assert wp.teacher == teacher


def test_fail_create_workshop_period_student_as_teacher(create_student, create_structure):
    """
    Test that shows saving a WorkshopPeriod with a student as a teacher fails
    """
    # fetch student and workshops data
    student = create_student
    _, _, workshops = create_structure

    # create workshop
    date_start = timezone.make_aware(datetime(2024, 3, 13), timezone.get_default_timezone())
    date_end = timezone.make_aware(datetime(2024, 6, 1), timezone.get_default_timezone())
    with pytest.raises(ValueError, match=r"Teacher must be a member of the .+"):
        WorkshopPeriod.objects.create(workshop=workshops[0], date_start=date_start, date_end=date_end, teacher=student)
