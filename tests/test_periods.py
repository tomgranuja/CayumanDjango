from datetime import date
from typing import Optional
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from cayuman.models import Period


pytestmark = pytest.mark.django_db


def instantiate_period(
    name,
    preview_date: Optional[date] = None,
    enrollment_start: Optional[date] = None,
    enrollment_end: Optional[date] = None,
    date_start: Optional[date] = None,
    date_end: Optional[date] = None,
    create_entry: Optional[bool] = True,
):
    """Utility function to create a Period instance"""
    if not date_start:
        date_start = date.now()
    if not enrollment_start:
        # define enrollment_start by substracting 15 days to date_start
        enrollment_start = date_start - timezone.timedelta(days=15)
    if not preview_date:
        preview_date = enrollment_start
    if not enrollment_end:
        enrollment_end = enrollment_start + timezone.timedelta(days=7)
    if not date_end:
        date_end = date_start + timezone.timedelta(days=7 * 6)

    if create_entry:
        return Period.objects.create(
            name=name,
            enrollment_start=enrollment_start,
            enrollment_end=enrollment_end,
            date_start=date_start,
            date_end=date_end,
            preview_date=preview_date,
        )
    else:
        return Period(
            name=name,
            enrollment_start=enrollment_start,
            enrollment_end=enrollment_end,
            date_start=date_start,
            date_end=date_end,
            preview_date=preview_date,
        )


def test_period_create():
    """Tests correct Period creation"""
    date_start = date(2024, 5, 4)
    period = instantiate_period("Period 1", date_start=date_start)

    assert period.name == "Period 1"
    assert period.date_start == date_start
    assert period.date_end == date_start + timezone.timedelta(days=7 * 6)
    assert period.enrollment_start == date_start - timezone.timedelta(days=15)
    assert period.enrollment_end == period.enrollment_start + timezone.timedelta(days=7)
    assert period.preview_date == period.enrollment_start


def test_implicit_dates():
    """Tests that enrollment_end and preview_date are filled as they are supposed to be implicitly"""
    date_start = date(2024, 5, 4)
    p = Period.objects.create(
        name="Period X",
        enrollment_start=date_start - timezone.timedelta(days=10),
        date_start=date_start,
        date_end=date_start + timezone.timedelta(days=7 * 6),
    )

    assert p.enrollment_end == p.enrollment_start + timezone.timedelta(days=5)
    assert p.preview_date == p.enrollment_start


def test_period_create_invalid_():
    """Test various invalid ways to create periods"""
    # date_end < date_start
    date_start = date(2024, 5, 4)
    date_end = date(2024, 5, 2)
    with pytest.raises(ValidationError, match=r"must be before"):
        instantiate_period("Period 1", date_start=date_start, date_end=date_end)

    # preview_date > enrollment_start
    preview_date = date(2024, 5, 5)
    enrollment_start = date(2024, 5, 4)
    date_start = date(2024, 5, 18)
    with pytest.raises(ValidationError, match=r"must be before"):
        instantiate_period("Period 1", date_start=date_start, enrollment_start=enrollment_start, preview_date=preview_date)

    # enrollment_end < enrollment_start
    enrollment_start = date(2024, 5, 4)
    enrollment_end = date(2024, 5, 2)
    date_start = date(2024, 5, 18)
    with pytest.raises(ValidationError, match=r"must be before"):
        instantiate_period("Period 1", date_start=date_start, enrollment_start=enrollment_start, enrollment_end=enrollment_end)

    # date_start < enrollment_start
    date_start = date(2024, 5, 2)
    enrollment_start = date(2024, 5, 4)
    with pytest.raises(ValidationError, match=r"must be before"):
        instantiate_period("Period 1", date_start=date_start, enrollment_start=enrollment_start)

    # collision with another period
    date_start = date(2024, 5, 4)
    instantiate_period("Period 1", date_start=date_start)

    date_start = date(2024, 5, 18)
    with pytest.raises(ValidationError, match=r"colliding with another period"):
        instantiate_period("Period 2", date_start=date_start)


