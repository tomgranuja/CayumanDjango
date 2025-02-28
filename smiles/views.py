from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.http import Http404
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse_lazy as reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views import View

from cayuman.forms import StudentLoginForm
from smiles.decorators import enrollment_access_required
from smiles.decorators import membergroup_required
from smiles.decorators import student_required
from smiles.models import SubjectOffering
from smiles.models import Term
from smiles.services import EnrollmentService

# We'll need to create this form

# from .forms import SubjectSelectionForm


class StudentLoginView(LoginView):
    """Django Login View but with our custom form to control each message and label"""

    form_class = StudentLoginForm


@method_decorator(login_required, name="dispatch")
@method_decorator(student_required, name="dispatch")
@method_decorator(membergroup_required, name="dispatch")
@method_decorator(enrollment_access_required, name="dispatch")
class EnrollmentView(LoginRequiredMixin, View):
    """Enrollment form view, where students can choose their subjects"""

    login_url = reverse("login")
    redirect_field_name = "redirect_to"

    def get(self, request, term_id: int):
        """GET view for the enrollment form"""
        # Get the current term
        try:
            term = Term.objects.get(id=term_id)
        except Term.DoesNotExist:
            raise Http404("Term does not exist")

        # Get the member's current group assignment
        member_group_assignment = request.member.current_group_assignment

        if not member_group_assignment:
            messages.warning(request, _("Your student account is not associated with any Group. Please ask your teachers to fix this."))
            return HttpResponseRedirect(reverse("home"))

        # Get available subject offerings by time slot
        enrollment_service = EnrollmentService(member=request.member, term=term)
        offerings_by_timeslot = enrollment_service.get_available_offerings_by_timeslot()

        # Get current selections
        initial_data = {}
        current_offerings = member_group_assignment.subject_offerings_by_term(term)

        for timeslot, offering in current_offerings.items():
            initial_data[f"timeslot_{timeslot.id}"] = offering.id if offering else None

        # TODO: Create and use SubjectSelectionForm
        # form = SubjectSelectionForm(
        #     initial=initial_data,
        #     timeslots_with_offerings=offerings_by_timeslot,
        #     member=request.member
        # )

        # For now, we'll just render a placeholder
        return render(
            request,
            "smiles/enrollment.html",
            {
                "offerings_by_timeslot": offerings_by_timeslot,
                "term": term,
                # "form": form
            },
        )

    def post(self, request, term_id: int):
        """Save subject offerings for current member group assignment"""
        # Get the current term
        try:
            term = Term.objects.get(id=term_id)
        except Term.DoesNotExist:
            raise Http404("Term does not exist")

        # Get the member's current group assignment
        member_group_assignment = request.member.current_group_assignment

        if not member_group_assignment:
            messages.warning(request, _("Your student account is not associated with any Group. Please ask your teachers to fix this."))
            return HttpResponseRedirect(reverse("home"))

        # Get available subject offerings by time slot
        # enrollment_service = EnrollmentService(member=request.member, term=term)
        # offerings_by_timeslot = enrollment_service.get_available_offerings_by_timeslot()

        # Get current selections
        initial_data = {}
        current_offerings = member_group_assignment.subject_offerings_by_term(term)

        for timeslot, offering in current_offerings.items():
            initial_data[f"timeslot_{timeslot.id}"] = offering.id if offering else None

        # TODO: Create and use SubjectSelectionForm
        # form = SubjectSelectionForm(
        #     request.POST,
        #     initial=initial_data,
        #     timeslots_with_offerings=offerings_by_timeslot,
        #     member=request.member,
        #     term=term
        # )

        # For now, we'll just render a placeholder
        # if form.is_valid():
        #     # Form is valid, proceed with saving data
        #     subject_offering_ids = set()
        #     for timeslot in offerings_by_timeslot:
        #         field_name = f"timeslot_{timeslot.id}"
        #         offering = form.cleaned_data[field_name]
        #         if offering:
        #             subject_offering_ids.add(offering)
        #
        #     subject_offerings = list(SubjectOffering.objects.filter(id__in=subject_offering_ids))
        #
        #     # Associate subject offerings with member group assignment
        #     try:
        #         with transaction.atomic():
        #             # Get subject_offerings only in current term
        #             offerings_to_remove = member_group_assignment.subject_offerings.filter(term=term)
        #
        #             # Remove these subject offerings from the member_group_assignment
        #             member_group_assignment.subject_offerings.remove(*offerings_to_remove)
        #
        #             # Attempt to associate new subject offerings with member group assignment
        #             member_group_assignment.subject_offerings.add(*subject_offerings)
        #     except ValidationError as e:
        #         form.add_error(None, e)
        #
        #     if form.errors:
        #         return render(request, "smiles/enrollment.html", {"form": form})
        #     else:
        #         messages.success(request, _("Your subjects have been saved"))
        #         return HttpResponseRedirect(reverse("weekly_schedule", kwargs={"term_id": term.id}))
        # else:
        #     # Form is not valid, re-render the page with form errors
        #     return render(request, "smiles/enrollment.html", {"form": form})

        # For now, just redirect back to the enrollment page
        messages.info(request, _("This feature is not yet implemented"))
        return HttpResponseRedirect(reverse("enrollment", kwargs={"term_id": term.id}))


