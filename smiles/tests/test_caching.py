"""
Tests for the caching implementation in the Smiles app.

This module contains tests to verify that:
1. Cache hits occur as expected
2. Caches are properly cleared when data changes
3. Performance improvements are measurable
"""
import time
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from smiles.models import Activity
from smiles.models import ActivityType
from smiles.models import Group
from smiles.models import Member
from smiles.models import MemberGroupAssignment
from smiles.models import ScheduleAssignment
from smiles.models import ScheduleTemplate
from smiles.models import Subject
from smiles.models import SubjectOffering
from smiles.models import SubjectType
from smiles.models import Term
from smiles.models import TimeSlot
from smiles.services import TermService


class CacheHitTestCase(TestCase):
    """Test that cache hits occur as expected."""

    def setUp(self):
        """Set up test data."""
        # Create a term
        self.term = Term.objects.create(
            name="Test Term",
            term_type="Workshop Period",
            date_start=timezone.now().date(),
            date_end=timezone.now().date() + timedelta(days=30),
        )

        # Create a group
        self.group = Group.objects.create(
            name="Test Group",
            group_type="Cycle",
        )

        # Create a member
        self.member = Member.objects.create(
            username="testuser",
            email="test@example.com",
            first_name="Test",
            last_name="User",
        )

        # Create a member group assignment
        self.assignment = MemberGroupAssignment.objects.create(
            member=self.member,
            group=self.group,
        )

        # Create a subject type
        self.subject_type = SubjectType.objects.create(
            name="Test Subject Type",
            is_selectable=True,
        )

        # Create a subject
        self.subject = Subject.objects.create(
            name="Test Subject",
            type=self.subject_type,
        )

        # Create a subject offering
        self.subject_offering = SubjectOffering.objects.create(
            subject=self.subject,
            term=self.term,
            max_students=10,
        )
        self.subject_offering.eligible_groups.add(self.group)

        # Create a time slot
        self.time_slot = TimeSlot.objects.create(
            name="Test Time Slot",
            day_of_week="Monday",
            time_start="09:00:00",
            time_end="10:00:00",
        )

        # Create an activity type
        self.activity_type = ActivityType.objects.create(
            name="Test Activity Type",
            requires_attendance=True,
        )

        # Create an activity
        self.activity = Activity.objects.create(
            name="Test Activity",
            type=self.activity_type,
            subject_offering=self.subject_offering,
        )

        # Create a schedule template
        self.template = ScheduleTemplate.objects.create(
            name="Test Template",
        )

        # Create a schedule assignment
        self.assignment_schedule = ScheduleAssignment.objects.create(
            template=self.template,
            time_slot=self.time_slot,
            activity=self.activity,
        )

        # Add the subject offering to the member group assignment
        self.assignment.subject_offerings.add(self.subject_offering)

    def test_term_service_current_cache_hit(self):
        """Test that TermService.current() uses cache on subsequent calls."""
        # Clear the cache first
        TermService.current.cache_clear()

        # First call should hit the database
        with self.assertNumQueries(1):
            term1 = TermService.current()

        # Second call should use the cache
        with self.assertNumQueries(0):
            term2 = TermService.current()

        # Both calls should return the same object
        self.assertEqual(term1, term2)

    def test_term_service_get_term_by_date_cache_hit(self):
        """Test that TermService.get_term_by_date() uses cache on subsequent calls."""
        # Clear the cache first
        TermService.get_term_by_date.cache_clear()

        today = timezone.now().date()

        # First call should hit the database
        with self.assertNumQueries(1):
            term1 = TermService.get_term_by_date(today)

        # Second call should use the cache
        with self.assertNumQueries(0):
            term2 = TermService.get_term_by_date(today)

        # Both calls should return the same object
        self.assertEqual(term1, term2)

    def test_member_group_assignment_subject_offerings_by_time_slot_cache_hit(self):
        """Test that MemberGroupAssignment.subject_offerings_by_time_slot() uses cache."""
        # Clear the cache first
        self.assignment.subject_offerings_by_time_slot.cache_clear()

        # First call should hit the database multiple times
        with self.assertNumQueries(lambda x: x > 1):
            offerings1 = self.assignment.subject_offerings_by_time_slot()

        # Second call should use the cache
        with self.assertNumQueries(0):
            offerings2 = self.assignment.subject_offerings_by_time_slot()

        # Both calls should return the same result
        self.assertEqual(offerings1, offerings2)

    def test_member_group_assignment_is_schedule_full_cache_hit(self):
        """Test that MemberGroupAssignment.is_schedule_full() uses cache."""
        # Clear the cache first
        self.assignment.is_schedule_full.cache_clear()

        # First call should hit the database
        with self.assertNumQueries(lambda x: x > 0):
            result1 = self.assignment.is_schedule_full(self.term)

        # Second call should use the cache
        with self.assertNumQueries(0):
            result2 = self.assignment.is_schedule_full(self.term)

        # Both calls should return the same result
        self.assertEqual(result1, result2)


