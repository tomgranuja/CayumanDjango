import pytest
from django.contrib.auth.models import User, Group
from django.conf import settings
from cayuman.models import Member


@pytest.fixture(scope='function')
def create_user():
    """Fixture to create a basic user."""
    return User.objects.create_user(username='testuser', password='12345')


@pytest.fixture
def create_groups():
    """Fixture to create student and teacher groups."""
    students_group, _ = Group.objects.get_or_create(name=settings.STUDENTS_GROUP)
    teachers_group, _ = Group.objects.get_or_create(name=settings.TEACHERS_GROUP)
    return students_group, teachers_group


def test_member_can_be_student(create_user, create_groups):
    student_group, _ = create_groups
    user = create_user
    user.groups.add(student_group)
    m = Member(user=user)
    m.save()
    assert m.is_student
    assert not m.is_teacher


def test_member_can_be_teacher(create_user, create_groups):
    _, teacher_group = create_groups
    user = create_user
    user.groups.add(teacher_group)
    m = Member(user=user)
    m.save()
    assert m.is_teacher
    assert not m.is_student


def test_member_cannot_be_both_student_and_teacher(create_user, create_groups):
    student_group, teacher_group = create_groups
    user = create_user
    user.groups.add(student_group, teacher_group)
    m = Member(user=user)
    with pytest.raises(ValueError, match="Member cannot be both a student and a teacher"):
        m.save()


def test_member_cannot_be_student_and_staff(create_user, create_groups):
    student_group, _ = create_groups
    user = create_user
    user.groups.add(student_group)
    user.is_staff = True
    m = Member(user=user)
    with pytest.raises(ValueError, match="Member cannot be both a student and a staff member"):
        m.save()


def test_member_can_be_staff_only(create_user):
    user = create_user
    user.is_staff = True
    m = Member(user=user)
    m.save()  # No ValueError expected
    assert not m.is_student
    assert not m.is_teacher
    assert user.is_staff
