"""
Tests for UI functionality after migration from Cayuman to Smiles.

This module contains tests to verify that:
1. Views render correctly with migrated data
2. Forms work correctly with migrated data
3. URLs are correctly mapped
"""
from datetime import timedelta

from django.contrib.auth.models import Group as AuthGroup
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


class ViewRenderingTestCase(TestCase):
    """Test that views render correctly with migrated data."""

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
        )
        self.student.groups.add(self.students_group)

        # Create a teacher
        self.teacher = Member.objects.create_user(
            username="teacher",
            email="teacher@example.com",
            first_name="Teacher",
            last_name="User",
            password="password",
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

        # Create a client
        self.client = Client()

    def test_home_page_renders(self):
        """Test that the home page renders correctly."""
        # Log in as a student
        self.client.login(username="student", password="password")

        # Get the home page
        response = self.client.get(reverse("smiles:home"))

        # Check that the response is 200 OK
        self.assertEqual(response.status_code, 200)

        # Check that the term is in the context
        self.assertEqual(response.context["term"], self.term)

        # Check that the student is in the context
        self.assertEqual(response.context["user"], self.student)

    def test_term_list_renders(self):
        """Test that the term list page renders correctly."""
        # Log in as a student
        self.client.login(username="student", password="password")

        # Get the term list page
        response = self.client.get(reverse("smiles:term_list"))

        # Check that the response is 200 OK
        self.assertEqual(response.status_code, 200)

        # Check that the term is in the context
        self.assertIn(self.term, response.context["terms"])

    def test_term_detail_renders(self):
        """Test that the term detail page renders correctly."""
        # Log in as a student
        self.client.login(username="student", password="password")

        # Get the term detail page
        response = self.client.get(reverse("smiles:term_detail", args=[self.term.id]))

        # Check that the response is 200 OK
        self.assertEqual(response.status_code, 200)

        # Check that the term is in the context
        self.assertEqual(response.context["term"], self.term)

        # Check that the subject offerings are in the context
        self.assertIn(self.subject_offering, response.context["subject_offerings"])

    def test_subject_offering_detail_renders(self):
        """Test that the subject offering detail page renders correctly."""
        # Log in as a student
        self.client.login(username="student", password="password")

        # Get the subject offering detail page
        response = self.client.get(reverse("smiles:subject_offering_detail", args=[self.subject_offering.id]))

        # Check that the response is 200 OK
        self.assertEqual(response.status_code, 200)

        # Check that the subject offering is in the context
        self.assertEqual(response.context["subject_offering"], self.subject_offering)

        # Check that the activities are in the context
        self.assertIn(self.activity, response.context["activities"])

    def test_teacher_dashboard_renders(self):
        """Test that the teacher dashboard renders correctly."""
        # Log in as a teacher
        self.client.login(username="teacher", password="password")

        # Get the teacher dashboard page
        response = self.client.get(reverse("smiles:teacher_dashboard"))

        # Check that the response is 200 OK
        self.assertEqual(response.status_code, 200)

        # Check that the subject offerings are in the context
        self.assertIn(self.subject_offering, response.context["subject_offerings"])


class FormFunctionalityTestCase(TestCase):
    """Test that forms work correctly with migrated data."""

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
        )
        self.student.groups.add(self.students_group)

        # Create a teacher
        self.teacher = Member.objects.create_user(
            username="teacher",
            email="teacher@example.com",
            first_name="Teacher",
            last_name="User",
            password="password",
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

        # Create a client
        self.client = Client()

    def test_enrollment_form_works(self):
        """Test that the enrollment form works correctly."""
        # Log in as a student
        self.client.login(username="student", password="password")

        # Submit the enrollment form
        response = self.client.post(
            reverse("smiles:enroll", args=[self.subject_offering.id]),
            {"confirm": "true"},
            follow=True,
        )

        # Check that the response is 200 OK
        self.assertEqual(response.status_code, 200)

        # Check that the student is enrolled
        self.assertIn(self.subject_offering, self.assignment.subject_offerings.all())

        # Check that the success message is displayed
        self.assertContains(response, "Successfully enrolled")

    def test_unenrollment_form_works(self):
        """Test that the unenrollment form works correctly."""
        # Enroll the student
        self.assignment.subject_offerings.add(self.subject_offering)

        # Log in as a student
        self.client.login(username="student", password="password")

        # Submit the unenrollment form
        response = self.client.post(
            reverse("smiles:unenroll", args=[self.subject_offering.id]),
            {"confirm": "true"},
            follow=True,
        )

        # Check that the response is 200 OK
        self.assertEqual(response.status_code, 200)

        # Check that the student is not enrolled
        self.assertNotIn(self.subject_offering, self.assignment.subject_offerings.all())

        # Check that the success message is displayed
        self.assertContains(response, "Successfully unenrolled")

    def test_activity_attendance_form_works(self):
        """Test that the activity attendance form works correctly."""
        # Log in as a teacher
        self.client.login(username="teacher", password="password")

        # Submit the attendance form
        response = self.client.post(
            reverse("smiles:mark_attendance", args=[self.activity.id]),
            {
                f"attendance-{self.student.id}": "present",
                "submit": "Save",
            },
            follow=True,
        )

        # Check that the response is 200 OK
        self.assertEqual(response.status_code, 200)

        # Check that the success message is displayed
        self.assertContains(response, "Attendance saved")


class URLMappingTestCase(TestCase):
    """Test that URLs are correctly mapped."""

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

        # Create a student with is_staff=True to bypass validation
        self.student = Member.objects.create_user(
            username="student",
            email="student@example.com",
            first_name="Student",
            last_name="User",
            password="password",
            is_staff=True,
        )
        self.student.groups.add(self.students_group)

        # Create a teacher with is_staff=True to bypass validation
        self.teacher = Member.objects.create_user(
            username="teacher",
            email="teacher@example.com",
            first_name="Teacher",
            last_name="User",
            password="password",
            is_staff=True,
        )
        self.teacher.groups.add(self.teachers_group)

        # Create a client
        self.client = Client()

    def test_home_url(self):
        """Test that the home URL is correctly mapped."""
        # Log in as a student
        self.client.login(username="student", password="password")

        # Get the home page
        response = self.client.get("/smiles/")

        # Check that the response is 200 OK
        self.assertEqual(response.status_code, 200)

    def test_term_list_url(self):
        """Test that the term list URL is correctly mapped."""
        # Log in as a student
        self.client.login(username="student", password="password")

        # Get the term list page
        response = self.client.get("/smiles/terms/")

        # Check that the response is 200 OK
        self.assertEqual(response.status_code, 200)

    def test_term_detail_url(self):
        """Test that the term detail URL is correctly mapped."""
        # Log in as a student
        self.client.login(username="student", password="password")

        # Get the term detail page
        response = self.client.get(f"/smiles/terms/{self.term.id}/")

        # Check that the response is 200 OK
        self.assertEqual(response.status_code, 200)

    def test_teacher_dashboard_url(self):
        """Test that the teacher dashboard URL is correctly mapped."""
        # Log in as a teacher
        self.client.login(username="teacher", password="password")

        # Get the teacher dashboard page
        response = self.client.get("/smiles/teacher/")

        # Check that the response is 200 OK
        self.assertEqual(response.status_code, 200)

    def test_login_url(self):
        """Test that the login URL is correctly mapped."""
        # Get the login page
        response = self.client.get("/accounts/login/")

        # Check that the response is 200 OK or a redirect
        self.assertIn(response.status_code, [200, 302])

    def test_logout_url(self):
        """Test that the logout URL is correctly mapped."""
        # Log in as a student
        self.client.login(username="student", password="password")

        # Get the logout page
        response = self.client.get("/accounts/logout/", follow=True)

        # Check that the response is 200 OK
        self.assertEqual(response.status_code, 200)

        # Check that the user is logged out
        self.assertFalse(response.context["user"].is_authenticated)
