import datetime

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from cayuman.models import Schedule


pytestmark = pytest.mark.django_db


def test_schedule_create():
    """Tests correct Schedule creation"""
    time_start = datetime.time(10, 15)
    time_end = datetime.time(11, 15)
    schedule = Schedule.objects.create(day="Lunes", time_start=time_start, time_end=time_end)
    assert schedule.day == "Lunes"
    assert schedule.time_start == time_start
    assert schedule.time_end == time_end


def test_schedule_create_invalid():
    """Tests invalid Schedule instantiation because time_end comes before time_start"""
    time_start = datetime.time(11, 15)
    time_end = datetime.time(10, 15)
    with pytest.raises(ValidationError, match=r"must be before"):
        Schedule.objects.create(day="Lunes", time_start=time_start, time_end=time_end)


def test_schedule_instances_intersection():
    """Tests intersection between 2 schedules"""
    # This test does not create the schedule objects to be able to test intersection
    time_start_1 = datetime.time(10, 15)
    time_end_1 = datetime.time(11, 15)
    schedule_1 = Schedule(day="Lunes", time_start=time_start_1, time_end=time_end_1)

    time_start_2 = datetime.time(10, 45)
    time_end_2 = datetime.time(11, 45)
    schedule_2 = Schedule(day="Lunes", time_start=time_start_2, time_end=time_end_2)

    # there's intersection here
    assert schedule_1 & schedule_2


def test_schedule_creation_fail():
    """Tests that it's not possible to create schedule instances colliding in time"""
    today = timezone.localdate()
    now = timezone.make_aware(datetime.datetime.combine(today, datetime.time(10, 0)))

    time_start_1 = now
    time_end_1 = now + timezone.timedelta(hours=2)
    Schedule.objects.create(day="Lunes", time_start=time_start_1, time_end=time_end_1)
    time_start_2 = now + timezone.timedelta(hours=1)
    time_end_2 = now + timezone.timedelta(hours=3)
    with pytest.raises(ValidationError, match=r"another schedule colliding"):
        Schedule.objects.create(day="Lunes", time_start=time_start_2, time_end=time_end_2)


def test_schedule_intersection_empty_time():
    """Tests that schedules don't intersect based on different times"""
    time_start_1 = datetime.time(10, 15)
    time_end_1 = datetime.time(11, 15)
    schedule_1 = Schedule(day="Lunes", time_start=time_start_1, time_end=time_end_1)

    time_start_2 = datetime.time(12, 30)
    time_end_2 = datetime.time(13, 30)
    schedule_2 = Schedule(day="Lunes", time_start=time_start_2, time_end=time_end_2)

    # there's no intersection here
    assert not schedule_1 & schedule_2


def test_schedule_intersection_empty_different_day():
    """Tests that schedules don't intersect based on different day"""
    time_start_1 = datetime.time(10, 15)
    time_end_1 = datetime.time(11, 15)
    schedule_1 = Schedule(day="Lunes", time_start=time_start_1, time_end=time_end_1)

    schedule_2 = Schedule(day="Martes", time_start=time_start_1, time_end=time_end_1)

    # there's no intersection here
    assert not schedule_1 & schedule_2
