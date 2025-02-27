from datetime import datetime
from datetime import time
from typing import Optional
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from cayuman.models import Period


pytestmark = pytest.mark.django_db


def instantiate_period(
    name,
    preview_date: Optional[datetime] = None,
    enrollment_start: Optional[datetime] = None,
    enrollment_end: Optional[datetime] = None,
    date_start: Optional[datetime] = None,
    date_end: Optional[datetime] = None,
    create_entry: Optional[bool] = True,
):
    """Utility function to create a Period instance"""
    if not date_start:
        date_start = timezone.now()
    if not enrollment_start:
        # define enrollment_start by substracting 15 days to date_start
        enrollment_start = date_start - timezone.timedelta(days=15)
    if not preview_date:
        preview_date = enrollment_start
    if not enrollment_end:
        enrollment_end = enrollment_start + timezone.timedelta(days=7)
    if not date_end:
        date_end = date_start + timezone.timedelta(days=7 * 6)

    if isinstance(date_start, datetime):
        date_start = date_start.date()
    if isinstance(preview_date, datetime):
        preview_date = preview_date.date()
    if isinstance(enrollment_end, datetime):
        enrollment_end = enrollment_end.date()
    if isinstance(date_end, datetime):
        date_end = date_end.date()

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
    date_start = timezone.make_aware(datetime(2024, 5, 4))
    period = instantiate_period("Period 1", date_start=date_start)
    date_start = date_start.date()

    assert period.name == "Period 1"
    assert period.date_start == date_start
    assert period.date_end == date_start + timezone.timedelta(days=7 * 6)
    assert period.enrollment_start.date() == date_start - timezone.timedelta(days=15)
    assert period.enrollment_end == period.enrollment_start.date() + timezone.timedelta(days=7)
    assert period.preview_date == period.enrollment_start.date()


def test_implicit_dates():
    """Tests that enrollment_end and preview_date are filled as they are supposed to be implicitly"""
    date_start = timezone.make_aware(datetime(2024, 5, 4))
    p = Period.objects.create(
        name="Period X",
        enrollment_start=date_start - timezone.timedelta(days=10),
        date_start=date_start.date(),
        date_end=date_start.date() + timezone.timedelta(days=7 * 6),
    )

    assert p.enrollment_end == p.enrollment_start.date() + timezone.timedelta(days=5)
    assert p.preview_date == p.enrollment_start.date()


def test_period_create_invalid_():
    """Test various invalid ways to create periods"""
    # date_end < date_start
    date_start = timezone.make_aware(datetime(2024, 5, 4))
    date_end = timezone.make_aware(datetime(2024, 5, 2))
    with pytest.raises(ValidationError, match=r"must be before"):
        instantiate_period("Period 1", date_start=date_start, date_end=date_end)

    # preview_date > enrollment_start
    preview_date = timezone.make_aware(datetime(2024, 5, 5))
    enrollment_start = timezone.make_aware(datetime(2024, 5, 4))
    date_start = timezone.make_aware(datetime(2024, 5, 18))
    with pytest.raises(ValidationError, match=r"must be before"):
        instantiate_period("Period 1", date_start=date_start, enrollment_start=enrollment_start, preview_date=preview_date)

    # enrollment_end < enrollment_start
    enrollment_start = timezone.make_aware(datetime(2024, 5, 4))
    enrollment_end = timezone.make_aware(datetime(2024, 5, 2))
    date_start = timezone.make_aware(datetime(2024, 5, 18))
    with pytest.raises(ValidationError, match=r"must be before"):
        instantiate_period("Period 1", date_start=date_start, enrollment_start=enrollment_start, enrollment_end=enrollment_end)

    # date_start < enrollment_start
    date_start = timezone.make_aware(datetime(2024, 5, 2))
    enrollment_start = timezone.make_aware(datetime(2024, 5, 4))
    with pytest.raises(ValidationError, match=r"must be before"):
        instantiate_period("Period 1", date_start=date_start, enrollment_start=enrollment_start)

    # collision with another period
    date_start = timezone.make_aware(datetime(2024, 5, 4))
    instantiate_period("Period 1", date_start=date_start)

    date_start = timezone.make_aware(datetime(2024, 5, 18))
    with pytest.raises(ValidationError, match=r"colliding with another period"):
        instantiate_period("Period 2", date_start=date_start)


def test_period_instances_intersection():
    """Tests intersection between 2 schedules"""
    # This test does not create the period objects to be able to test intersection
    date_start_1 = timezone.make_aware(datetime(2024, 5, 4))
    period_1 = instantiate_period("Period 1", date_start=date_start_1, create_entry=False)

    date_start_2 = timezone.make_aware(datetime(2024, 5, 18))
    period_2 = instantiate_period("Period 2", date_start=date_start_2, create_entry=False)

    # there's intersection here
    assert period_1 & period_2


def test_period_empty_intersection():
    """Tests periods not intersecting"""
    date_start_1 = timezone.make_aware(datetime(2024, 5, 4))
    period_1 = instantiate_period("Period 1", date_start=date_start_1)

    date_start_2 = timezone.make_aware(datetime(2024, 6, 30))
    period_2 = instantiate_period("Period 2", date_start=date_start_2)

    # there's intersection here
    assert not period_1 & period_2