class CacheClearingTestCase(TestCase):
    """Test that caches are properly cleared when data changes."""

    def setUp(self):
        """Set up test data."""
        # Create a term
        self.term = Term.objects.create(
            name="Test Term",
            term_type="Workshop Period",
            date_start=timezone.now().date(),
            date_end=timezone.now().date() + timedelta(days=30),
        )

        # Create a group
        self.group = Group.objects.create(
            name="Test Group",
            group_type="Cycle",
        )

        # Create a member
        self.member = Member.objects.create(
            username="testuser",
            email="test@example.com",
            first_name="Test",
            last_name="User",
        )

        # Create a member group assignment
        self.assignment = MemberGroupAssignment.objects.create(
            member=self.member,
            group=self.group,
        )

        # Create a subject type
        self.subject_type = SubjectType.objects.create(
            name="Test Subject Type",
            is_selectable=True,
        )

        # Create a subject
        self.subject = Subject.objects.create(
            name="Test Subject",
            type=self.subject_type,
        )

        # Create a subject offering
        self.subject_offering = SubjectOffering.objects.create(
            subject=self.subject,
            term=self.term,
            max_students=10,
        )
        self.subject_offering.eligible_groups.add(self.group)

        # Add the subject offering to the member group assignment
        self.assignment.subject_offerings.add(self.subject_offering)

    def test_term_service_cache_cleared_on_term_save(self):
        """Test that TermService caches are cleared when a Term is saved."""
        # Prime the cache
        TermService.current()

        # Modify the term
        self.term.name = "Updated Term"
        self.term.save()

        # Cache should be cleared, so this should hit the database
        with self.assertNumQueries(1):
            term2 = TermService.current()

        # The result should reflect the updated term
        self.assertEqual(term2.name, "Updated Term")

    def test_member_group_assignment_cache_cleared_on_m2m_change(self):
        """Test that MemberGroupAssignment caches are cleared when M2M relationships change."""
        # Prime the cache
        offerings1 = self.assignment.subject_offerings_by_time_slot()

        # Create a new subject offering
        new_offering = SubjectOffering.objects.create(
            subject=self.subject,
            term=self.term,
            max_students=10,
        )
        new_offering.eligible_groups.add(self.group)

        # Add the new offering to the assignment
        self.assignment.subject_offerings.add(new_offering)

        # Cache should be cleared, so this should hit the database
        with self.assertNumQueries(lambda x: x > 0):
            offerings2 = self.assignment.subject_offerings_by_time_slot()

        # The result should include the new offering
        self.assertNotEqual(len(offerings1), len(offerings2))

    def test_member_group_assignment_cache_cleared_on_save(self):
        """Test that MemberGroupAssignment caches are cleared when the object is saved."""
        # Prime the cache
        self.assignment.subject_offerings_by_time_slot()

        # Modify and save the assignment
        self.assignment.is_active = False
        self.assignment.save()

        # Cache should be cleared, so this should hit the database
        with self.assertNumQueries(lambda x: x > 0):
            self.assignment.subject_offerings_by_time_slot()


class PerformanceTestCase(TestCase):
    """Test that caching improves performance."""

    def setUp(self):
        """Set up test data."""
        # Create multiple terms
        for i in range(5):
            Term.objects.create(
                name=f"Term {i}",
                term_type="Workshop Period",
                date_start=timezone.now().date() + timedelta(days=i * 60),
                date_end=timezone.now().date() + timedelta(days=(i + 1) * 60 - 1),
            )

        # Create a current term
        self.current_term = Term.objects.create(
            name="Current Term",
            term_type="Workshop Period",
            date_start=timezone.now().date() - timedelta(days=15),
            date_end=timezone.now().date() + timedelta(days=15),
        )

    def test_term_service_current_performance(self):
        """Test that TermService.current() is faster with caching."""
        # Clear the cache first
        TermService.current.cache_clear()

        # Measure time for first call (no cache)
        start_time = time.time()
        term1 = TermService.current()
        first_call_time = time.time() - start_time

        # Measure time for second call (with cache)
        start_time = time.time()
        term2 = TermService.current()
        second_call_time = time.time() - start_time

        # Second call should be significantly faster
        self.assertLess(second_call_time, first_call_time)

        # Both calls should return the same object
        self.assertEqual(term1, term2)

    def test_term_service_get_term_by_date_performance(self):
        """Test that TermService.get_term_by_date() is faster with caching."""
        # Clear the cache first
        TermService.get_term_by_date.cache_clear()

        today = timezone.now().date()

        # Measure time for first call (no cache)
        start_time = time.time()
        term1 = TermService.get_term_by_date(today)
        first_call_time = time.time() - start_time

        # Measure time for second call (with cache)
        start_time = time.time()
        term2 = TermService.get_term_by_date(today)
        second_call_time = time.time() - start_time

        # Second call should be significantly faster
        self.assertLess(second_call_time, first_call_time)

        # Both calls should return the same object
        self.assertEqual(term1, term2)