def test_period_instances_intersection():
    """Tests intersection between 2 schedules"""
    # This test does not create the period objects to be able to test intersection
    date_start_1 = date(2024, 5, 4)
    period_1 = instantiate_period("Period 1", date_start=date_start_1, create_entry=False)

    date_start_2 = date(2024, 5, 18)
    period_2 = instantiate_period("Period 2", date_start=date_start_2, create_entry=False)

    # there's intersection here
    assert period_1 & period_2


def test_period_empty_intersection():
    """Tests periods not intersecting"""
    date_start_1 = date(2024, 5, 4)
    period_1 = instantiate_period("Period 1", date_start=date_start_1)

    date_start_2 = date(2024, 6, 30)
    period_2 = instantiate_period("Period 2", date_start=date_start_2)

    # there's intersection here
    assert not period_1 & period_2


def test_current_period():
    """Tests logic for current period"""
    from datetime import datetime

    period_1 = instantiate_period(
        "Period 1",
        preview_date=date(2024, 4, 17),
        enrollment_start=date(2024, 4, 19),
        enrollment_end=date(2024, 4, 26),
        date_start=date(2024, 5, 4),
        date_end=date(2024, 6, 15),
    )
    # note that period 2 preview_date and enrollment date range fall within period 1 dates range
    # this is done just to be 100% sure current period logic is guided by [date_start, date_end]
    period_2 = instantiate_period(
        "Period 2",
        preview_date=date(2024, 6, 10),
        enrollment_start=date(2024, 6, 10),
        enrollment_end=date(2024, 6, 16),
        date_start=date(2024, 6, 21),
        date_end=date(2024, 7, 30),
    )

    # test date falling withing period 1 preview_date
    Period.objects.current.cache_clear()
    with patch("cayuman.models.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2024, 4, 18)
        mock_datetime.now.date.return_value = datetime(2024, 4, 18).date()
        assert Period.objects.current() == period_1
        assert period_1.is_current() is True
        assert period_2.is_current() is False
        assert period_1.can_be_previewed() is True
        assert period_2.can_be_previewed() is False

    # test date falling within period 1 enrollment range
    Period.objects.current.cache_clear()
    with patch("cayuman.models.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2024, 4, 25)
        mock_datetime.now.date.return_value = datetime(2024, 4, 25).date()
        assert Period.objects.current() == period_1

    # test date falling between period 1 date_start and enrollment_end
    Period.objects.current.cache_clear()
    with patch("cayuman.models.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2024, 5, 3)
        mock_datetime.now.date.return_value = datetime(2024, 5, 3).date()
        assert Period.objects.current() == period_1

    # test date before period 1 date_end but before period 2 enrollment_start
    Period.objects.current.cache_clear()
    with patch("cayuman.models.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2024, 6, 9)
        mock_datetime.now.date.return_value = datetime(2024, 6, 9).date()
        assert Period.objects.current() == period_1

    # test date between period 2 enrollment_start/preview_date and period 1 date_end
    Period.objects.current.cache_clear()
    with patch("cayuman.models.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2024, 6, 14)
        mock_datetime.now.date.return_value = datetime(2024, 6, 14).date()
        assert Period.objects.current() == period_1
        assert period_1.can_be_previewed() is True
        assert period_2.can_be_previewed() is True

    # test date between period 2 enrollment_end and date_start and after period 1 date_end
    Period.objects.current.cache_clear()
    with patch("cayuman.models.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2024, 6, 17)
        mock_datetime.now.date.return_value = datetime(2024, 6, 17).date()
        assert Period.objects.current() == period_2
        assert period_1.is_current() is False
        assert period_2.is_current() is True
        assert period_1.can_be_previewed() is False
        assert period_2.can_be_previewed() is True

    # test date far in the future
    Period.objects.current.cache_clear()
    with patch("cayuman.models.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2024, 12, 17)
        mock_datetime.now.date.return_value = datetime(2024, 12, 17).date()
        assert Period.objects.current() == period_2