def test_current_period():
    """Tests logic for current period"""

    period_1 = instantiate_period(
        "Period 1",
        preview_date=timezone.make_aware(datetime(2024, 4, 17)),
        enrollment_start=timezone.make_aware(datetime(2024, 4, 19)),
        enrollment_end=timezone.make_aware(datetime(2024, 4, 26)),
        date_start=timezone.make_aware(datetime(2024, 5, 4)),
        date_end=timezone.make_aware(datetime(2024, 6, 15)),
    )
    # note that period 2 preview_date and enrollment date range fall within period 1 dates range
    # this is done just to be 100% sure current period logic is guided by [date_start, date_end]
    period_2 = instantiate_period(
        "Period 2",
        preview_date=timezone.make_aware(datetime(2024, 6, 10)),
        enrollment_start=timezone.make_aware(datetime(2024, 6, 10)),
        enrollment_end=timezone.make_aware(datetime(2024, 6, 16)),
        date_start=timezone.make_aware(datetime(2024, 6, 21)),
        date_end=timezone.make_aware(datetime(2024, 7, 30)),
    )

    # test date falling withing period 1 preview_date
    with patch("cayuman.models.timezone") as mock_datetime:
        mock_datetime.now.return_value = timezone.make_aware(datetime(2024, 4, 18))
        mock_datetime.now.date.return_value = timezone.make_aware(datetime(2024, 4, 18))
        assert Period.objects.current() is None
        assert period_1.is_current() is False
        assert period_2.is_current() is False
        assert period_1.is_enabled_to_preview() is True
        assert period_2.is_enabled_to_preview() is False

    # test date falling within period 1 enrollment range
    with patch("cayuman.models.timezone") as mock_datetime:
        mock_datetime.now.return_value = timezone.make_aware(datetime(2024, 4, 25))
        mock_datetime.now.date.return_value = timezone.make_aware(datetime(2024, 4, 25))
        assert Period.objects.current() is None

    # test date falling between period 1 date_start and enrollment_end
    with patch("cayuman.models.timezone") as mock_datetime:
        mock_datetime.now.return_value = timezone.make_aware(datetime(2024, 5, 3))
        mock_datetime.now.date.return_value = timezone.make_aware(datetime(2024, 5, 3))
        assert Period.objects.current() is None

    # test date before period 1 date_end but before period 2 enrollment_start
    with patch("cayuman.models.timezone") as mock_datetime:
        mock_datetime.now.return_value = timezone.make_aware(datetime(2024, 6, 9))
        mock_datetime.now.date.return_value = timezone.make_aware(datetime(2024, 6, 9))
        assert Period.objects.current() == period_1

    # test date between period 2 enrollment_start/preview_date and period 1 date_end
    with patch("cayuman.models.timezone") as mock_datetime:
        mock_datetime.now.return_value = timezone.make_aware(datetime(2024, 6, 14))
        mock_datetime.now.date.return_value = timezone.make_aware(datetime(2024, 6, 14))
        assert Period.objects.current() == period_1
        assert period_1.is_enabled_to_preview() is True
        assert period_2.is_enabled_to_preview() is True

    # test date between period 2 enrollment_end and date_start and after period 1 date_end
    with patch("cayuman.models.timezone") as mock_datetime:
        mock_datetime.now.return_value = timezone.make_aware(datetime(2024, 6, 17))
        mock_datetime.now.date.return_value = timezone.make_aware(datetime(2024, 6, 17))
        assert Period.objects.current() is None
        assert period_1.is_current() is False
        assert period_2.is_current() is False
        assert period_1.is_enabled_to_preview() is False
        assert period_2.is_enabled_to_preview() is True

    # test date after or equal to date_start
    with patch("cayuman.models.timezone") as mock_datetime:
        mock_datetime.now.return_value = timezone.make_aware(datetime(2024, 6, 21))
        mock_datetime.now.date.return_value = timezone.make_aware(datetime(2024, 6, 21))
        assert Period.objects.current() == period_2
        assert period_1.is_current() is False
        assert period_2.is_current() is True
        assert period_1.is_enabled_to_preview() is False
        assert period_2.is_enabled_to_preview() is True

    # test date far in the future
    with patch("cayuman.models.timezone") as mock_datetime:
        mock_datetime.now.return_value = timezone.make_aware(datetime(2024, 12, 17))
        mock_datetime.now.date.return_value = timezone.make_aware(datetime(2024, 12, 17))
        assert Period.objects.current() is None


def test_period_by_date_with_datetime(create_period):
    """Test period_by_date method with datetime objects"""
    period = create_period

    # Test with datetime object within period
    datetime_in_period = timezone.make_aware(datetime.combine(period.date_start + timezone.timedelta(days=1), time(12, 0)))
    assert Period.objects.period_by_date(datetime_in_period) == period

    # Test with datetime object before period
    datetime_before_period = timezone.make_aware(datetime.combine(period.date_start - timezone.timedelta(days=1), time(12, 0)))
    assert Period.objects.period_by_date(datetime_before_period) is None

    # Test with datetime object after period
    datetime_after_period = timezone.make_aware(datetime.combine(period.date_end + timezone.timedelta(days=1), time(12, 0)))
    assert Period.objects.period_by_date(datetime_after_period) is None

    # Test with date object (existing functionality)
    date_in_period = period.date_start + timezone.timedelta(days=1)
    assert Period.objects.period_by_date(date_in_period) == period
