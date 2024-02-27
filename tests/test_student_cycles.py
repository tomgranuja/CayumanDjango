from datetime import datetime

import pytest
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.utils import timezone

from cayuman.models import Cycle
from cayuman.models import Member
from cayuman.models import Period
from cayuman.models import Schedule
from cayuman.models import StudentCycle
from cayuman.models import Workshop
from cayuman.models import WorkshopPeriod


pytestmark = pytest.mark.django_db


@pytest.fixture()
def create_student():
    """Fixture to create a student"""
    user = Member.objects.create_user(username="99999999", password="12345")
    group, _ = Group.objects.get_or_create(name=settings.STUDENTS_GROUP)
    user.groups.add(group)
    return user


@pytest.fixture
def create_teacher():
    """Fixture to create a teacher"""
    user = Member.objects.create_user(username="8888888", password="12345")
    group, _ = Group.objects.get_or_create(name=settings.TEACHERS_GROUP)
    user.groups.add(group)
    return user


@pytest.fixture
def create_period():
    """Fixture to create a sample Period"""
    # Period
    Period.objects.create(name="Period 1", date_start=datetime(2023, 1, 1), date_end=datetime(2023, 12, 31), enrollment_start=datetime(2022, 12, 23))
    return Period.objects.all()[0]


@pytest.fixture
def create_workshops():
    """Fixture to create sample Workshops"""
    # Workshops
    for name in ("Fractangulos", "Comics", "Ingles"):
        Workshop.objects.create(name=name)
    return Workshop.objects.all()


@pytest.fixture
def create_cycles():
    for name in ("Avellanos", "Ulmos", "Canelos"):
        Cycle.objects.create(name=name)
    return Cycle.objects.all()


def test_student_cycle_ok(create_student, create_teacher, create_workshops, create_cycles, create_period):
    """Test StudentCycle creation"""
    # Create a StudentCycle
    student = create_student
    teacher = create_teacher
    workshops = create_workshops
    cycles = create_cycles
    period = create_period

    # create workshop period
    wp1 = WorkshopPeriod.objects.create(workshop=workshops[0], period=period, teacher=teacher)
    wp2 = WorkshopPeriod.objects.create(workshop=workshops[1], period=period, teacher=teacher)

    # add cycles
    wp1.cycles.add(cycles[0])
    wp2.cycles.add(cycles[0])

    # create schedule for wp1
    time_start = timezone.now()
    time_end = timezone.now() + timezone.timedelta(hours=2)
    schedule_1 = Schedule.objects.create(day="monday", time_start=time_start, time_end=time_end)
    schedule_2 = Schedule.objects.create(day="tuesday", time_start=time_start, time_end=time_end)
    wp1.schedules.add(schedule_1, schedule_2)

    # create schedule for wp2
    schedule_3 = Schedule.objects.create(day="wednesday", time_start=time_start, time_end=time_end)
    wp2.schedules.add(schedule_3)

    sc = StudentCycle.objects.create(student=student, cycle=cycles[0], date_joined=timezone.now())  # coincidence in cycles[0]

    # assign workshop periods to student cycle
    sc.workshop_periods.add(wp1, wp2)

    assert sc.student == student
    assert sc.cycle == cycles[0]
    assert sc.workshop_periods.count() == 2
    assert set(sc.workshop_periods.all()) == set([wp1, wp2])


