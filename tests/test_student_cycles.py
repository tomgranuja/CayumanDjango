from datetime import datetime
from datetime import time
from unittest.mock import patch

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
    user = Member.objects.create_user(username="99999999", password="12345", first_name="Test", last_name="Student")
    group, _ = Group.objects.get_or_create(name=settings.STUDENTS_GROUP)
    user.groups.add(group)
    return user


@pytest.fixture
def create_teacher():
    """Fixture to create a teacher"""
    user = Member.objects.create_user(username="8888888", password="12345", first_name="Test", last_name="Teacher")
    group, _ = Group.objects.get_or_create(name=settings.TEACHERS_GROUP)
    user.groups.add(group)
    return user


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
    time_start = time(10, 15)
    time_end = time(11, 15)
    schedule_1 = Schedule.objects.create(day="monday", time_start=time_start, time_end=time_end)
    schedule_2 = Schedule.objects.create(day="tuesday", time_start=time_start, time_end=time_end)
    wp1.schedules.add(schedule_1, schedule_2)

    # create schedule for wp2
    schedule_3 = Schedule.objects.create(day="wednesday", time_start=time_start, time_end=time_end)
    wp2.schedules.add(schedule_3)

    sc = StudentCycle.objects.create(student=student, cycle=cycles[0], date_joined=time(10, 15))  # coincidence in cycles[0]

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
    time_start = time(10, 15)
    time_end = time(11, 15)
    schedule_1 = Schedule.objects.create(day="monday", time_start=time_start, time_end=time_end)
    schedule_2 = Schedule.objects.create(day="tuesday", time_start=time_start, time_end=time_end)
    wp1.schedules.add(schedule_1, schedule_2)

    # create schedule for wp2
    schedule_3 = Schedule.objects.create(day="wednesday", time_start=time_start, time_end=time_end)
    wp2.schedules.add(schedule_3)

    sc = StudentCycle.objects.create(student=student, cycle=cycles[2], date_joined=time(10, 15))  # no cycle coincidence

    # assign workshop periods to student cycle
    with pytest.raises(ValidationError, match=r"cannot be associated with workshop period"):
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
    time_start = time(10, 15)
    time_end = time(11, 15)
    schedule_1 = Schedule.objects.create(day="monday", time_start=time_start, time_end=time_end)
    schedule_2 = Schedule.objects.create(day="tuesday", time_start=time_start, time_end=time_end)
    wp1.schedules.add(schedule_1, schedule_2)

    # create schedule for wp2
    wp2.schedules.add(schedule_1)  # collision with schedule from wp1

    sc = StudentCycle.objects.create(student=student, cycle=cycles[0])  # no cycle coincidence

    # assign workshop periods to student cycle
    with pytest.raises(ValidationError, match=r"have colliding schedules"):
        sc.workshop_periods.add(wp1, wp2)


def test_student_cycle_fail_students_quota(create_teacher, create_workshops, create_cycles, create_period):
    """
    Tests `StudentCycle.max_students`, `WorkshopPeriod.count_students()` and `WorkshopPeriod.remaining_quota()`
    work correctly as students enroll if max_students > 0
    """
    # Create a StudentCycle
    teacher = create_teacher
    workshops = create_workshops
    cycles = create_cycles
    period = create_period

    MAX_STUDENTS = 5

    # create workshop period
    wp1 = WorkshopPeriod.objects.create(workshop=workshops[0], period=period, teacher=teacher, max_students=MAX_STUDENTS)

    # add cycles
    wp1.cycles.add(cycles[0])

    # create schedule for wp1
    time_start = time(10, 15)
    time_end = time(11, 15)
    schedule_1 = Schedule.objects.create(day="monday", time_start=time_start, time_end=time_end)
    schedule_2 = Schedule.objects.create(day="tuesday", time_start=time_start, time_end=time_end)
    wp1.schedules.add(schedule_1, schedule_2)

    for i in range(1, MAX_STUDENTS + 2):
        user = Member.objects.create_user(username=f"{i}" * 8, password="12345")
        group, _ = Group.objects.get_or_create(name=settings.STUDENTS_GROUP)
        user.groups.add(group)

        sc = StudentCycle.objects.create(student=user, cycle=cycles[0], date_joined=time(10, 15))  # no cycle coincidence

        if i > MAX_STUDENTS:
            # assign workshop periods to student cycle
            with pytest.raises(ValidationError, match=r"has reached its quota of students"):
                sc.workshop_periods.add(wp1)
        else:
            sc.workshop_periods.add(wp1)

            assert wp1.count_students() == i
            assert wp1.remaining_quota() == MAX_STUDENTS - i


def test_student_cycle_fail_students_no_quota(create_teacher, create_workshops, create_cycles, create_period):
    """
    Tests `StudentCycle.max_students`, `WorkshopPeriod.count_students()` and `WorkshopPeriod.remaining_quota()`
    work correctly if max_students == 0
    """
    # Create a StudentCycle
    teacher = create_teacher
    workshops = create_workshops
    cycles = create_cycles
    period = create_period

    # create workshop period
    wp1 = WorkshopPeriod.objects.create(workshop=workshops[0], period=period, teacher=teacher, max_students=0)

    assert wp1.remaining_quota() is None

    # add cycles
    wp1.cycles.add(cycles[0])

    # create schedule for wp1
    time_start = time(10, 15)
    time_end = time(11, 15)
    schedule_1 = Schedule.objects.create(day="monday", time_start=time_start, time_end=time_end)
    schedule_2 = Schedule.objects.create(day="tuesday", time_start=time_start, time_end=time_end)
    wp1.schedules.add(schedule_1, schedule_2)

    for i in range(1, 5):
        user = Member.objects.create_user(username=f"{i}" * 8, password="12345")
        group, _ = Group.objects.get_or_create(name=settings.STUDENTS_GROUP)
        user.groups.add(group)

        sc = StudentCycle.objects.create(student=user, cycle=cycles[0], date_joined=time(10, 15))  # no cycle coincidence
        sc.workshop_periods.add(wp1)

        assert wp1.count_students() == i
        assert wp1.remaining_quota() is None


