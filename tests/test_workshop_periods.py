from datetime import datetime

import pytest
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.utils import timezone

from cayuman.models import Member
from cayuman.models import Period
from cayuman.models import Schedule
from cayuman.models import Workshop
from cayuman.models import WorkshopPeriod


pytestmark = pytest.mark.django_db


@pytest.fixture()
def create_student():
    """Fixture to create a student"""
    user = Member.objects.create_user(username="11111111", password="12345")
    group, _ = Group.objects.get_or_create(name=settings.STUDENTS_GROUP)
    user.groups.add(group)
    return user


@pytest.fixture
def create_teacher():
    """Fixture to create a teacher"""
    user = Member.objects.create_user(username="22222222", password="12345")
    group, _ = Group.objects.get_or_create(name=settings.TEACHERS_GROUP)
    user.groups.add(group)
    return user


@pytest.fixture
def create_workshops():
    """Fixture to create sample Workshops"""
    # Workshops
    for name in ("Fractangulos", "Comics", "Ingles"):
        Workshop.objects.create(name=name)
    return Workshop.objects.all()


@pytest.fixture
def create_period():
    """Fixture to create a sample Period"""
    # Period
    Period.objects.create(name="Period 1", date_start=datetime(2023, 1, 1), date_end=datetime(2023, 12, 31), enrollment_start=datetime(2022, 12, 23))
    return Period.objects.all()[0]


def test_ok_workshop_period_with_teacher(create_teacher, create_workshops, create_period):
    """
    Test creating a WorkshopPeriod with a teacher
    """
    # fetch teacher and workshops data
    teacher = create_teacher
    workshops = create_workshops
    period = create_period

    # create workshop
    wp = WorkshopPeriod.objects.create(workshop=workshops[0], period=period, teacher=teacher)
    wp.save()

    assert wp.teacher == teacher


def test_fail_create_workshop_period_student_as_teacher(create_student, create_workshops, create_period):
    """
    Test that shows saving a WorkshopPeriod with a student as a teacher fails
    """
    # fetch student and workshops data
    student = create_student
    workshops = create_workshops
    period = create_period

    # create workshop
    with pytest.raises(ValidationError, match=r"Teacher must be"):
        WorkshopPeriod.objects.create(workshop=workshops[0], period=period, teacher=student)


def test_workshop_period_non_overlapping(create_workshops, create_teacher, create_period):
    """Tests 2 workshop periods non overlapping"""
    workshops = create_workshops
    teacher = create_teacher
    period = create_period

    # create workshop period
    wp1 = WorkshopPeriod.objects.create(workshop=workshops[0], period=period, teacher=teacher)

    # create workshop period
    wp2 = WorkshopPeriod.objects.create(workshop=workshops[1], period=period, teacher=teacher)

    # create schedule for wp1
    time_start = timezone.now()
    time_end = timezone.now() + timezone.timedelta(hours=2)
    schedule_1 = Schedule.objects.create(day="monday", time_start=time_start, time_end=time_end)
    schedule_2 = Schedule.objects.create(day="tuesday", time_start=time_start, time_end=time_end)
    wp1.schedules.add(schedule_1, schedule_2)

    # create schedule for wp2
    schedule_3 = Schedule.objects.create(day="wednesday", time_start=time_start, time_end=time_end)
    wp2.schedules.add(schedule_3)

    # no overlapping because the wp have schedules on different days
    assert not wp1 & wp2


def test_workshop_period_overlapping(create_workshops, create_teacher, create_period):
    """Tests overlapping between 2 workshop periods based on their schedules"""
    workshops = create_workshops
    teacher = create_teacher
    period = create_period

    # create workshop period
    wp1 = WorkshopPeriod.objects.create(workshop=workshops[0], period=period, teacher=teacher)

    # create workshop period
    wp2 = WorkshopPeriod.objects.create(workshop=workshops[1], period=period, teacher=teacher)

    # create schedule for wp1
    time_start = timezone.now()
    time_end = timezone.now() + timezone.timedelta(hours=2)
    schedule_1 = Schedule.objects.create(day="monday", time_start=time_start, time_end=time_end)
    schedule_2 = Schedule.objects.create(day="tuesday", time_start=time_start, time_end=time_end)
    wp1.schedules.add(schedule_1, schedule_2)

    # create schedule for wp2
    wp2.schedules.add(schedule_1)

    # there's overlapping because both wp have schedule at Lunes, same time
    assert wp1 & wp2
