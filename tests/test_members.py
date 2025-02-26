from datetime import datetime
from datetime import time

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from cayuman.models import Period
from cayuman.models import StudentCycle

pytestmark = pytest.mark.django_db


def test_member_can_be_student(create_user, create_groups):
    user = create_user
    student_group, _ = create_groups
    user.groups.add(student_group)
    assert user.is_student
    assert not user.is_teacher


def test_member_can_be_teacher(create_user, create_groups):
    user = create_user
    _, teacher_group = create_groups
    user.groups.add(teacher_group)
    assert user.is_teacher
    assert not user.is_student


def test_member_cannot_be_both_student_and_teacher(create_user, create_groups):
    student_group, teacher_group = create_groups
    user = create_user
    with pytest.raises(ValidationError, match=r"must not be both"):
        user.groups.add(student_group, teacher_group)


def test_member_cannot_be_student_and_staff(create_user, create_groups):
    student_group, _ = create_groups
    user = create_user
    user.is_staff = True
    user.save()
    user.groups.clear()
    with pytest.raises(ValidationError, match=r"staff"):
        user.groups.add(student_group)


def test_member_can_be_staff_only(create_user):
    user = create_user
    user.is_staff = True
    user.save()  # No ValidationError expected
    assert not user.is_student
    assert not user.is_teacher
    assert user.is_staff


def test_get_studentcycle_for_period(create_student, create_period, create_cycles):
    """Test get_studentcycle_for_period method"""
    student = create_student
    period = create_period
    cycle = create_cycles[0]

    # Create a StudentCycle for the student
    student_cycle = StudentCycle.objects.create(student=student, cycle=cycle)

    # Test getting studentcycle for period
    assert student.get_studentcycle_for_period(period) == student_cycle

    # Test getting studentcycle for future period - should return latest studentcycle
    future_period = Period.objects.create(
        name="Future Period",
        enrollment_start=timezone.now() + timezone.timedelta(days=1),
        date_start=timezone.now().date() + timezone.timedelta(days=2),
        date_end=timezone.now().date() + timezone.timedelta(days=30),
    )

    assert student.get_studentcycle_for_period(future_period) == student_cycle

    # Test getting studentcycle for past period - should raise ValueError
    past_period = Period.objects.create(
        name="Past Period",
        enrollment_start=timezone.now() - timezone.timedelta(days=31),
        date_start=timezone.now().date() - timezone.timedelta(days=30),
        date_end=timezone.now().date() - timezone.timedelta(days=1),
    )

    with pytest.raises(ValueError):
        student.get_studentcycle_for_period(past_period)


def test_get_studentcycle_for_period_or_none(create_student, create_period, create_cycles):
    """Test get_studentcycle_for_period_or_none method"""
    student = create_student
    period = create_period
    cycle = create_cycles[0]

    # Create a StudentCycle for the student
    student_cycle = StudentCycle.objects.create(student=student, cycle=cycle)

    # Test getting studentcycle for period
    assert student.get_studentcycle_for_period_or_none(period) == student_cycle

    # Test getting studentcycle for future period - should return latest studentcycle
    future_period = Period.objects.create(
        name="Future Period",
        enrollment_start=timezone.now() + timezone.timedelta(days=1),
        date_start=timezone.now().date() + timezone.timedelta(days=2),
        date_end=timezone.now().date() + timezone.timedelta(days=30),
    )

    assert student.get_studentcycle_for_period_or_none(future_period) == student_cycle

    # Test getting studentcycle for past period - should return None
    past_period = Period.objects.create(
        name="Past Period",
        enrollment_start=timezone.now() - timezone.timedelta(days=31),
        date_start=timezone.now().date() - timezone.timedelta(days=30),
        date_end=timezone.now().date() - timezone.timedelta(days=1),
    )

    assert student.get_studentcycle_for_period_or_none(past_period) is None


def test_get_studentcycle_for_date(create_student, create_period, create_cycles):
    """Test get_studentcycle_for_date method"""
    student = create_student
    period = create_period
    cycle = create_cycles[0]

    # Create a StudentCycle for the student
    student_cycle = StudentCycle.objects.create(student=student, cycle=cycle)

    # Test getting studentcycle for date within period
    date_in_period = period.date_start + timezone.timedelta(days=1)
    assert student.get_studentcycle_for_date(date_in_period) == student_cycle

    # Test getting studentcycle for datetime within period
    datetime_in_period = timezone.make_aware(datetime.combine(date_in_period, time(12, 0)))
    assert student.get_studentcycle_for_date(datetime_in_period) == student_cycle

    # Test getting studentcycle for date not in any period
    future_date = period.date_end + timezone.timedelta(days=1)
    with pytest.raises(ValueError):
        student.get_studentcycle_for_date(future_date)


def test_get_studentcycle_for_date_or_none(create_student, create_period, create_cycles):
    """Test get_studentcycle_for_date_or_none method"""
    student = create_student
    period = create_period
    cycle = create_cycles[0]

    # Create a StudentCycle for the student
    student_cycle = StudentCycle.objects.create(student=student, cycle=cycle)

    # Test getting studentcycle for date within period
    date_in_period = period.date_start + timezone.timedelta(days=1)
    assert student.get_studentcycle_for_date_or_none(date_in_period) == student_cycle

    # Test getting studentcycle for datetime within period
    datetime_in_period = timezone.make_aware(datetime.combine(date_in_period, time(12, 0)))
    assert student.get_studentcycle_for_date_or_none(datetime_in_period) == student_cycle

    # Test getting studentcycle for date not in any period
    future_date = period.date_end + timezone.timedelta(days=1)
    assert student.get_studentcycle_for_date_or_none(future_date) is None
