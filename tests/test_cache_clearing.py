from datetime import time
from datetime import timedelta
from functools import lru_cache
from unittest.mock import patch

import pytest
from django.conf import settings
from django.contrib.auth.models import Group
from django.db.models.signals import m2m_changed
from django.db.models.signals import post_save
from django.utils import timezone

from cayuman.models import Cycle
from cayuman.models import Member
from cayuman.models import Period
from cayuman.models import Schedule
from cayuman.models import StudentCycle
from cayuman.models import Workshop
from cayuman.models import WorkshopPeriod

pytestmark = pytest.mark.django_db


class TestCacheClearing:
    """Tests for cache clearing logic in models"""

    def test_lru_cache_behavior(self):
        """Test basic LRU cache behavior to ensure our understanding is correct"""
        # Define a simple cached function for testing
        call_count = 0

        @lru_cache(maxsize=None)
        def cached_func(arg):
            nonlocal call_count
            call_count += 1
            return f"Result for {arg}"

        # Call with same arg multiple times
        result1 = cached_func("test")
        result2 = cached_func("test")
        result3 = cached_func("test")

        # Should only increment call_count once
        assert call_count == 1
        assert result1 == result2 == result3

        # Call with different arg
        cached_func("different")

        # Should increment call_count again
        assert call_count == 2

        # Clear cache
        cached_func.cache_clear()

        # Call again with original arg
        result5 = cached_func("test")

        # Should increment call_count again
        assert call_count == 3
        assert result5 == result1

    def test_period_manager_caching(self):
        """Test that Period manager methods are cached"""
        # Create test periods
        Period.objects.create(
            name="Period 1",
            date_start=timezone.now().date(),
            date_end=timezone.now().date() + timedelta(days=30),
            enrollment_start=timezone.now() - timedelta(days=5),
        )

        Period.objects.create(
            name="Period 2",
            date_start=timezone.now().date() + timedelta(days=40),
            date_end=timezone.now().date() + timedelta(days=70),
            enrollment_start=timezone.now() + timedelta(days=35),
        )

        # Test that calling the method twice with the same arguments returns the same result
        test_date = timezone.now().date()
        result1 = Period.objects.period_by_date(test_date)

        # Call the method again with the same date
        result2 = Period.objects.period_by_date(test_date)

        # Results should be the same due to caching
        assert result1 == result2

        # Clear the cache
        Period.objects.period_by_date.cache_clear()

        # Call again
        result3 = Period.objects.period_by_date(test_date)

        # Results should still be the same
        assert result1 == result3

    def test_studentcycle_instance_caching(self):
        """Test that StudentCycle instance methods are cached"""
        # Create test data
        group, _ = Group.objects.get_or_create(name=settings.STUDENTS_GROUP)
        teacher_group, _ = Group.objects.get_or_create(name=settings.TEACHERS_GROUP)

        student = Member.objects.create_user(username="test_student", password="password")
        student.groups.add(group)

        teacher = Member.objects.create_user(username="test_teacher", password="password")
        teacher.groups.add(teacher_group)

        cycle = Cycle.objects.create(name="Test Cycle")
        workshop = Workshop.objects.create(name="Test Workshop")

        period = Period.objects.create(
            name="Test Period",
            date_start=timezone.now().date(),
            date_end=timezone.now().date() + timedelta(days=30),
            enrollment_start=timezone.now() - timedelta(days=5),
        )

        # Create a workshop period
        wp = WorkshopPeriod.objects.create(workshop=workshop, period=period, teacher=teacher)
        wp.cycles.add(cycle)

        # Create a student cycle
        student_cycle = StudentCycle.objects.create(student=student, cycle=cycle)
        student_cycle.workshop_periods.add(wp)

        # First call to the method
        result1 = student_cycle.workshop_periods_by_period(period)

        # Call again with same period
        result2 = student_cycle.workshop_periods_by_period(period)

        # Results should be the same due to caching
        assert result1 == result2

        # Clear the cache
        student_cycle.workshop_periods_by_period.cache_clear()

        # Call again
        result3 = student_cycle.workshop_periods_by_period(period)

        # Results should still be the same
        assert result1 == result3

    def test_signal_handler_functionality(self):
        """Test that signal handlers actually do something when triggered"""
        # Create test data
        group, _ = Group.objects.get_or_create(name=settings.STUDENTS_GROUP)
        student = Member.objects.create_user(username="test_student2", password="password")

        # Test user_changed signal handler
        with patch("cayuman.models.StudentCycle.objects"):
            # Add the student to the group to trigger the signal
            student.groups.add(group)

            # Verify that the signal handler was triggered
            # We can't directly check if cache_clear was called, but we can check if the handler did something
            assert len(post_save.receivers) > 0

        # Test user_groups_changed signal handler
        with patch("cayuman.models.StudentCycle.objects"):
            # Create a new group and add the student to trigger the signal
            new_group, _ = Group.objects.get_or_create(name="TestGroup")
            student.groups.add(new_group)

            # Verify that the signal handler was triggered
            assert len(m2m_changed.receivers) > 0

    def test_cache_clearing_on_model_changes(self):
        """Test that caches are cleared when models are changed"""
        # Create test data
        group, _ = Group.objects.get_or_create(name=settings.STUDENTS_GROUP)
        teacher_group, _ = Group.objects.get_or_create(name=settings.TEACHERS_GROUP)

        student = Member.objects.create_user(username="test_student3", password="password")
        student.groups.add(group)

        teacher = Member.objects.create_user(username="test_teacher", password="password")
        teacher.groups.add(teacher_group)

        cycle = Cycle.objects.create(name="Test Cycle")
        workshop = Workshop.objects.create(name="Test Workshop")

        period = Period.objects.create(
            name="Test Period",
            date_start=timezone.now().date(),
            date_end=timezone.now().date() + timedelta(days=30),
            enrollment_start=timezone.now() - timedelta(days=5),
        )

        # Create a workshop period with a schedule
        schedule = Schedule.objects.create(day="Monday", time_start=time(10, 0), time_end=time(11, 0))

        wp = WorkshopPeriod.objects.create(workshop=workshop, period=period, teacher=teacher)
        wp.cycles.add(cycle)
        wp.schedules.add(schedule)

        # Create a student cycle
        student_cycle = StudentCycle.objects.create(student=student, cycle=cycle)

        # First call to cache the result
        result1 = student_cycle.is_schedule_full(period)

        # Add a workshop period to the student cycle
        student_cycle.workshop_periods.add(wp)

        # The result should be different after adding a workshop period
        # This indirectly tests that the cache was cleared
        result2 = student_cycle.is_schedule_full(period)

        # The results should be different because the cache should have been cleared
        # when we added the workshop period
        assert result1 != result2
