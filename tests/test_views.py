import functools
import random
from datetime import date
from datetime import datetime
from datetime import time
from unittest.mock import patch

import pytest
from django.conf import settings
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils import timezone

from cayuman.models import Cycle
from cayuman.models import Member
from cayuman.models import Period
from cayuman.models import Schedule
from cayuman.models import StudentCycle
from cayuman.models import Workshop
from cayuman.models import WorkshopPeriod


pytestmark = pytest.mark.django_db


def mock_date(given_date):
    """Decorator to easily force a date over a test function"""

    def decorator(test_func):
        @functools.wraps(test_func)
        def wrapper(*args, **kwargs):
            # Clear the cache before running the test
            Period.objects.current.cache_clear()
            with patch("cayuman.models.datetime") as mock_datetime:
                # Set the mocked datetime
                mock_datetime.now.return_value = datetime(given_date.year, given_date.month, given_date.day)
                mock_datetime.now.date.return_value = given_date

                return test_func(*args, **kwargs)

        return wrapper

    return decorator


def random_date_between(date1, date2):
    """
    Returns a random date between two given dates, inclusive.

    Args:
    date1 (date): The first date.
    date2 (date): The second date.

    Returns:
    date: A random date between date1 and date2, inclusive.
    """
    start_date = min(date1, date2)
    end_date = max(date1, date2)
    delta_days = (end_date - start_date).days
    random_days = random.randint(0, delta_days)
    return start_date + timezone.timedelta(days=random_days)


@pytest.fixture
def create_groups(autouse=True):
    # Create student and teacher groups
    students_group, _ = Group.objects.get_or_create(name=settings.STUDENTS_GROUP)
    teachers_group, _ = Group.objects.get_or_create(name=settings.TEACHERS_GROUP)
    return students_group, teachers_group  # Groups are available to the test function


@pytest.fixture(autouse=True)
def create_student(create_groups):
    students_group, _ = create_groups
    user = Member.objects.create_user(username="11111111", password="12345", first_name="student", last_name="lopez")
    user.groups.add(students_group)
    return user


@pytest.fixture(autouse=True)
def create_teacher(create_groups):
    _, teachers_group = create_groups
    user = Member.objects.create_user(username="22222222", password="67890", first_name="teacher", last_name="gonzalez")
    user.groups.add(teachers_group)
    return user


@pytest.fixture(autouse=True)
def create_period():
    return Period.objects.create(
        name="Period X",
        preview_date=date(2024, 4, 17),
        enrollment_start=date(2024, 4, 19),
        enrollment_end=date(2024, 4, 26),
        date_start=date(2024, 5, 4),
        date_end=date(2024, 6, 15),
    )


@pytest.fixture(autouse=True)
def create_schedule():
    time_start = time(10, 15)
    time_end = time(11, 15)
    return Schedule.objects.create(day="Monday", time_start=time_start, time_end=time_end)


@pytest.fixture(autouse=True)
def create_cycle():
    return Cycle.objects.create(name="Cycle 1")


@pytest.fixture(autouse=True)
def create_workshop():
    return Workshop.objects.create(name="Fractangulos")


@pytest.fixture
def create_workshop_period(create_workshop, create_period, create_teacher, create_schedule, create_cycle):
    wp = WorkshopPeriod.objects.create(workshop=create_workshop, period=create_period, teacher=create_teacher)
    wp.cycles.add(create_cycle)
    wp.schedules.add(create_schedule)
    return wp


@pytest.fixture
def create_student_cycle(create_student, create_cycle, create_workshop_period):
    sc = StudentCycle.objects.create(student=create_student, cycle=create_cycle)
    # sc.workshop_periods.add(create_workshop_period)
    return sc


@pytest.fixture
def client_authenticated_student(client, create_student):
    client.force_login(create_student)
    return client


@pytest.fixture
def client_authenticated_teacher(client, create_teacher):
    client.force_login(create_teacher)
    return client


