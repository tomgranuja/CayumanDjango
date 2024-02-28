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


def test_member_can_be_student(create_user, create_groups):
    user = create_user
    student_group, _ = create_groups
    user.groups.add(student_group)
    assert user.is_student
    assert not user.is_teacher


def test_member_can_be_teacher(create_user, create_groups):
    user = create_user
    _, teacher_group = create_groups
    user.groups.add(teacher_group)
    assert user.is_teacher
    assert not user.is_student


def test_member_cannot_be_both_student_and_teacher(create_user, create_groups):
    student_group, teacher_group = create_groups
    user = create_user
    with pytest.raises(ValidationError, match="User must not be both Student and Teacher"):
        user.groups.add(student_group, teacher_group)


def test_member_cannot_be_student_and_staff(create_user, create_groups):
    student_group, _ = create_groups
    user = create_user
    user.is_staff = True
    user.save()
    user.groups.clear()
    with pytest.raises(ValidationError, match="Student cannot be staff member"):
        user.groups.add(student_group)


def test_member_can_be_staff_only(create_user):
    user = create_user
    user.is_staff = True
    user.save()  # No ValidationError expected
    assert not user.is_student
    assert not user.is_teacher
    assert user.is_staff
