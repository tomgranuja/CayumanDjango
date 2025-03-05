"""
Tests for performance after migration from Cayuman to Smiles.

This module contains tests to verify that:
1. Database queries are optimized
2. Cache hit rates are acceptable
3. Page load times are reasonable
"""
import functools
import time
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import Group as AuthGroup
from django.db import connection
from django.db import reset_queries
from django.test import Client
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from smiles.models import Activity
from smiles.models import ActivityType
from smiles.models import Event
from smiles.models import EventType
from smiles.models import Group
from smiles.models import Member
from smiles.models import MemberGroupAssignment
from smiles.models import Subject
from smiles.models import SubjectOffering
from smiles.models import SubjectType
from smiles.models import Term
from smiles.models import TimeSlot
from smiles.services import EnrollmentService
from smiles.services import TermService


def query_counter(func):
    """Decorator to count database queries."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        reset_queries()
        # Store the DEBUG setting and temporarily enable it
        old_debug = settings.DEBUG
        settings.DEBUG = True

        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()

        query_count = len(connection.queries)
        query_time = sum(float(q["time"]) for q in connection.queries)

        print(f"{func.__name__} used {query_count} queries in {end - start:.2f}s")
        print(f"Query time: {query_time:.2f}s")

        # Restore the DEBUG setting
        settings.DEBUG = old_debug
        return result

    return wrapper


class QueryOptimizationTestCase(TestCase):
    """Test that database queries are optimized."""

    def setUp(self):
        """Set up test data."""
        # Create student and teacher groups
        self.students_group = AuthGroup.objects.create(name="Students")
        self.teachers_group = AuthGroup.objects.create(name="Teachers")

        # Create terms
        self.terms = []
        for i in range(5):
            term = Term.objects.create(
                name=f"Term {i}",
                term_type="Workshop Period",
                date_start=timezone.now().date() + timedelta(days=i * 60),
                date_end=timezone.now().date() + timedelta(days=(i + 1) * 60 - 1),
            )
            self.terms.append(term)

        # Create groups
        self.groups = []
        for i in range(5):
            group = Group.objects.create(
                name=f"Group {i}",
                group_type="Cycle",
            )
            self.groups.append(group)

        # Create students
        self.students = []
        for i in range(20):
            student = Member.objects.create_user(
                username=f"student{i}",
                email=f"student{i}@example.com",
                first_name=f"Student{i}",
                last_name="User",
                password="password",
                is_staff=True,
            )
            student.groups.add(self.students_group)
            self.students.append(student)

        # Create teachers
        self.teachers = []
        for i in range(5):
            teacher = Member.objects.create_user(
                username=f"teacher{i}",
                email=f"teacher{i}@example.com",
                first_name=f"Teacher{i}",
                last_name="User",
                password="password",
                is_staff=True,
            )
            teacher.groups.add(self.teachers_group)
            self.teachers.append(teacher)

        # Create member group assignments
        self.assignments = []
        for student in self.students:
            for group in self.groups:
                assignment = MemberGroupAssignment.objects.create(
                    member=student,
                    group=group,
                )
                self.assignments.append(assignment)

        # Create subject types
        self.subject_types = []
        for i in range(3):
            subject_type = SubjectType.objects.create(
                name=f"Subject Type {i}",
                is_selectable=True,
            )
            self.subject_types.append(subject_type)

        # Create subjects
        self.subjects = []
        for i in range(10):
            subject = Subject.objects.create(
                name=f"Subject {i}",
                type=self.subject_types[i % 3],
            )
            self.subjects.append(subject)

        # Create enrollment event type
        self.enrollment_type, created = EventType.objects.get_or_create(
            name="Enrollment",
            defaults={"description": "Enrollment period for subjects"},
        )

        # Create enrollment events
        self.enrollment_events = []
        for term in self.terms:
            event = Event.objects.create(
                name=f"Enrollment for {term.name}",
                type=self.enrollment_type,
                term=term,
                preview_date=term.date_start - timedelta(days=15),
                date_start=term.date_start - timedelta(days=10),
                date_end=term.date_start - timedelta(days=1),
                is_active=True,
            )
            for group in self.groups:
                event.affects_groups.add(group)
            self.enrollment_events.append(event)

        # Create subject offerings
        self.subject_offerings = []
        for term in self.terms:
            for subject in self.subjects:
                for teacher in self.teachers:
                    offering = SubjectOffering.objects.create(
                        subject=subject,
                        term=term,
                        teacher=teacher,
                        max_students=10,
                        enrollment_event=self.enrollment_events[self.terms.index(term)],
                    )
                    for group in self.groups:
                        offering.eligible_groups.add(group)
                    self.subject_offerings.append(offering)

        # Create time slots
        self.time_slots = []
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        times = [
            ("09:00:00", "10:00:00"),
            ("10:00:00", "11:00:00"),
            ("11:00:00", "12:00:00"),
            ("13:00:00", "14:00:00"),
            ("14:00:00", "15:00:00"),
        ]
        for day in days:
            for time_start, time_end in times:
                time_slot = TimeSlot.objects.create(
                    name=f"{day} {time_start}-{time_end}",
                    day_of_week=day,
                    time_start=time_start,
                    time_end=time_end,
                )
                self.time_slots.append(time_slot)

        # Create activity type
        self.activity_type = ActivityType.objects.create(
            name="Class",
            requires_attendance=True,
        )

        # Create activities
        self.activities = []
        for offering in self.subject_offerings[:20]:  # Limit to first 20 offerings
            for time_slot in self.time_slots[:5]:  # Limit to first 5 time slots
                activity = Activity.objects.create(
                    name=f"{offering.subject.name} {time_slot.name}",
                    type=self.activity_type,
                    subject_offering=offering,
                )
                self.activities.append(activity)

        # Enroll students in subject offerings
        for i, assignment in enumerate(self.assignments[:100]):  # Limit to first 100 assignments
            assignment.subject_offerings.add(self.subject_offerings[i % len(self.subject_offerings)])

        # Create a client
        self.client = Client()

        # Log in as a student
        self.client.login(username=self.students[0].username, password="password")

    @query_counter
    def test_term_service_current(self):
        """Test that TermService.current() is optimized."""
        # First call should query the database
        term = TermService.current()
        self.assertIsNotNone(term)

        # Reset queries
        reset_queries()

        # Second call should use the cache
        term = TermService.current()
        self.assertIsNotNone(term)

        # Should be 0 queries due to caching
        self.assertEqual(len(connection.queries), 0)

    @query_counter
    def test_term_service_current_or_last(self):
        """Test that TermService.current_or_last() is optimized."""
        # First call should query the database
        term = TermService.current_or_last()
        self.assertIsNotNone(term)

        # Reset queries
        reset_queries()

        # Second call should use the cache
        term = TermService.current_or_last()
        self.assertIsNotNone(term)

        # Should be 0 queries due to caching
        self.assertEqual(len(connection.queries), 0)

    @query_counter
    def test_enrollment_service_get_available_offerings(self):
        """Test that EnrollmentService.get_available_offerings() is optimized."""
        # Get available offerings for the student
        offerings = EnrollmentService.get_available_offerings(self.students[0], self.terms[0])
        self.assertTrue(len(offerings) > 0)

        # Should use select_related and prefetch_related to minimize queries
        self.assertLess(len(connection.queries), 10)

    @query_counter
    def test_subject_offering_count_students(self):
        """Test that SubjectOffering.count_students() is optimized."""
        # Count students in a subject offering
        count = self.subject_offerings[0].count_students()
        self.assertIsNotNone(count)

        # Should use annotations to minimize queries
        self.assertLess(len(connection.queries), 3)


class CacheHitRateTestCase(TestCase):
    """Test that cache hit rates are acceptable."""

    def setUp(self):
        """Set up test data."""
        # Create a term
        self.term = Term.objects.create(
            name="Test Term",
            term_type="Workshop Period",
            date_start=timezone.now().date(),
            date_end=timezone.now().date() + timedelta(days=30),
        )

    def test_term_service_current_cache_hit(self):
        """Test that TermService.current() has a high cache hit rate."""
        # Clear the cache
        TermService.current.cache_clear()

        # First call should be a cache miss
        term1 = TermService.current()

        # Second call should be a cache hit
        term2 = TermService.current()

        # Both calls should return the same term
        self.assertEqual(term1, term2)

        # Create a new term that would be current
        new_term = Term.objects.create(
            name="New Term",
            term_type="Workshop Period",
            date_start=timezone.now().date() - timedelta(days=5),
            date_end=timezone.now().date() + timedelta(days=25),
        )

        # Call should still return the cached term
        term3 = TermService.current()
        self.assertEqual(term1, term3)

        # Clear the cache
        TermService.current.cache_clear()

        # Call should now return the new term
        term4 = TermService.current()
        self.assertEqual(new_term, term4)


class PageLoadTimeTestCase(TestCase):
    """Test that page load times are reasonable."""

    def setUp(self):
        """Set up test data."""
        # Create student and teacher groups
        self.students_group = AuthGroup.objects.create(name="Students")
        self.teachers_group = AuthGroup.objects.create(name="Teachers")

        # Create a term
        self.term = Term.objects.create(
            name="Test Term",
            term_type="Workshop Period",
            date_start=timezone.now().date(),
            date_end=timezone.now().date() + timedelta(days=30),
        )

        # Create an enrollment event type
        self.enrollment_type = EventType.objects.create(
            name="Enrollment",
            description="Enrollment period for subjects",
        )

        # Create an enrollment event
        self.enrollment_event = Event.objects.create(
            name="Test Enrollment",
            type=self.enrollment_type,
            term=self.term,
            preview_date=timezone.now() - timedelta(days=5),
            date_start=timezone.now() - timedelta(days=2),
            date_end=timezone.now() + timedelta(days=5),
            is_active=True,
        )

        # Create a group
        self.group = Group.objects.create(
            name="Test Group",
            group_type="Cycle",
        )

        # Associate the group with the enrollment event
        self.enrollment_event.affects_groups.add(self.group)

        # Create a student
        self.student = Member.objects.create_user(
            username="student",
            email="student@example.com",
            first_name="Student",
            last_name="User",
            password="password",
            is_staff=True,
        )
        self.student.groups.add(self.students_group)

        # Create a teacher
        self.teacher = Member.objects.create_user(
            username="teacher",
            email="teacher@example.com",
            first_name="Teacher",
            last_name="User",
            password="password",
            is_staff=True,
        )
        self.teacher.groups.add(self.teachers_group)

        # Create a member group assignment
        self.assignment = MemberGroupAssignment.objects.create(
            member=self.student,
            group=self.group,
        )

        # Create a subject type
        self.subject_type = SubjectType.objects.create(
            name="Test Subject Type",
            is_selectable=True,
        )

        # Create subjects
        self.subjects = []
        for i in range(20):
            subject = Subject.objects.create(
                name=f"Subject {i}",
                type=self.subject_type,
            )
            self.subjects.append(subject)

        # Create subject offerings
        self.subject_offerings = []
        for subject in self.subjects:
            offering = SubjectOffering.objects.create(
                subject=subject,
                term=self.term,
                teacher=self.teacher,
                max_students=10,
                enrollment_event=self.enrollment_event,
            )
            offering.eligible_groups.add(self.group)
            self.subject_offerings.append(offering)

        # Create a client
        self.client = Client()

        # Log in as a student
        self.client.login(username="student", password="password")

    def test_home_page_load_time(self):
        """Test that the home page loads in a reasonable time."""
        # Get the home page
        start = time.time()
        response = self.client.get(reverse("smiles:home"))
        end = time.time()

        # Check that the response is 200 OK
        self.assertEqual(response.status_code, 200)

        # Check that the page loaded in a reasonable time (less than 1 second)
        self.assertLess(end - start, 1.0)

    def test_term_list_page_load_time(self):
        """Test that the term list page loads in a reasonable time."""
        # Get the term list page
        start = time.time()
        response = self.client.get(reverse("smiles:term_list"))
        end = time.time()

        # Check that the response is 200 OK
        self.assertEqual(response.status_code, 200)

        # Check that the page loaded in a reasonable time (less than 1 second)
        self.assertLess(end - start, 1.0)

    def test_term_detail_page_load_time(self):
        """Test that the term detail page loads in a reasonable time."""
        # Get the term detail page
        start = time.time()
        response = self.client.get(reverse("smiles:term_detail", args=[self.term.id]))
        end = time.time()

        # Check that the response is 200 OK
        self.assertEqual(response.status_code, 200)

        # Check that the page loaded in a reasonable time (less than 1 second)
        self.assertLess(end - start, 1.0)
