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


class EnrollmentService:
    """Service class for enrollment-related operations."""

    @staticmethod
    def get_available_offerings(member, term):
        """
        Get all subject offerings available for enrollment for a member in a term.

        Args:
            member (Member): The member to get available offerings for.
            term (Term): The term to get available offerings for.

        Returns:
            QuerySet: A queryset of SubjectOffering objects.
        """
        from smiles.models import SubjectOffering, MemberGroupAssignment

        # Get the member's groups
        member_groups = MemberGroupAssignment.objects.filter(member=member).values_list("group", flat=True)

        # Get subject offerings for the term that are eligible for the member's groups
        offerings = (
            SubjectOffering.objects.filter(term=term, eligible_groups__in=member_groups)
            .select_related("subject", "subject__type", "teacher", "term")
            .prefetch_related("eligible_groups", "enrolled_members")
            .distinct()
        )

        return offerings

    @staticmethod
    def can_enroll(member, subject_offering):
        """
        Check if a member can enroll in a subject offering.

        Args:
            member (Member): The member to check enrollment for.
            subject_offering (SubjectOffering): The subject offering to check enrollment for.

        Returns:
            tuple: A tuple of (bool, str) indicating if enrollment is possible and a reason if not.
        """
        from smiles.models import MemberGroupAssignment

        # Check if the subject offering is open for enrollment
        if not subject_offering.is_open_for_enrollment():
            return False, "Enrollment is not open for this subject offering."

        # Check if the member is in an eligible group
        member_groups = MemberGroupAssignment.objects.filter(member=member).values_list("group", flat=True)

        eligible_groups = subject_offering.eligible_groups.values_list("id", flat=True)

        if not set(member_groups).intersection(set(eligible_groups)):
            return False, "You are not in an eligible group for this subject offering."

        # Check if the subject offering has reached its maximum enrollment
        if subject_offering.max_students > 0 and subject_offering.count_students() >= subject_offering.max_students:
            return False, "This subject offering has reached its maximum enrollment."

        # Check if the member is already enrolled
        member_assignments = MemberGroupAssignment.objects.filter(member=member, group__in=subject_offering.eligible_groups.all())

        for assignment in member_assignments:
            if subject_offering in assignment.subject_offerings.all():
                return False, "You are already enrolled in this subject offering."

        return True, ""

    @staticmethod
    def enroll(member, subject_offering):
        """
        Enroll a member in a subject offering.

        Args:
            member (Member): The member to enroll.
            subject_offering (SubjectOffering): The subject offering to enroll in.

        Returns:
            bool: True if enrollment was successful, False otherwise.
        """
        from smiles.models import MemberGroupAssignment

        # Check if the member can enroll
        can_enroll, reason = EnrollmentService.can_enroll(member, subject_offering)

        if not can_enroll:
            return False

        # Get the member's assignments for eligible groups
        member_assignments = MemberGroupAssignment.objects.filter(member=member, group__in=subject_offering.eligible_groups.all())

        # Enroll the member in the first eligible assignment
        if member_assignments.exists():
            member_assignments.first().subject_offerings.add(subject_offering)
            return True

        return False

    @staticmethod
    def unenroll(member, subject_offering):
        """
        Unenroll a member from a subject offering.

        Args:
            member (Member): The member to unenroll.
            subject_offering (SubjectOffering): The subject offering to unenroll from.

        Returns:
            bool: True if unenrollment was successful, False otherwise.
        """
        from smiles.models import MemberGroupAssignment

        # Get the member's assignments for eligible groups
        member_assignments = MemberGroupAssignment.objects.filter(member=member, group__in=subject_offering.eligible_groups.all())

        # Unenroll the member from all assignments
        for assignment in member_assignments:
            assignment.subject_offerings.remove(subject_offering)

        return True
