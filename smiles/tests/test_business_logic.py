"""
Tests for business logic after migration from Cayuman to Smiles.

This module contains tests to verify that:
1. Enrollment functionality works with migrated data
2. Time-sensitive functions work correctly
3. Permissions are correctly applied
"""
from datetime import timedelta

from django.contrib.auth.models import Group as AuthGroup
from django.test import TestCase
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


class EnrollmentFunctionalityTestCase(TestCase):
    """Test enrollment functionality with migrated data."""

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
        self.enrollment_type, created = EventType.objects.get_or_create(
            name="Enrollment",
            defaults={"description": "Enrollment period for subjects"},
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

        # Create a subject
        self.subject = Subject.objects.create(
            name="Test Subject",
            type=self.subject_type,
        )

        # Create a subject offering
        self.subject_offering = SubjectOffering.objects.create(
            subject=self.subject,
            term=self.term,
            teacher=self.teacher,
            max_students=10,
            enrollment_event=self.enrollment_event,
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

    def test_enrollment_service_get_available_offerings(self):
        """Test that EnrollmentService.get_available_offerings() returns the correct offerings."""
        # Get available offerings for the student
        available_offerings = EnrollmentService.get_available_offerings(self.student, self.term)

        # The subject offering should be available
        self.assertIn(self.subject_offering, available_offerings)

        # Create a new subject offering with a different group
        other_group = Group.objects.create(
            name="Other Group",
            group_type="Cycle",
        )

        other_offering = SubjectOffering.objects.create(
            subject=self.subject,
            term=self.term,
            teacher=self.teacher,
            max_students=10,
            enrollment_event=self.enrollment_event,
        )
        other_offering.eligible_groups.add(other_group)

        # Get available offerings again
        available_offerings = EnrollmentService.get_available_offerings(self.student, self.term)

        # The other offering should not be available
        self.assertNotIn(other_offering, available_offerings)

    def test_enrollment_service_can_enroll(self):
        """Test that EnrollmentService.can_enroll() returns the correct result."""
        # Check if the student can enroll in the subject offering
        can_enroll, reason = EnrollmentService.can_enroll(self.student, self.subject_offering)

        # The student should be able to enroll
        self.assertTrue(can_enroll)

        # Create a subject offering with max_students=0
        unlimited_offering = SubjectOffering.objects.create(
            subject=self.subject,
            term=self.term,
            teacher=self.teacher,
            max_students=0,
            enrollment_event=self.enrollment_event,
        )
        unlimited_offering.eligible_groups.add(self.group)

        # Check if the student can enroll in the unlimited offering
        can_enroll, reason = EnrollmentService.can_enroll(self.student, unlimited_offering)

        # The student should be able to enroll
        self.assertTrue(can_enroll)

        # Create a subject offering with max_students=1 and enroll a student
        limited_offering = SubjectOffering.objects.create(
            subject=self.subject,
            term=self.term,
            teacher=self.teacher,
            max_students=1,
            enrollment_event=self.enrollment_event,
        )
        limited_offering.eligible_groups.add(self.group)

        # Create another student and enroll them in the limited offering
        other_student = Member.objects.create_user(
            username="other_student",
            email="other_student@example.com",
            first_name="Other",
            last_name="Student",
            password="password",
            is_staff=True,
        )
        other_student.groups.add(self.students_group)

        other_assignment = MemberGroupAssignment.objects.create(
            member=other_student,
            group=self.group,
        )
        other_assignment.subject_offerings.add(limited_offering)

        # Check if the student can enroll in the limited offering
        can_enroll, reason = EnrollmentService.can_enroll(self.student, limited_offering)

        # The student should not be able to enroll
        self.assertFalse(can_enroll)
        self.assertIn("maximum enrollment", reason.lower())

    def test_member_group_assignment_enrollment(self):
        """Test that MemberGroupAssignment can enroll in subject offerings."""
        # Enroll the student in the subject offering
        self.assignment.subject_offerings.add(self.subject_offering)

        # Check if the student is enrolled
        self.assertIn(self.subject_offering, self.assignment.subject_offerings.all())

        # Check if the subject offering has the student enrolled
        self.assertIn(self.assignment, self.subject_offering.enrolled_members.all())

        # Check the count of students
        self.assertEqual(self.subject_offering.count_students(), 1)

        # Check the remaining quota
        self.assertEqual(self.subject_offering.remaining_quota(), 9)


class TimeSensitiveFunctionsTestCase(TestCase):
    """Test time-sensitive functions with migrated data."""

    def setUp(self):
        """Set up test data."""
        # Create a past term
        self.past_term = Term.objects.create(
            name="Past Term",
            term_type="Workshop Period",
            date_start=timezone.now().date() - timedelta(days=60),
            date_end=timezone.now().date() - timedelta(days=30),
        )

        # Create a current term
        self.current_term = Term.objects.create(
            name="Current Term",
            term_type="Workshop Period",
            date_start=timezone.now().date() - timedelta(days=15),
            date_end=timezone.now().date() + timedelta(days=15),
        )

        # Create a future term
        self.future_term = Term.objects.create(
            name="Future Term",
            term_type="Workshop Period",
            date_start=timezone.now().date() + timedelta(days=30),
            date_end=timezone.now().date() + timedelta(days=60),
        )

        # Create an enrollment event type
        self.enrollment_type, created = EventType.objects.get_or_create(
            name="Enrollment",
            defaults={"description": "Enrollment period for subjects"},
        )

        # Create an enrollment event for the current term
        self.current_enrollment_event = Event.objects.create(
            name="Current Enrollment",
            type=self.enrollment_type,
            term=self.current_term,
            preview_date=timezone.now() - timedelta(days=20),
            date_start=timezone.now() - timedelta(days=10),
            date_end=timezone.now() + timedelta(days=5),
            is_active=True,
        )

        # Create an enrollment event for the future term
        self.future_enrollment_event = Event.objects.create(
            name="Future Enrollment",
            type=self.enrollment_type,
            term=self.future_term,
            preview_date=timezone.now() + timedelta(days=15),
            date_start=timezone.now() + timedelta(days=20),
            date_end=timezone.now() + timedelta(days=25),
            is_active=True,
        )

    def test_term_is_current(self):
        """Test that Term.is_current() returns the correct result."""
        # The past term should not be current
        self.assertFalse(self.past_term.is_current())

        # The current term should be current
        self.assertTrue(self.current_term.is_current())

        # The future term should not be current
        self.assertFalse(self.future_term.is_current())

    def test_term_is_in_the_past(self):
        """Test that Term.is_in_the_past() returns the correct result."""
        # The past term should be in the past
        self.assertTrue(self.past_term.is_in_the_past())

        # The current term should not be in the past
        self.assertFalse(self.current_term.is_in_the_past())

        # The future term should not be in the past
        self.assertFalse(self.future_term.is_in_the_past())

    def test_term_is_in_the_future(self):
        """Test that Term.is_in_the_future() returns the correct result."""
        # The past term should not be in the future
        self.assertFalse(self.past_term.is_in_the_future())

        # The current term should not be in the future
        self.assertFalse(self.current_term.is_in_the_future())

        # The future term should be in the future
        self.assertTrue(self.future_term.is_in_the_future())

    def test_term_is_enabled_to_preview(self):
        """Test that Term.is_enabled_to_preview() returns the correct result."""
        # The past term should not be enabled for preview
        self.assertFalse(self.past_term.is_enabled_to_preview())

        # The current term should be enabled for preview
        self.assertTrue(self.current_term.is_enabled_to_preview())

        # The future term should not be enabled for preview yet
        self.assertFalse(self.future_term.is_enabled_to_preview())

    def test_term_is_enabled_to_enroll(self):
        """Test that Term.is_enabled_to_enroll() returns the correct result."""
        # The past term should not be enabled for enrollment
        self.assertFalse(self.past_term.is_enabled_to_enroll())

        # The current term should be enabled for enrollment
        self.assertTrue(self.current_term.is_enabled_to_enroll())

        # The future term should not be enabled for enrollment yet
        self.assertFalse(self.future_term.is_enabled_to_enroll())

    def test_term_service_current(self):
        """Test that TermService.current() returns the correct term."""
        # The current term should be returned
        self.assertEqual(TermService.current(), self.current_term)

    def test_term_service_current_or_last(self):
        """Test that TermService.current_or_last() returns the correct term."""
        # The current term should be returned
        self.assertEqual(TermService.current_or_last(), self.current_term)

        # Delete the current term
        self.current_term.delete()

        # Clear the cache
        TermService.current_or_last.cache_clear()

        # The past term should be returned
        self.assertEqual(TermService.current_or_last(), self.past_term)

    def test_term_service_get_term_by_date(self):
        """Test that TermService.get_term_by_date() returns the correct term."""
        # Get a date in the past term
        past_date = self.past_term.date_start + timedelta(days=5)

        # Get a date in the current term
        current_date = self.current_term.date_start + timedelta(days=5)

        # Get a date in the future term
        future_date = self.future_term.date_start + timedelta(days=5)

        # The past term should be returned for the past date
        self.assertEqual(TermService.get_term_by_date(past_date), self.past_term)

        # The current term should be returned for the current date
        self.assertEqual(TermService.get_term_by_date(current_date), self.current_term)

        # The future term should be returned for the future date
        self.assertEqual(TermService.get_term_by_date(future_date), self.future_term)


class PermissionsTestCase(TestCase):
    """Test permissions with migrated data."""

    def setUp(self):
        """Set up test data."""
        # Create student and teacher groups
        self.students_group = AuthGroup.objects.create(name="Students")
        self.teachers_group = AuthGroup.objects.create(name="Teachers")

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

        # Create a regular user
        self.user = Member.objects.create_user(
            username="user",
            email="user@example.com",
            first_name="Regular",
            last_name="User",
            password="password",
            is_staff=True,
        )

    def test_member_is_student(self):
        """Test that Member.is_student returns the correct result."""
        # The student should be a student
        self.assertTrue(self.student.is_student)

        # The teacher should not be a student
        self.assertFalse(self.teacher.is_student)

        # The regular user should not be a student
        self.assertFalse(self.user.is_student)

    def test_member_is_teacher(self):
        """Test that Member.is_teacher returns the correct result."""
        # The student should not be a teacher
        self.assertFalse(self.student.is_teacher)

        # The teacher should be a teacher
        self.assertTrue(self.teacher.is_teacher)

        # The regular user should not be a teacher
        self.assertFalse(self.user.is_teacher)
