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
    if not enrollment_end:
        enrollment_end = enrollment_start + timezone.timedelta(days=7)
    if not date_end:
        date_end = date_start + timezone.timedelta(days=7 * 6)

    if create_entry:
        return Period.objects.create(
            name=name, enrollment_start=enrollment_start, enrollment_end=enrollment_end, date_start=date_start, date_end=date_end
        )
    else:
        return Period(name=name, enrollment_start=enrollment_start, enrollment_end=enrollment_end, date_start=date_start, date_end=date_end)


def test_period_create():
    """Tests correct Period creation"""
    date_start = date(2024, 5, 4)
    period = instantiate_period("Period 1", date_start=date_start)

    assert period.name == "Period 1"
    assert period.date_start == date_start
    assert period.date_end == date_start + timezone.timedelta(days=7 * 6)
    assert period.enrollment_start == date_start - timezone.timedelta(days=15)
    assert period.enrollment_end == period.enrollment_start + timezone.timedelta(days=7)


def test_period_create_invalid_():
    """Test various invalid ways to create periods"""
    # date_end < date_start
    date_start = date(2024, 5, 4)
    date_end = date(2024, 5, 2)
    with pytest.raises(ValidationError, match=r"must be before"):
        instantiate_period("Period 1", date_start=date_start, date_end=date_end)

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
    period_1 = instantiate_period("Period 1", date_start=date_start)
    print(period_1.date_end)

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
    # Period 1 from 2024-05-04 to 2024-06-15
    # enrollment dates
    # 2024-04-19
    # 2024-04-26
    # Period 2 from 2024-06-18 to 2024-07-30
    # enrollment dates
    # 2024-06-03
    # 2024-06-10
    from datetime import datetime

    period_1 = instantiate_period("Period 1", date_start=date(2024, 5, 4))
    period_2 = instantiate_period("Period 2", date_start=date(2024, 6, 18))

    # test date falling within period 1 enrollment
    Period.objects.current.cache_clear()
    with patch("cayuman.models.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2024, 4, 25)
        mock_datetime.now.date.return_value = datetime(2024, 4, 25).date()
        assert Period.objects.current() == period_1

    # test date falling between date_start and enrollment_end
    Period.objects.current.cache_clear()
    with patch("cayuman.models.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2024, 5, 3)
        mock_datetime.now.date.return_value = datetime(2024, 5, 3).date()
        assert Period.objects.current() == period_1

    # test date falling within date_start and date_end
    Period.objects.current.cache_clear()
    with patch("cayuman.models.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2024, 5, 5)
        mock_datetime.now.date.return_value = datetime(2024, 5, 5).date()
        assert Period.objects.current() == period_1

    # test date after between period 2 enrollment_start and period 1 date_end
    Period.objects.current.cache_clear()
    with patch("cayuman.models.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2024, 6, 8)
        mock_datetime.now.date.return_value = datetime(2024, 6, 8).date()
        assert Period.objects.current() == period_1

    # test date between period 2 enrollment_end and date_start
    Period.objects.current.cache_clear()
    with patch("cayuman.models.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2024, 6, 17)
        mock_datetime.now.date.return_value = datetime(2024, 6, 17).date()
        assert Period.objects.current() == period_2

    # test date far in the future
    Period.objects.current.cache_clear()
    with patch("cayuman.models.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2024, 12, 17)
        mock_datetime.now.date.return_value = datetime(2024, 12, 17).date()
        assert Period.objects.current() == period_2
