from datetime import datetime
from datetime import time
from unittest.mock import Mock

import pytest
from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory
from django.utils import timezone

from cayuman.middleware import CayumanMiddleware
from cayuman.models import Cycle
from cayuman.models import Member
from cayuman.models import Period
from cayuman.models import Schedule


def pytest_configure():
    """Set language to English for tests"""
    settings.LANGUAGE_CODE = "en"


@pytest.fixture
def create_schedule():
    time_start = time(10, 15)
    time_end = time(11, 15)
    return Schedule.objects.create(day="Monday", time_start=time_start, time_end=time_end)


@pytest.fixture(autouse=True)
def middleware():
    """Create middleware instance with mock get_response"""
    get_response = Mock(return_value="response")
    return CayumanMiddleware(get_response)


@pytest.fixture
def mock_request():
    """Create a request object with session and message support for testing middleware"""
    factory = RequestFactory()
    request = factory.get("/")
    request.user = Mock(is_authenticated=False, is_active=True, is_impersonate=False, _impersonate=None)
    request.impersonator = None

    # Add session
    session_middleware = SessionMiddleware(lambda req: None)
    session_middleware.process_request(request)
    request.session.save()

    # Add messages
    messages_middleware = MessageMiddleware(lambda req: None)
    messages_middleware.process_request(request)
    request._messages = FallbackStorage(request)

    return request


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
def create_superuser():
    """Create a superuser for testing"""
    return Member.objects.create_superuser(username="admin", password="admin123", email="admin@test.com", first_name="Admin", last_name="User")


@pytest.fixture
def create_groups():
    """Create student and teacher groups"""
    students_group, _ = Group.objects.get_or_create(name=settings.STUDENTS_GROUP)
    teachers_group, _ = Group.objects.get_or_create(name=settings.TEACHERS_GROUP)
    return students_group, teachers_group


@pytest.fixture
def create_staff():
    """Create a staff user (non-superuser) for testing"""
    user = Member.objects.create_user(
        username="staff", password="staff123", email="staff@test.com", first_name="Staff", last_name="User", is_staff=True
    )
    return user


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


@pytest.fixture
def create_workshops():
    """Fixture to create sample Workshops"""
    from cayuman.models import Workshop

    for name in ("Fractangulos", "Comics", "Ingles"):
        Workshop.objects.create(name=name)
    return Workshop.objects.all()


@pytest.fixture
def create_cycles():
    for name in ("Avellanos", "Ulmos", "Canelos"):
        Cycle.objects.create(name=name)
    return Cycle.objects.all()


@pytest.fixture
def create_user():
    # Create a basic user
    user = Member.objects.create_user(username="11111111", password="12345", first_name="test", last_name="user")
    return user