def test_student_cycle_fail_no_cycle_coincidence(create_student, create_teacher, create_workshops, create_cycles, create_period):
    """Test StudentCycle cannot be created if the workshop_period does not support the cycle"""
    # Create a StudentCycle
    student = create_student
    teacher = create_teacher
    workshops = create_workshops
    cycles = create_cycles
    period = create_period

    # create workshop period
    wp1 = WorkshopPeriod.objects.create(workshop=workshops[0], period=period, teacher=teacher)
    wp2 = WorkshopPeriod.objects.create(workshop=workshops[1], period=period, teacher=teacher)

    # add cycles
    wp1.cycles.add(cycles[0])
    wp2.cycles.add(cycles[1])

    # create schedule for wp1
    time_start = timezone.now()
    time_end = timezone.now() + timezone.timedelta(hours=2)
    schedule_1 = Schedule.objects.create(day="monday", time_start=time_start, time_end=time_end)
    schedule_2 = Schedule.objects.create(day="tuesday", time_start=time_start, time_end=time_end)
    wp1.schedules.add(schedule_1, schedule_2)

    # create schedule for wp2
    schedule_3 = Schedule.objects.create(day="wednesday", time_start=time_start, time_end=time_end)
    wp2.schedules.add(schedule_3)

    sc = StudentCycle.objects.create(student=student, cycle=cycles[2], date_joined=timezone.now())  # no cycle coincidence

    # assign workshop periods to student cycle
    with pytest.raises(ValidationError, match="StudentCycle cycle not in workshop period's cycles"):
        sc.workshop_periods.add(wp1, wp2)


def test_student_cycle_fail_schedule_collision(create_student, create_teacher, create_workshops, create_cycles, create_period):
    """Test StudentCycle cannot be created if the schedules of the workshop periods of the student have collisions"""
    # Create a StudentCycle
    student = create_student
    teacher = create_teacher
    workshops = create_workshops
    cycles = create_cycles
    period = create_period

    # create workshop period
    wp1 = WorkshopPeriod.objects.create(workshop=workshops[0], period=period, teacher=teacher)
    wp2 = WorkshopPeriod.objects.create(workshop=workshops[1], period=period, teacher=teacher)

    # add cycles
    wp1.cycles.add(cycles[0])
    wp2.cycles.add(cycles[1])

    # create schedule for wp1
    time_start = timezone.now()
    time_end = timezone.now() + timezone.timedelta(hours=2)
    schedule_1 = Schedule.objects.create(day="monday", time_start=time_start, time_end=time_end)
    schedule_2 = Schedule.objects.create(day="tuesday", time_start=time_start, time_end=time_end)
    wp1.schedules.add(schedule_1, schedule_2)

    # create schedule for wp2
    wp2.schedules.add(schedule_1)  # collision with schedule from wp1

    sc = StudentCycle.objects.create(student=student, cycle=cycles[0], date_joined=timezone.now())  # no cycle coincidence

    # assign workshop periods to student cycle
    with pytest.raises(ValidationError, match="Workshop periods are overlapping"):
        sc.workshop_periods.add(wp1, wp2)


def test_student_cycle_fail_max_students(create_teacher, create_workshops, create_cycles, create_period):
    """Test StudentCycle cannot be created if the schedules of the workshop periods of the student have collisions"""
    # Create a StudentCycle
    teacher = create_teacher
    workshops = create_workshops
    cycles = create_cycles
    period = create_period

    # create workshop period
    wp1 = WorkshopPeriod.objects.create(workshop=workshops[0], period=period, teacher=teacher, max_students=2)

    # add cycles
    wp1.cycles.add(cycles[0])

    # create schedule for wp1
    time_start = timezone.now()
    time_end = timezone.now() + timezone.timedelta(hours=2)
    schedule_1 = Schedule.objects.create(day="monday", time_start=time_start, time_end=time_end)
    schedule_2 = Schedule.objects.create(day="tuesday", time_start=time_start, time_end=time_end)
    wp1.schedules.add(schedule_1, schedule_2)

    for i in range(1, 4):
        user = Member.objects.create_user(username=f"{i}" * 8, password="12345")
        group, _ = Group.objects.get_or_create(name=settings.STUDENTS_GROUP)
        user.groups.add(group)

        sc = StudentCycle.objects.create(student=user, cycle=cycles[0], date_joined=timezone.now())  # no cycle coincidence

        if i > 2:
            # assign workshop periods to student cycle
            with pytest.raises(ValidationError, match="Workshop period is already full"):
                sc.workshop_periods.add(wp1)
        else:
            sc.workshop_periods.add(wp1)
