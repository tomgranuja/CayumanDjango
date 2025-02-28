from datetime import datetime
from functools import lru_cache

from django.utils import timezone

from .models import Term


class TermService:
    """
    Service class for Term-related operations.

    This class provides methods for retrieving terms based on various criteria,
    similar to the PeriodManager in the cayuman application.
    """

    @classmethod
    def current(cls):
        """
        Get the current term.

        A term is considered current if the current date falls between
        its start and end dates.

        Returns:
            Term: The current term, or None if no term is current
        """
        now = timezone.now()
        return cls.get_term_by_date(now.date())

    @classmethod
    def current_or_last(cls):
        """
        Get the current term, or the last term if no term is current.

        This method is guaranteed to return a term if any exist in the database.
        It's used to ensure there's always a "current" term for UI purposes.

        Returns:
            Term: The current or last term, or None if no terms exist
        """
        current = cls.current()
        if current:
            return current

        # Return the most recent term by end date
        return Term.objects.order_by("-date_end").first()

    @classmethod
    @lru_cache(maxsize=None)
    def get_term_by_date(cls, date_or_datetime):
        """
        Get the term that contains the given date.

        Args:
            date_or_datetime: The date to find a term for

        Returns:
            Term: The term containing the date, or None if no term contains it
        """
        if isinstance(date_or_datetime, datetime):
            date_obj = date_or_datetime.date()
        else:
            date_obj = date_or_datetime

        try:
            return Term.objects.get(date_start__lte=date_obj, date_end__gte=date_obj)
        except (Term.DoesNotExist, Term.MultipleObjectsReturned):
            return None

    @classmethod
    @lru_cache(maxsize=None)
    def other_terms(cls, term, order="id"):
        """
        Get all terms except the given one.

        Args:
            term: The term to exclude
            order: The field to order the results by

        Returns:
            QuerySet: All terms except the given one, ordered by the given field
        """
        return Term.objects.exclude(id=term.id).order_by(order)

    @classmethod
    def clear_caches(cls):
        """
        Clear all cached methods in this service.
        """
        cls.get_term_by_date.cache_clear()
        cls.other_terms.cache_clear()
