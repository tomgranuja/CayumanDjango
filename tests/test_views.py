import functools
import random
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
            with patch("cayuman.models.timezone") as mock_datetime:
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
        name="Period 1",
        preview_date=timezone.make_aware(datetime(2024, 4, 17)).date(),
        enrollment_start=timezone.make_aware(datetime(2024, 4, 19)),
        enrollment_end=timezone.make_aware(datetime(2024, 4, 26)).date(),
        date_start=timezone.make_aware(datetime(2024, 5, 4)).date(),
        date_end=timezone.make_aware(datetime(2024, 6, 15)).date(),
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


parameterized_tests = {
    # anon redirected to login
    "0": (reverse("home"), datetime(2024, 1, 1), None, None, None, False, 302, reverse("login") + "?next=/", [], []),
    # teacher redirected to admin login
    "0-2": (reverse("home"), datetime(2024, 1, 1), "client_authenticated_teacher", None, None, False, 302, reverse("admin:login"), [], []),
    # student redirected to workshop_periods when no full schedule and before preview_date
    "1": (
        reverse("home"),
        datetime(2024, 4, 16),  # before preview_date
        "client_authenticated_student",
        "create_workshop_period",
        None,
        False,
        302,
        reverse("workshop_periods", kwargs={"period_id": 1}),
        [],
        [],
    ),
    # student without student cycle gets warning when no associated StudentCycle
    "2": (
        reverse("workshop_periods", kwargs={"period_id": 1}),
        datetime(2024, 4, 18),  # between preview_date and enrollment_start
        "client_authenticated_student",
        "create_workshop_period",
        None,
        False,
        200,
        None,
        ["Hello", "Your student account is not associated with any Cycle"],
        ["Fill up the following form choosing one workshop", "Click here to enroll in your workshops"],
    ),
    # student with student cycle get list of workshops, no enrollment button when after preview_date and before enrollment_start
    "3": (
        reverse("workshop_periods", kwargs={"period_id": 1}),
        datetime(2024, 4, 18),  # between preview_date and enrollment_start
        "client_authenticated_student",
        "create_workshop_period",
        "create_student_cycle",
        False,
        200,
        None,
        ["Hello"],
        [
            "No workshops available for this period",
            "Fill up the following form choosing one workshop",
            "Click here to enroll in your workshops",
            "Your student account is not associated with any Cycle",
        ],
    ),
    # student gets list of workshops and enrollment button if no full schedule and after enrollment_start
    "4": (
        reverse("workshop_periods", kwargs={"period_id": 1}),
        datetime(2024, 4, 20),  # after enrollment_start
        "client_authenticated_student",
        "create_workshop_period",
        "create_student_cycle",
        False,  # no full schedule
        200,
        None,
        ["Hello", "Click here to enroll in your workshops", "card-title mb-2 text-body-primar"],
        ["Your student account is not associated with any Cycle"],
    ),
    # student with full schedule is redirected to weekly-schedule when visiting home
    "5": (
        reverse("home"),
        datetime(2024, 4, 20),
        "client_authenticated_student",
        "create_workshop_period",
        "create_student_cycle",
        True,  # with full schedule
        302,
        reverse("weekly_schedule", kwargs={"period_id": 1}),
        [],
        [],
    ),
    # student without workshops gets list of workshops and enrollment button even after enrollment_end and before date_start
    "6": (
        reverse("workshop_periods", kwargs={"period_id": 1}),
        datetime(2024, 4, 27),  # after enrollment_end
        "client_authenticated_student",
        "create_workshop_period",
        "create_student_cycle",
        False,  # no full schedule
        200,
        None,
        ["Hello", "Click here to enroll in your workshops"],
        ["Your student account is not associated with any Cycle"],
    ),
    # student with full schedule redirected to weekly-schedule after enrollment end
    "7": (
        reverse("home"),
        datetime(2024, 4, 27),  # after enrollment end
        "client_authenticated_student",
        "create_workshop_period",
        "create_student_cycle",
        True,
        302,
        reverse("weekly_schedule", kwargs={"period_id": 1}),
        [],
        [],
    ),
    # student without full schedule is allowed into workshop periods even after date_start
    "8": (
        reverse("workshop_periods", kwargs={"period_id": 1}),
        datetime(2024, 5, 10),  # after date_start
        "client_authenticated_student",
        "create_workshop_period",
        "create_student_cycle",
        False,
        200,
        None,
        ["Hello", "Click here to enroll in your workshops"],
        ["Your student account is not associated with any Cycle"],
    ),
    # student is redirected to weekly schedule if full schedule after date_start
    "9": (
        reverse("home"),
        datetime(2024, 5, 10),  # after date_start
        "client_authenticated_student",
        "create_workshop_period",
        "create_student_cycle",
        True,
        302,
        reverse("weekly_schedule", kwargs={"period_id": 1}),
        [],
        [],
    ),
    # student shown workshops and enrollment button if full schedule and between enrollment_start and enrollment_end
    # i.e. chosen workshop periods can be changed by the student until date_start
    "10": (
        reverse("workshop_periods", kwargs={"period_id": 1}),
        datetime(2024, 4, 20),  # between enrollment_start and enrollment_end
        "client_authenticated_student",
        "create_workshop_period",
        "create_student_cycle",
        True,
        200,
        None,
        ["Hello", "Click here to enroll in your workshops"],
        ["Your student account is not associated with any Cycle"],
    ),
    # student without full schedule is allowed to change their workshops even after date_start
    "11": (
        reverse("weekly_schedule", kwargs={"period_id": 1}),
        datetime(2024, 5, 10),  # after date_start
        "client_authenticated_student",
        "create_workshop_period",
        "create_student_cycle",
        False,
        200,
        None,
        ["Weekly Workshop Schedule", "Click here to enroll in your workshops"],
        ["If you need to change your workshops"],
    ),
    # student with full schedule cannot change workshops after date_start
    "12": (
        reverse("weekly_schedule", kwargs={"period_id": 1}),
        datetime(2024, 5, 10),  # after date_start
        "client_authenticated_student",
        "create_workshop_period",
        "create_student_cycle",
        True,
        200,
        None,
        ["Weekly Workshop Schedule", "If you need to change your workshops"],
        ["Change my Workshops"],
    ),
    # student without full schedule is sent to weekly-schedule before preview_date
    "13": (
        reverse("enrollment", kwargs={"period_id": 1}),
        datetime(2024, 4, 16),  # before preview_date
        "client_authenticated_student",
        "create_workshop_period",
        "create_student_cycle",
        False,
        302,
        reverse("workshop_periods", kwargs={"period_id": 1}),
        [],
        [],
    ),
    # student with full schedule sent to weekly-schedule before preview_date (this case shouldn't happen)
    "14": (
        reverse("enrollment", kwargs={"period_id": 1}),
        datetime(2024, 4, 16),  # before preview_date
        "client_authenticated_student",
        "create_workshop_period",
        "create_student_cycle",
        True,
        302,
        reverse("workshop_periods", kwargs={"period_id": 1}),
        [],
        [],
    ),
    # student redirected to weekly-schedule before enrollment_start
    "15": (
        reverse("enrollment", kwargs={"period_id": 1}),
        datetime(2024, 4, 18),  # before enrollment_start
        "client_authenticated_student",
        "create_workshop_period",
        "create_student_cycle",
        False,
        302,
        reverse("workshop_periods", kwargs={"period_id": 1}),
        [],
        [],
    ),
    # student redirected to weekly-schedule if full_schedule and before enrollment_start (this shouldn't happen)
    "16": (
        reverse("enrollment", kwargs={"period_id": 1}),
        datetime(2024, 4, 18),
        "client_authenticated_student",
        "create_workshop_period",
        "create_student_cycle",
        True,
        302,
        reverse("workshop_periods", kwargs={"period_id": 1}),
        [],
        [],
    ),
    # student without full schedule is shown enrollment form after enrollment_start
    "17": (
        reverse("enrollment", kwargs={"period_id": 1}),
        datetime(2024, 4, 20),  # after enrollment_start
        "client_authenticated_student",
        "create_workshop_period",
        "create_student_cycle",
        False,  # no full schedule
        200,
        None,
        ["Fill up the following form choosing one workshop"],
        ["No enrollment available at this time"],
    ),
    # student without full schedule is shown enrollment form even after date_start
    "18": (
        reverse("enrollment", kwargs={"period_id": 1}),
        datetime(2024, 5, 10),  # after date_start
        "client_authenticated_student",
        "create_workshop_period",
        "create_student_cycle",
        False,
        200,
        None,
        ["Fill up the following form choosing one workshop"],
        ["No enrollment available at this time"],
    ),
    # student with full schedule redirected to weekly-schedule after date_start
    "19": (
        reverse("enrollment", kwargs={"period_id": 1}),
        datetime(2024, 5, 10),  # after date_start
        "client_authenticated_student",
        "create_workshop_period",
        "create_student_cycle",
        True,
        302,
        reverse("weekly_schedule", kwargs={"period_id": 1}),
        [],
        [],
    ),
    # student without student cycle is sent to workshop_periods after date_start
    "20": (
        reverse("enrollment", kwargs={"period_id": 1}),
        datetime(2024, 5, 10),  # after date_start
        "client_authenticated_student",
        "create_workshop_period",
        None,
        False,
        302,
        reverse("workshop_periods", kwargs={"period_id": 1}),
        [],
        [],
    ),
    # student without studentcycle is shown warning workshops are not yet visible before preview_date
    "21": (
        reverse("workshop_periods", kwargs={"period_id": 1}),
        datetime(2024, 4, 16),  # before preview_date
        "client_authenticated_student",
        "create_workshop_period",
        None,
        False,
        200,
        None,
        ["Hello", "The period you are viewing is not yet open", "Your student account is not associated with any Cycle"],
        ["Fill up the following form choosing one workshop", "Click here to enroll in your workshops"],
    ),
    # student with studentcycle is shown warning workshops are not yet visible before preview_date
    "22": (
        reverse("workshop_periods", kwargs={"period_id": 1}),
        datetime(2024, 4, 16),  # before preview_date
        "client_authenticated_student",
        "create_workshop_period",
        "create_student_cycle",
        False,
        200,
        None,
        ["Hello", "The period you are viewing is not yet open"],
        [
            "Your student account is not associated with any Cycle",
            "Fill up the following form choosing one workshop",
            "Click here to enroll in your workshops",
        ],
    ),
}


@pytest.mark.parametrize(
    (
        "url, current_date, member_session, workshop_period, student_cycle, "
        "assign_student_cycle_workshop_period, status_code, redirect_url, wanted_words, unwanted_words"
    ),
    list(parameterized_tests.values()),
    ids=list(parameterized_tests.keys()),
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

    with patch("cayuman.models.timezone") as mock_datetime:
        # Set the mocked datetime
        mock_datetime.now.return_value = timezone.make_aware(datetime(current_date.year, current_date.month, current_date.day))
        mock_datetime.now.date.return_value = timezone.make_aware(current_date).date()

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
