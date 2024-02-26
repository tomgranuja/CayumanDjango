import pytest
from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from cayuman.models import Member


pytestmark = pytest.mark.django_db


@pytest.fixture(scope="function")
def create_user():
    """Fixture to create a basic user."""
    yield User.objects.create_user(username="11111111", password="12345", first_name="test", last_name="user")
    User.objects.all().delete()


@pytest.fixture
def create_groups():
    """Fixture to create student and teacher groups."""
    students_group, _ = Group.objects.get_or_create(name=settings.STUDENTS_GROUP)
    teachers_group, _ = Group.objects.get_or_create(name=settings.TEACHERS_GROUP)
    return students_group, teachers_group


def test_member_can_be_student(create_user, create_groups):
    user = create_user
    student_group, _ = create_groups
    m = Member.objects.get(username=user.username)
    m.groups.add(student_group)
    assert m.is_student
    assert not m.is_teacher


def test_member_can_be_teacher(create_user, create_groups):
    user = create_user
    _, teacher_group = create_groups
    m = Member.objects.get(username=user.username)
    m.groups.add(teacher_group)
    assert m.is_teacher
    assert not m.is_student


def test_member_cannot_be_both_student_and_teacher(create_user, create_groups):
    student_group, teacher_group = create_groups
    user = create_user
    user.groups.add(student_group, teacher_group)
    m = Member.objects.get(username=user.username)
    with pytest.raises(ValidationError, match="Member cannot be both a student and a teacher"):
        m.save()


def test_member_cannot_be_student_and_staff(create_user, create_groups):
    student_group, _ = create_groups
    user = create_user
    user.groups.add(student_group)
    user.is_staff = True
    user.save()
    m = Member.objects.get(username=user.username)
    with pytest.raises(ValidationError, match="Member cannot be both a student and a staff member"):
        m.save()


def test_member_can_be_staff_only(create_user):
    user = create_user
    m = Member.objects.get(username=user.username)
    m.is_staff = True
    m.save()  # No ValidationError expected
    assert not m.is_student
    assert not m.is_teacher
    assert m.is_staff