@login_required(login_url=reverse("login"))
@student_required
def home(request):
    """
    Home view

    - if member_group_assignment.is_schedule_full(request.term) - redirect to schedule view
    - else - redirect to subject offerings view
    """
    # Get the current term
    term = Term.objects.current()

    if not term:
        messages.warning(request, _("No active term found"))
        return render(request, "smiles/home.html")

    # Check if the member has a current group assignment
    if not hasattr(request.member, "current_group_assignment") or not request.member.current_group_assignment:
        messages.warning(request, _("Your student account is not associated with any Group. Please ask your teachers to fix this."))
        return render(request, "smiles/home.html")

    if request.member.current_group_assignment.is_schedule_full(term):
        return HttpResponseRedirect(reverse("weekly_schedule", kwargs={"term_id": term.id}))
    else:
        return HttpResponseRedirect(reverse("subject_offerings", kwargs={"term_id": term.id}))


@login_required(login_url=reverse("login"))
@student_required
@membergroup_required
def weekly_schedule(request, term_id: int):
    """Show users their weekly time table for the given term"""
    # Get the current term
    try:
        term = Term.objects.get(id=term_id)
    except Term.DoesNotExist:
        raise Http404("Term does not exist")

    # Get the member's current group assignment
    member_group_assignment = request.member.current_group_assignment

    if not member_group_assignment:
        messages.warning(request, _("Your student account is not associated with any Group. Please ask your teachers to fix this."))
        return HttpResponseRedirect(reverse("home"))

    # Get the subject offerings for this term
    subject_offerings = member_group_assignment.subject_offerings.filter(term=term)

    return render(
        request,
        "smiles/weekly_schedule.html",
        {"subject_offerings": subject_offerings, "term": term},
    )


@login_required(login_url=reverse("login"))
def subject_offering(request, subject_offering_id: int):
    """View detailed information about a subject offering"""
    try:
        offering = SubjectOffering.objects.get(id=subject_offering_id)
    except SubjectOffering.DoesNotExist:
        raise Http404
    return render(request, "smiles/subject_offering.html", {"offering": offering})


@login_required(login_url=reverse("login"))
@student_required
def subject_offerings(request, term_id: int):
    """View showing the list of all available subject offerings for the given logged in student"""
    # Get the current term
    try:
        term = Term.objects.get(id=term_id)
    except Term.DoesNotExist:
        raise Http404("Term does not exist")

    offerings = set()
    show_offerings = False  # By default do not show anything

    # Get the member's current group assignment
    member_group_assignment = request.member.current_group_assignment

    # Get all available subject offerings for this student and return
    if member_group_assignment:
        # Calculate show_offerings according if the term is current, or is in the past or member is enabled to enroll
        show_offerings = term.is_enabled_to_preview() or term.is_in_the_past()

        if show_offerings:
            # Get available offerings by time slot
            enrollment_service = EnrollmentService(member=request.member, term=term)
            offerings_by_timeslot = enrollment_service.get_available_offerings_by_timeslot()

            # Flatten the dictionary of time slots to offerings
            offerings = {offering for sublist in offerings_by_timeslot.values() for offering in sublist}
    else:
        messages.warning(request, _("Your student account is not associated with any Group. Please ask your teachers to fix this."))

    show_offerings = bool(offerings)  # coordinate flag var with the list of offerings

    return render(request, "smiles/subject_offerings.html", {"subject_offerings": offerings, "show_offerings": show_offerings, "term": term})
