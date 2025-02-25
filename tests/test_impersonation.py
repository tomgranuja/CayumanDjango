import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


class TestImpersonationAccess:
    """Test suite for impersonation access control"""

    def test_superuser_can_impersonate_through_admin(self, client_authenticated_superuser, create_student):
        """Test that superusers can impersonate students through admin interface"""
        # First access the admin page to get the impersonation link
        response = client_authenticated_superuser.get(reverse("admin:cayuman_member_changelist"))
        assert response.status_code == 200

        # Then try to impersonate
        response = client_authenticated_superuser.get(reverse("impersonate-start", args=[create_student.id]))
        assert response.status_code == 302  # Successful redirect
        assert "_impersonate" in client_authenticated_superuser.session
        assert client_authenticated_superuser.session["_impersonate"] == create_student.id
        assert response.url == "/"  # Should redirect to home first

        # Follow the home redirect
        response = client_authenticated_superuser.get(response.url)
        assert response.status_code == 302  # Should redirect to workshop periods
        assert response.url == reverse("workshop_periods", kwargs={"period_id": 1})

        # Follow the workshop-periods redirect and check we're impersonating
        response = client_authenticated_superuser.get(response.url)
        assert response.status_code == 200
        assert b"Impersonating" in response.content

    def test_staff_cannot_impersonate_through_admin(self, client_authenticated_staff, create_student):
        """Test that staff users cannot impersonate students through admin interface"""
        # First check that staff cannot access Member admin (should get 403)
        response = client_authenticated_staff.get(reverse("admin:cayuman_member_changelist"))
        assert response.status_code == 403  # Cannot access Member admin without proper permissions

        # Try to impersonate - should redirect to home
        response = client_authenticated_staff.get(reverse("impersonate-start", args=[create_student.id]))
        assert response.status_code == 302  # Redirected to home
        assert response.url == "/"  # Redirected to home

        # Check session to ensure we're not impersonating
        assert "_impersonate" not in client_authenticated_staff.session

    def test_teacher_cannot_access_admin_impersonation(self, client_authenticated_teacher, create_student):
        """Test that teachers cannot access admin to impersonate"""
        response = client_authenticated_teacher.get(reverse("admin:cayuman_member_changelist"))
        assert response.status_code == 302  # Redirected to login
        assert "_impersonate" not in client_authenticated_teacher.session

    def test_student_cannot_access_admin_impersonation(self, client_authenticated_student, create_teacher):
        """Test that students cannot access admin to impersonate"""
        response = client_authenticated_student.get(reverse("admin:cayuman_member_changelist"))
        assert response.status_code == 302  # Redirected to login
        assert "_impersonate" not in client_authenticated_student.session

    def test_cannot_impersonate_superuser_through_admin(self, client_authenticated_superuser, create_superuser):
        """Test that superusers cannot be impersonated through admin"""
        response = client_authenticated_superuser.get(reverse("impersonate-start", args=[create_superuser.id]))
        assert response.status_code == 302  # Redirected to home
        assert response.url == "/"  # Redirected to home
        assert "_impersonate" not in client_authenticated_superuser.session  # Should not be impersonating
