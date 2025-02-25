from unittest.mock import Mock
from unittest.mock import patch

import pytest
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from django.urls import Resolver404

pytestmark = pytest.mark.django_db


def test_anonymous_user_gets_no_member(middleware, mock_request):
    """
    Test that anonymous users get request.member = None.
    This is important as many views check request.member to determine access.
    """
    middleware(mock_request)
    assert mock_request.member is None


def test_authenticated_user_gets_member(middleware, mock_request, create_student, create_period):
    """
    Test that authenticated users get their Member instance in request.member.
    This is crucial for the application as it's used throughout for permissions and access control.
    """
    mock_user = Mock(id=create_student.id, is_authenticated=True, is_active=True, is_impersonate=False)
    mock_request.user = mock_user

    middleware(mock_request)
    assert mock_request.member == create_student


def test_inactive_user_gets_no_member(middleware, mock_request, create_student):
    """
    Test that inactive users get request.member = None even if authenticated.
    This ensures inactive users can't access member-only features.
    """
    mock_user = Mock(id=create_student.id, is_authenticated=True, is_active=False, is_impersonate=False)
    mock_request.user = mock_user

    middleware(mock_request)
    assert mock_request.member is None


def test_admin_path_skips_period(middleware, mock_request):
    """
    Test that admin paths skip period handling.
    This is important as admin views don't need period context and shouldn't be affected by period restrictions.
    """
    mock_request.path_info = "/admin/some/path"
    middleware(mock_request)
    assert not hasattr(mock_request, "period")


def test_impersonate_path_skips_period(middleware, mock_request):
    """
    Test that impersonate paths skip period handling.
    This ensures impersonation views work independently of period context.
    """
    mock_request.path_info = "/impersonate/1"
    middleware(mock_request)
    assert not hasattr(mock_request, "period")


@patch("cayuman.middleware.resolve")
def test_period_from_url(mock_resolve, middleware, mock_request, create_period):
    """
    Test that period is extracted from URL when period_id is present.
    This is crucial for views that operate on specific periods.
    """
    mock_resolve.return_value.kwargs = {"period_id": create_period.id}
    middleware(mock_request)
    assert mock_request.period == create_period


@patch("cayuman.middleware.resolve")
def test_404_on_invalid_period(mock_resolve, middleware, mock_request):
    """
    Test that invalid period_id raises 404.
    This prevents accessing non-existent periods and ensures proper error handling.
    """
    mock_resolve.return_value.kwargs = {"period_id": 99999}
    with patch("cayuman.models.Period.objects.get", side_effect=ObjectDoesNotExist):
        with patch("cayuman.models.Period.objects.current_or_last", side_effect=Http404):
            with pytest.raises(Http404):
                middleware(mock_request)


@patch("cayuman.middleware.resolve")
def test_current_period_on_no_period_id(mock_resolve, middleware, mock_request, create_period):
    """
    Test that current period is used when no period_id in URL.
    This ensures views always have a period context even without explicit period_id.
    """
    mock_resolve.return_value.kwargs = {}
    middleware(mock_request)
    assert mock_request.period == create_period


@patch("cayuman.middleware.resolve")
def test_current_period_on_resolver404(mock_resolve, middleware, mock_request, create_period):
    """
    Test that current period is used when URL doesn't match any pattern.
    This provides fallback period context for non-standard URLs.
    """
    mock_resolve.side_effect = Resolver404()
    middleware(mock_request)
    assert mock_request.period == create_period


def test_impersonation_handling(middleware, mock_request, create_superuser, create_student, create_period):
    """
    Test proper handling of impersonation state.
    This ensures impersonation works correctly and all necessary attributes are set.
    """
    # Setup impersonation
    mock_user = Mock(id=create_student.id, is_authenticated=True, is_active=True, is_impersonate=True)
    mock_request.user = mock_user
    mock_request.impersonator = create_superuser

    middleware(mock_request)

    assert mock_request.member.is_impersonate is True
    assert mock_request.member.impersonator == create_superuser
    assert mock_request.impersonator == create_superuser


def test_failed_impersonation_cleanup(middleware, mock_request, create_student, create_period):
    """
    Test that failed impersonation attempts are properly cleaned up.
    This prevents incomplete/invalid impersonation state from affecting the request.
    """
    # Setup broken impersonation state
    mock_user = Mock(id=create_student.id, is_authenticated=True, is_active=True, is_impersonate=True)
    mock_request.user = mock_user
    mock_request.impersonator = None  # Simulate missing impersonator

    middleware(mock_request)

    assert mock_request.member.is_impersonate is False
    assert not hasattr(mock_request.member, "impersonator")
    assert mock_request.impersonator is None
