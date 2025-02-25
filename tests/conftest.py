from datetime import datetime
from unittest.mock import Mock

import pytest
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.models import Group
from django.contrib.messages.storage.base import BaseStorage
from django.utils import timezone

from cayuman.middleware import CayumanMiddleware
from cayuman.models import Cycle
from cayuman.models import Member
from cayuman.models import Period
from cayuman.models import StudentCycle
from cayuman.models import Workshop


class MockMessageStorage(BaseStorage):
    """Mock storage class for messages framework"""

    def __init__(self, request, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        self._messages = []

    def _get(self, *args, **kwargs):
        return self._messages, True

    def _store(self, messages, response, *args, **kwargs):
        self._messages = messages
        return []

    def add(self, level, message, extra_tags=""):
        self._messages.append(message)


class MockRequest:
    """Custom request class for testing middleware"""

    def __init__(self):
        self.user = AnonymousUser()
        self.path_info = "/"
        self._attrs = {}
        self.META = {}
        self._messages = MockMessageStorage(self)
        self.session = {}

    def __getattr__(self, name):
        if name == "period" and name not in self._attrs:
            raise AttributeError(f"'MockRequest' object has no attribute '{name}'")
        return self._attrs.get(name)

    def __setattr__(self, name, value):
        if name in ("user", "path_info", "_attrs", "META", "_messages", "session"):
            super().__setattr__(name, value)
        else:
            self._attrs[name] = value


@pytest.fixture
def mock_request():
    """Create a mock request object with basic attributes"""
    request = MockRequest()
    return request


@pytest.fixture
def middleware():
    """Create middleware instance with mock get_response"""
    get_response = Mock(return_value="response")
    return CayumanMiddleware(get_response)


@pytest.fixture
def create_period(request):
    """
    Create a test period with configurable dates.

    Can be used in two ways:
    1. Without parameters - uses default dates
    2. With parameters via indirect parametrization, e.g.:
       @pytest.mark.parametrize('create_period', [{
           'preview_date': '2024-01-01',
           'enrollment_start': '2024-01-03',
           'enrollment_end': '2024-01-10',
           'date_start': '2024-01-15',
           'date_end': '2024-02-15'
       }], indirect=True)
    """
    # Default dates
    default_dates = {
        "preview_date": timezone.make_aware(datetime(2025, 4, 17)).date(),
        "enrollment_start": timezone.make_aware(datetime(2025, 4, 19)),
        "enrollment_end": timezone.make_aware(datetime(2025, 4, 26)).date(),
        "date_start": timezone.make_aware(datetime(2025, 5, 4)).date(),
        "date_end": timezone.make_aware(datetime(2025, 6, 15)).date(),
    }

    # If the fixture is parametrized, use those dates
    if hasattr(request, "param"):
        dates = request.param
        # Convert string dates to datetime objects if needed
        for key, value in dates.items():
            if isinstance(value, str):
                dt = datetime.strptime(value, "%Y-%m-%d")
                dates[key] = timezone.make_aware(dt).date() if key != "enrollment_start" else timezone.make_aware(dt)
    else:
        dates = default_dates

    period = Period.objects.create(
        name="Test Period",
        preview_date=dates["preview_date"],
        enrollment_start=dates["enrollment_start"],
        enrollment_end=dates["enrollment_end"],
        date_start=dates["date_start"],
        date_end=dates["date_end"],
    )

    # Mock current_or_last to return this period by default
    Period.objects.current_or_last = Mock(return_value=period)
    # Mock is_in_the_past to return True by default for testing messages
    period.is_in_the_past = Mock(return_value=True)

    return period


@pytest.fixture
def create_cycle():
    """Create a test cycle"""
    return Cycle.objects.create(name="Test Cycle")


@pytest.fixture
def create_groups():
    """Create student and teacher groups"""
    students_group, _ = Group.objects.get_or_create(name=settings.STUDENTS_GROUP)
    teachers_group, _ = Group.objects.get_or_create(name=settings.TEACHERS_GROUP)
    return students_group, teachers_group


@pytest.fixture
def create_superuser():
    """Create a superuser for testing"""
    return Member.objects.create_superuser(username="admin", password="admin123", email="admin@test.com", first_name="Admin", last_name="User")


@pytest.fixture
def create_staff():
    """Create a staff user (non-superuser) for testing"""
    user = Member.objects.create_user(
        username="staff", password="staff123", email="staff@test.com", first_name="Staff", last_name="User", is_staff=True
    )
    return user


@pytest.fixture
def create_student(create_groups):
    """Create a student user for testing"""
    students_group, _ = create_groups
    user = Member.objects.create_user(username="student", password="student123", email="student@test.com", first_name="Student", last_name="User")
    user.groups.add(students_group)
    return user


@pytest.fixture
def create_teacher(create_groups):
    """Create a teacher user for testing"""
    _, teachers_group = create_groups
    user = Member.objects.create_user(username="teacher", password="teacher123", email="teacher@test.com", first_name="Teacher", last_name="User")
    user.groups.add(teachers_group)
    return user


@pytest.fixture
def create_inactive_user():
    """Create an inactive user for testing"""
    return Member.objects.create_user(
        username="inactive", password="inactive123", email="inactive@test.com", first_name="Inactive", last_name="User", is_active=False
    )


@pytest.fixture(autouse=True)
def create_student_cycle(create_student, create_cycle):
    """Create a test student cycle. This is used automatically for all tests."""
    return StudentCycle.objects.create(student=create_student, cycle=create_cycle)


@pytest.fixture
def client_authenticated_superuser(client, create_superuser):
    """Client authenticated as superuser"""
    client.force_login(create_superuser)
    return client


@pytest.fixture
def client_authenticated_staff(client, create_staff):
    """Client authenticated as staff"""
    client.force_login(create_staff)
    return client


@pytest.fixture
def client_authenticated_teacher(client, create_teacher):
    """Client authenticated as teacher"""
    client.force_login(create_teacher)
    return client


@pytest.fixture
def client_authenticated_student(client, create_student):
    """Client authenticated as student"""
    client.force_login(create_student)
    return client


@pytest.fixture(autouse=True)
def create_test_period():
    """Create a test period that will be used for all tests"""
    period = Period.objects.create(
        name="Test Period",
        preview_date=timezone.make_aware(datetime(2025, 7, 17)).date(),
        enrollment_start=timezone.make_aware(datetime(2025, 7, 19)),
        enrollment_end=timezone.make_aware(datetime(2025, 7, 26)).date(),
        date_start=timezone.make_aware(datetime(2025, 8, 4)).date(),
        date_end=timezone.make_aware(datetime(2025, 9, 15)).date(),
    )

    # Mock current_or_last to return this period by default
    Period.objects.current_or_last = Mock(return_value=period)
    # Mock is_in_the_past to return True by default for testing messages
    period.is_in_the_past = Mock(return_value=True)
    # Mock is_enabled_to_preview to return True by default
    period.is_enabled_to_preview = Mock(return_value=True)

    return period


@pytest.fixture
def create_workshops():
    """Fixture to create sample Workshops"""
    # Workshops
    for name in ("Fractangulos", "Comics", "Ingles"):
        Workshop.objects.create(name=name)
    return Workshop.objects.all()


@pytest.fixture
def create_cycles():
    """Fixture to create sample Cycles"""
    for name in ("Avellanos", "Ulmos", "Canelos"):
        Cycle.objects.create(name=name)
    return Cycle.objects.all()


def pytest_runtest_setup(item):
    # setup code here - runs before each test
    pass


def pytest_configure():
    """Set language to English for tests"""
    settings.LANGUAGE_CODE = "en"