@pytest.mark.parametrize(
    (
        "url, current_date, member_session, workshop_period, student_cycle, "
        "assign_student_cycle_workshop_period, status_code, redirect_url, wanted_words, unwanted_words"
    ),
    [
        # home
        (reverse("home"), date(2024, 1, 1), None, None, None, False, 302, reverse("login") + "?next=/", [], []),
        (reverse("home"), date(2024, 1, 1), "client_authenticated_teacher", None, None, False, 302, reverse("admin:login"), [], []),
        (
            reverse("home"),
            date(2024, 4, 16),
            "client_authenticated_student",
            "create_workshop_period",
            None,
            False,
            200,
            None,
            ["Hello", "It is still not the time to visualize workshops for the upcoming period"],
            ["Your student account is not associated with any Cycle", "These are the workshop options for", "Click here to enroll in your workshops"],
        ),
        (
            reverse("home"),
            date(2024, 4, 18),
            "client_authenticated_student",
            "create_workshop_period",
            None,
            False,
            200,
            None,
            ["Hello", "Your student account is not associated with any Cycle"],
            ["These are the workshop options for", "Click here to enroll in your workshops"],
        ),
        (
            reverse("home"),
            date(2024, 4, 18),
            "client_authenticated_student",
            "create_workshop_period",
            "create_student_cycle",
            False,
            200,
            None,
            ["Hello", "These are the workshop options for"],
            ["Click here to enroll in your workshops", "Your student account is not associated with any Cycle"],
        ),
        (
            reverse("home"),
            date(2024, 4, 20),
            "client_authenticated_student",
            "create_workshop_period",
            "create_student_cycle",
            False,
            200,
            None,
            ["Hello", "These are the workshop options for", "Click here to enroll in your workshops"],
            ["Your student account is not associated with any Cycle"],
        ),
        (
            reverse("home"),
            date(2024, 4, 20),
            "client_authenticated_student",
            "create_workshop_period",
            "create_student_cycle",
            True,
            302,
            reverse("weekly_schedule"),
            [],
            [],
        ),
        (
            reverse("home"),
            date(2024, 4, 27),
            "client_authenticated_student",
            "create_workshop_period",
            "create_student_cycle",
            False,
            200,
            None,
            ["Hello", "These are the workshop options for", "Click here to enroll in your workshops"],
            ["Your student account is not associated with any Cycle"],
        ),
        (
            reverse("home"),
            date(2024, 4, 27),
            "client_authenticated_student",
            "create_workshop_period",
            "create_student_cycle",
            True,
            302,
            reverse("weekly_schedule"),
            [],
            [],
        ),
        (
            reverse("home"),
            date(2024, 5, 10),
            "client_authenticated_student",
            "create_workshop_period",
            "create_student_cycle",
            False,
            200,
            None,
            ["Hello", "These are the workshop options for", "Click here to enroll in your workshops"],
            ["Your student account is not associated with any Cycle"],
        ),
        (
            reverse("home"),
            date(2024, 5, 10),
            "client_authenticated_student",
            "create_workshop_period",
            "create_student_cycle",
            True,
            302,
            reverse("weekly_schedule"),
            [],
            [],
        ),
        # home?force=true
        (
            reverse("home") + "?force=true",
            date(2024, 4, 20),
            "client_authenticated_student",
            "create_workshop_period",
            "create_student_cycle",
            True,
            200,
            None,
            ["Hello", "These are the workshop options for", "Click here to enroll in your workshops"],
            ["Your student account is not associated with any Cycle"],
        ),
        # weekly-schedule
        (
            reverse("weekly_schedule"),
            date(2024, 5, 10),
            "client_authenticated_student",
            "create_workshop_period",
            "create_student_cycle",
            False,
            200,
            None,
            ["Weekly Workshop Schedule", "Change my Workshops"],
            ["If you need to change your workshops"],
        ),
        (
            reverse("weekly_schedule"),
            date(2024, 5, 10),
            "client_authenticated_student",
            "create_workshop_period",
            "create_student_cycle",
            True,
            200,
            None,
            ["Weekly Workshop Schedule", "If you need to change your workshops"],
            ["Change my Workshops"],
        ),
        # enrollment
        (
            reverse("enrollment"),
            date(2024, 4, 16),
            "client_authenticated_student",
            "create_workshop_period",
            "create_student_cycle",
            False,
            302,
            reverse("weekly_schedule"),
            [],
            [],
        ),
        (
            reverse("enrollment"),
            date(2024, 4, 16),
            "client_authenticated_student",
            "create_workshop_period",
            "create_student_cycle",
            True,
            302,
            reverse("weekly_schedule"),
            [],
            [],
        ),
        (
            reverse("enrollment"),
            date(2024, 4, 18),
            "client_authenticated_student",
            "create_workshop_period",
            "create_student_cycle",
            False,
            302,
            reverse("weekly_schedule"),
            [],
            [],
        ),
        (
            reverse("enrollment"),
            date(2024, 4, 18),
            "client_authenticated_student",
            "create_workshop_period",
            "create_student_cycle",
            True,
            302,
            reverse("weekly_schedule"),
            [],
            [],
        ),
        (
            reverse("enrollment"),
            date(2024, 4, 20),
            "client_authenticated_student",
            "create_workshop_period",
            "create_student_cycle",
            False,
            200,
            None,
            ["These are the available workshops"],
            ["No enrollment available at this time"],
        ),
        (
            reverse("enrollment"),
            date(2024, 5, 10),
            "client_authenticated_student",
            "create_workshop_period",
            "create_student_cycle",
            False,
            200,
            None,
            ["These are the available workshops"],
            ["No enrollment available at this time"],
        ),
        (
            reverse("enrollment"),
            date(2024, 5, 10),
            "client_authenticated_student",
            "create_workshop_period",
            "create_student_cycle",
            True,
            302,
            reverse("weekly_schedule"),
            [],
            [],
        ),
    ],
    ids=[
        "home-anon-user",
        "home-teacher-user",
        "home-student-user-before-preview",
        "home-student-user-after-preview-no-student_cycle",
        "home-student-user-after-preview-with-student_cycle",
        "home-student-user-after-enrollment_start",
        "home-student-user-after-enrollment_start-with-student_cycle-workshop_period",
        "home-student-user-after-enrollment_end-no-student_cycle-workshop_period",
        "home-student-user-after-enrollment_end-with-student_cycle-workshop_period",
        "home-student-user-after-date_start-no-student_cycle-workshop_period",
        "home-student-user-after-date_start-with-student_cycle-workshop_period",
        "home-force-student-user-after-enrollment_start-with-student_cycle-workshop_period",
        "weekly_schedule-student-user-after-date_start-no-student_cycle-workshop_period",
        "weekly_schedule-student-user-after-date_start-with-student_cycle-workshop_period",
        "enrollment-student-user-before-preview-no-student_cycle-workshop_period",
        "enrollment-student-user-before-preview-with-student_cycle-workshop_period",
        "enrollment-student-user-before-enrollment_start-no-student_cycle-workshop_period",
        "enrollment-student-user-before-enrollment_start-with-student_cycle-workshop_period",
        "enrollment-student-user-after-enrollment_start-no-student_cycle-workshop_period",
        "enrollment-student-user-after-date_start-no-student_cycle-workshop_period",
        "enrollment-student-user-after-date_start-with-student_cycle-workshop_period",
    ],
)
def test_url(
    request,
    client,
    url,
    current_date,
    member_session,
    workshop_period,
    student_cycle,
    assign_student_cycle_workshop_period,
    status_code,
    redirect_url,
    wanted_words,
    unwanted_words,
):
    """Tests flows for different types of users and their conditions when visiting a given url"""
    if member_session:
        member_session = request.getfixturevalue(member_session)
    else:
        member_session = client
    if workshop_period:
        workshop_period = request.getfixturevalue(workshop_period)
    if student_cycle:
        student_cycle = request.getfixturevalue(student_cycle)
    if assign_student_cycle_workshop_period:
        student_cycle.workshop_periods.add(workshop_period)

    Period.objects.current.cache_clear()
    with patch("cayuman.models.datetime") as mock_datetime:
        # Set the mocked datetime
        mock_datetime.now.return_value = datetime(current_date.year, current_date.month, current_date.day)
        mock_datetime.now.date.return_value = current_date

        response = member_session.get(url)
        assert response.status_code == status_code
        if redirect_url:
            assert response.url == redirect_url
        if wanted_words:
            for words in wanted_words:
                assert words in response.content.decode()
        if unwanted_words:
            for words in unwanted_words:
                assert words not in response.content.decode()

    # clean up
    if assign_student_cycle_workshop_period:
        student_cycle.workshop_periods.clear()
