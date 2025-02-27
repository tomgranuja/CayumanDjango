from datetime import datetime
from datetime import time

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from cayuman.models import Period
from cayuman.models import Schedule
from cayuman.models import WorkshopPeriod


pytestmark = pytest.mark.django_db


@pytest.fixture
def create_period():
    """Fixture to create a sample Period"""
    # Period
    Period.objects.create(
        name="Period 1",
        date_start=timezone.make_aware(datetime(2023, 1, 1)).date(),
        date_end=timezone.make_aware(datetime(2023, 12, 31)).date(),
        enrollment_start=timezone.make_aware(datetime(2022, 12, 23)),
        enrollment_end=timezone.make_aware(datetime(2022, 12, 27)).date(),
    )
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
    time_start = time(10, 15)
    time_end = time(11, 15)
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
    time_start = time(10, 15)
    time_end = time(11, 15)
    schedule_1 = Schedule.objects.create(day="monday", time_start=time_start, time_end=time_end)
    schedule_2 = Schedule.objects.create(day="tuesday", time_start=time_start, time_end=time_end)
    wp1.schedules.add(schedule_1, schedule_2)

    # create schedule for wp2
    wp2.schedules.add(schedule_1)

    # there's overlapping because both wp have schedule at Lunes, same time
    assert wp1 & wp2
