import pytest
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError

from cayuman.models import Member

pytestmark = pytest.mark.django_db


@pytest.fixture
def create_user():
    # Create a basic user
    user = Member.objects.create_user(username="11111111", password="12345", first_name="test", last_name="user")
    return user


@pytest.fixture
def create_groups():
    # Create student and teacher groups
    students_group, _ = Group.objects.get_or_create(name=settings.STUDENTS_GROUP)
    teachers_group, _ = Group.objects.get_or_create(name=settings.TEACHERS_GROUP)
    return students_group, teachers_group  # Groups are available to the test function


def test_member_can_be_student(request):
    """Test that a member can be a student"""
    user = Member.objects.create_user(username="99999999", password="12345")
    request.node.user = user
    group, _ = Group.objects.get_or_create(name=settings.STUDENTS_GROUP)
    user.groups.add(group)
    assert user.is_student is True
    assert user.is_teacher is False


def test_member_can_be_teacher(request):
    """Test that a member can be a teacher"""
    user = Member.objects.create_user(username="99999999", password="12345")
    request.node.user = user
    group, _ = Group.objects.get_or_create(name=settings.TEACHERS_GROUP)
    user.groups.add(group)
    assert user.is_student is False
    assert user.is_teacher is True


def test_member_cannot_be_both_student_and_teacher(request):
    """Test that a member cannot be both student and teacher"""
    user = Member.objects.create_user(username="99999999", password="12345")
    request.node.user = user
    students_group, _ = Group.objects.get_or_create(name=settings.STUDENTS_GROUP)
    teachers_group, _ = Group.objects.get_or_create(name=settings.TEACHERS_GROUP)
    user.groups.add(students_group)
    with pytest.raises(ValidationError, match=r"User must not be both Student and Teacher"):
        user.groups.add(teachers_group)


def test_member_cannot_be_student_and_staff(request):
    """Test that a member cannot be both student and staff"""
    user = Member.objects.create_user(username="99999999", password="12345", is_staff=True)
    request.node.user = user
    students_group, _ = Group.objects.get_or_create(name=settings.STUDENTS_GROUP)
    with pytest.raises(ValidationError, match=r"Student cannot be staff member"):
        user.groups.add(students_group)


def test_member_can_be_staff_only(request):
    """Test that a member can be staff only"""
    user = Member.objects.create_user(username="99999999", password="12345", is_staff=True)
    request.node.user = user
    assert user.is_staff is True
    assert user.is_student is False
    assert user.is_teacher is False
