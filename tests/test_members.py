import pytest
from django.core.exceptions import ValidationError

pytestmark = pytest.mark.django_db


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
    with pytest.raises(ValidationError, match=r"must not be both"):
        user.groups.add(student_group, teacher_group)


def test_member_cannot_be_student_and_staff(create_user, create_groups):
    student_group, _ = create_groups
    user = create_user
    user.is_staff = True
    user.save()
    user.groups.clear()
    with pytest.raises(ValidationError, match=r"staff"):
        user.groups.add(student_group)


def test_member_can_be_staff_only(create_user):
    user = create_user
    user.is_staff = True
    user.save()  # No ValidationError expected
    assert not user.is_student
    assert not user.is_teacher
    assert user.is_staff