def test_is_schedule_full(create_student, create_teacher, create_period, create_workshops, create_cycles):
    """Tests method `is_full_schedule` works ok when telling whether students have filled all their weekly schedule or not"""
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
    time_start = time(10, 15)
    time_end = time(11, 15)
    schedule_1 = Schedule.objects.create(day="monday", time_start=time_start, time_end=time_end)
    schedule_2 = Schedule.objects.create(day="tuesday", time_start=time_start, time_end=time_end)
    wp1.schedules.add(schedule_1, schedule_2)

    sc = StudentCycle.objects.create(student=student, cycle=cycles[0])
    sc.workshop_periods.add(wp1, wp2)

    # Assuming there are 2 schedules in the system and the student has 2 workshop periods
    assert sc.is_schedule_full(period=period) is True

    # Add another schedule to the system without adding more workshop periods to the student
    Schedule.objects.create(day="wednesday", time_start=time_start, time_end=time_end)
    sc.is_schedule_full.cache_clear()  # TO-DO: Find the right spot in models.py or signals to clear cache for this case, although very unlikely
    assert sc.is_schedule_full(period=period) is False


def test_is_enabled_to_enroll(create_student, create_period, create_cycles):
    """Tests method `is_enabled_to_enroll` works ok when telling whether a student is allowed to enroll workshops or not"""
    student = create_student
    period = create_period
    cycle = create_cycles[0]
    sc = StudentCycle.objects.create(student=student, cycle=cycle)

    # Mock is_schedule_full to return True
    with patch.object(StudentCycle, "is_schedule_full", return_value=True):
        # Assuming the schedule is full and the current date is within the enrollment period
        with patch("cayuman.models.timezone") as mock_datetime:
            # Mock current date before enrollment_start
            mock_datetime.now.return_value = timezone.make_aware(datetime(2022, 12, 21))
            mock_datetime.now.date.return_value = timezone.make_aware(datetime(2022, 12, 21)).date()
            assert sc.is_enabled_to_enroll(period=period) is False

            # Mock current date within enrollment_start and enrollment_end
            mock_datetime.now.return_value = timezone.make_aware(datetime(2022, 12, 25))
            mock_datetime.now.date.return_value = timezone.make_aware(datetime(2022, 12, 25)).date()
            assert sc.is_enabled_to_enroll(period=period) is True

            # Mock current date within enrollment_end and date_start
            mock_datetime.now.return_value = timezone.make_aware(datetime(2022, 12, 31))
            mock_datetime.now.date.return_value = timezone.make_aware(datetime(2022, 12, 31)).date()
            assert sc.is_enabled_to_enroll(period=period) is False

            # Mock current date after date_start and before date_end
            mock_datetime.now.return_value = timezone.make_aware(datetime(2023, 1, 1))
            mock_datetime.now.date.return_value = timezone.make_aware(datetime(2023, 1, 1)).date()
            assert sc.is_enabled_to_enroll(period=period) is False

            # Mock current date after date_end
            mock_datetime.now.return_value = timezone.make_aware(datetime(2024, 1, 1))
            mock_datetime.now.date.return_value = timezone.make_aware(datetime(2024, 1, 1)).date()
            assert sc.is_enabled_to_enroll(period=period) is False

    # Mock is_schedule_full to return False
    with patch.object(StudentCycle, "is_schedule_full", return_value=False):
        # Assuming the schedule is not full and the current date is within the enrollment period but after date_start
        with patch("cayuman.models.timezone") as mock_datetime:
            # Mock current date before enrollment_start
            mock_datetime.now.return_value = timezone.make_aware(datetime(2022, 12, 21))
            mock_datetime.now.date.return_value = timezone.make_aware(datetime(2022, 12, 21)).date()
            assert sc.is_enabled_to_enroll(period=period) is False

            # Mock current date within enrollment_start and enrollment_end
            mock_datetime.now.return_value = timezone.make_aware(datetime(2022, 12, 25))
            mock_datetime.now.date.return_value = timezone.make_aware(datetime(2022, 12, 25)).date()
            assert sc.is_enabled_to_enroll(period=period) is True

            # Mock current date after date_start and before date_end
            mock_datetime.now.return_value = timezone.make_aware(datetime(2023, 1, 1))
            mock_datetime.now.date.return_value = timezone.make_aware(datetime(2023, 1, 1)).date()
            assert sc.is_enabled_to_enroll(period=period) is True

            # Mock current date after date_start and before date_end
            mock_datetime.now.return_value = timezone.make_aware(datetime(2023, 1, 1))
            mock_datetime.now.date.return_value = timezone.make_aware(datetime(2023, 1, 1)).date()
            assert sc.is_enabled_to_enroll(period=period) is True

            # Mock current date after date_end
            mock_datetime.now.return_value = timezone.make_aware(datetime(2024, 1, 1))
            mock_datetime.now.date.return_value = timezone.make_aware(datetime(2024, 1, 1)).date()
            assert sc.is_enabled_to_enroll(period=period) is False
