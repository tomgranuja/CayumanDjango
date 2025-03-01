from django.contrib import admin
from django.db import models as django_models
from django.http import HttpResponseRedirect
from django.urls import path
from django.urls import reverse_lazy as reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django_json_widget.widgets import JSONEditorWidget

from smiles.models import Activity
from smiles.models import ActivityType
from smiles.models import Attendance
from smiles.models import Event
from smiles.models import EventType
from smiles.models import Group
from smiles.models import MemberGroupAssignment
from smiles.models import MemberSchedule
from smiles.models import MemberScheduleOverride
from smiles.models import ScheduleAssignment
from smiles.models import ScheduleTemplate
from smiles.models import SpecialDay
from smiles.models import Subject
from smiles.models import SubjectOffering
from smiles.models import SubjectType
from smiles.models import Term
from smiles.models import TimeSlot


class TermAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "preview_date", "enrollment_start", "enrollment_end", "date_start", "date_end", "active")
    list_per_page = 20
    search_fields = ["name"]

    formfield_overrides = {
        django_models.JSONField: {"widget": JSONEditorWidget},
    }

    @admin.display(boolean=True, description=_("Active"))
    def active(self, obj):
        return obj.is_current()

    @admin.display(description=_("Preview date"))
    def preview_date(self, obj):
        preview_date = obj.get_preview_date()
        return format_html(str(preview_date.strftime("%B %d, %Y"))) if preview_date else "-"

    @admin.display(description=_("Enrollment start date and time"))
    def enrollment_start(self, obj):
        # Check for enrollment events first
        enrollment_events = obj.events.filter(type__name="Enrollment", is_active=True).order_by("date_start")
        if enrollment_events.exists():
            earliest_event = enrollment_events.first()
            if earliest_event.date_start:
                return format_html(str(earliest_event.date_start.strftime("%B %d, %Y")))

        # Fall back to enrollment periods in metadata
        enrollment_periods = obj.get_enrollment_periods()
        if enrollment_periods:
            first_period = enrollment_periods[0]
            start_date = first_period.get("start_date")
            if start_date:
                if isinstance(start_date, str):
                    import dateutil.parser

                    start_date = dateutil.parser.parse(start_date)
                return format_html(str(start_date.strftime("%B %d, %Y")))

        return "-"

    @admin.display(description=_("Enrollment end date"))
    def enrollment_end(self, obj):
        # Check for enrollment events first
        enrollment_events = obj.events.filter(type__name="Enrollment", is_active=True).order_by("-date_end")
        if enrollment_events.exists():
            latest_event = enrollment_events.first()
            if latest_event.date_end:
                return format_html(str(latest_event.date_end.strftime("%B %d, %Y")))

        # Fall back to enrollment periods in metadata
        enrollment_periods = obj.get_enrollment_periods()
        if enrollment_periods and enrollment_periods[-1]:
            last_period = enrollment_periods[-1]
            end_date = last_period.get("end_date")
            if end_date:
                if isinstance(end_date, str):
                    import dateutil.parser

                    end_date = dateutil.parser.parse(end_date)
                return format_html(str(end_date.strftime("%B %d, %Y")))

        return "-"

    def changelist_view(self, request, extra_context=None):
        # Check if the URL already has any filters set, else set term to the current one

        # if not request.GET and TermService.current_or_last():
        #    # Construct the URL for the filtered view
        #    current_term_id = TermService.current_or_last().id
        #     base_url = reverse("admin:%s_%s_changelist" % (self.model._meta.app_label, self.model._meta.model_name))
        #    query_string = f"id__exact={current_term_id}"
        #    return HttpResponseRedirect(f"{base_url}?{query_string}")

        # If the parameter is already there or there is no current term, just render the default view
        return super().changelist_view(request, extra_context)


class GroupAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "group_type", "description", "is_primary")
    list_per_page = 20
    search_fields = ["name", "group_type"]
    list_filter = ["group_type", "is_primary"]

    formfield_overrides = {
        django_models.JSONField: {"widget": JSONEditorWidget},
    }


class SubjectTypeAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "description", "is_selectable")
    list_per_page = 20
    search_fields = ["name"]
    list_filter = ["is_selectable"]

    formfield_overrides = {
        django_models.JSONField: {"widget": JSONEditorWidget},
    }


class SubjectAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "get_type", "description")
    list_per_page = 20
    search_fields = ["name", "type__name"]
    list_filter = ["type"]

    formfield_overrides = {
        django_models.JSONField: {"widget": JSONEditorWidget},
    }

    @admin.display(description=_("Type"))
    def get_type(self, obj):
        return obj.type.name if obj.type else "-"


class SubjectOfferingGroupsFilter(admin.SimpleListFilter):
    """Filter subject offerings by eligible group"""

    title = _("Group")
    parameter_name = "group"

    def lookups(self, request, model_admin):
        return list(Group.objects.values_list("id", "name"))

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(eligible_groups__id=self.value())
        return queryset


class SubjectOfferingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "subject",
        "teacher",
        "term",
        "groups_list",
        "num_students_html",
        "max_students_field",
        "active",
    )
    list_per_page = 20
    search_fields = ["subject__name", "teacher__first_name", "teacher__last_name"]
    list_filter = [
        ("term", admin.RelatedOnlyFieldListFilter),
        ("teacher", admin.RelatedOnlyFieldListFilter),
        SubjectOfferingGroupsFilter,
        "subject__type",
    ]
    filter_horizontal = ("eligible_groups",)

    formfield_overrides = {
        django_models.JSONField: {"widget": JSONEditorWidget},
    }

    def changelist_view(self, request, extra_context=None):
        # If no filters are set, redirect to current term
        if not request.GET and not request.session.get("admin_subject_offering_filter_set", False):
            from smiles.services import TermService

            current_term = TermService.current()
            if current_term:
                request.session["admin_subject_offering_filter_set"] = True
                return HttpResponseRedirect(f"{request.path}?term__id__exact={current_term.id}")
        return super().changelist_view(request, extra_context)

    @admin.display(boolean=True, description=_("Active"))
    def active(self, obj):
        return obj.term.is_current()

    @admin.display(description=_("Groups"))
    def groups_list(self, obj):
        return ", ".join([group.name for group in obj.eligible_groups.all()])

    @admin.display(description=_("Max Students"))
    def max_students_field(self, obj):
        return obj.max_students if obj.max_students > 0 else None

    @admin.display(description=_("Enrolled Students"))
    def num_students_html(self, obj):
        count = obj.count_students()
        if obj.max_students > 0 and count > obj.max_students:
            text = f"{count} ({_('overflow')})"
        else:
            text = f"{count}"
        return format_html(f'<a href="{reverse("admin:smiles_subjectoffering_enrolled_members", kwargs={"object_id": obj.id})}">{text}</a>')

    @admin.display(description=_("Enrolled Students"))
    def num_students(self, obj):
        return obj.count_students()

    def get_urls(self):
        """Add url for custom `enrolled_members` view"""
        from functools import update_wrapper

        def wrap(view):
            def wrapper(*args, **kwargs):
                return self.admin_site.admin_view(view)(*args, **kwargs)

            wrapper.model_admin = self
            return update_wrapper(wrapper, view)

        info = self.opts.app_label, self.opts.model_name
        urls = super().get_urls()
        new_urls = [
            path(
                "<path:object_id>/enrolled_members/",
                wrap(self.enrolled_members_view),
                name="%s_%s_enrolled_members" % info,  # smiles_subjectoffering_enrolled_members
            ),
        ]
        return new_urls + urls

    def enrolled_members_view(self, request, object_id, extra_context=None):
        """Admin view for enrolled members in a subject offering"""
        from django.contrib.admin.views.main import PAGE_VAR
        from django.contrib.admin.utils import unquote
        from django.core.exceptions import PermissionDenied
        from django.utils.text import capfirst
        from django.template.response import TemplateResponse

        # Check permissions
        model = self.model
        obj = self.get_object(request, unquote(object_id))
        if obj is None:
            return self._get_obj_does_not_exist_redirect(request, model._meta, object_id)

        if not self.has_view_or_change_permission(request, obj):
            raise PermissionDenied

        # Get enrolled members
        members_list = MemberGroupAssignment.objects.filter(subject_offerings=obj, member__is_active=True)

        paginator = self.get_paginator(request, members_list, 100)
        page_number = request.GET.get(PAGE_VAR, 1)
        page_obj = paginator.get_page(page_number)
        page_range = paginator.get_elided_page_range(page_obj.number)

        context = {
            **self.admin_site.each_context(request),
            "title": _("Enrolled Members: %s") % (obj),
            "subtitle": None,
            "members_list": page_obj,
            "page_range": page_range,
            "page_var": PAGE_VAR,
            "pagination_required": paginator.count > 100,
            "module_name": str(capfirst(self.opts.verbose_name_plural)),
            "object": obj,
            "opts": self.opts,
            "preserved_filters": self.get_preserved_filters(request),
            **(extra_context or {}),
        }

        request.current_app = self.admin_site.name

        return TemplateResponse(
            request,
            "admin/subject_offering_enrolled_members.html",
            context,
        )


class ActivityTypeAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "description", "is_selectable", "requires_attendance")
    list_per_page = 20
    search_fields = ["name", "description"]
    list_filter = ["is_selectable", "requires_attendance"]

    formfield_overrides = {
        django_models.JSONField: {"widget": JSONEditorWidget},
    }


class ActivityAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "type", "subject_offering", "description")
    list_per_page = 20
    search_fields = ["name", "description", "type__name"]
    list_filter = ["type", "subject_offering__term"]
    filter_horizontal = ("applicable_groups",)

    formfield_overrides = {
        django_models.JSONField: {"widget": JSONEditorWidget},
    }


class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "day_of_week", "time_start", "time_end")
    list_per_page = 20
    search_fields = ["name"]
    list_filter = ["day_of_week"]

    formfield_overrides = {
        django_models.JSONField: {"widget": JSONEditorWidget},
    }


class ScheduleTemplateAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "description")
    list_per_page = 20
    search_fields = ["name", "description"]
    filter_horizontal = ("applicable_groups", "applicable_terms")

    formfield_overrides = {
        django_models.JSONField: {"widget": JSONEditorWidget},
    }


class ScheduleAssignmentAdmin(admin.ModelAdmin):
    list_display = ("id", "template", "time_slot", "activity")
    list_per_page = 20
    search_fields = ["template__name", "activity__name"]
    list_filter = ["template", "time_slot__day_of_week"]

    formfield_overrides = {
        django_models.JSONField: {"widget": JSONEditorWidget},
    }


class MemberScheduleAdmin(admin.ModelAdmin):
    list_display = ("id", "member", "term", "template", "is_custom")
    list_per_page = 20
    search_fields = ["member__username", "member__first_name", "member__last_name", "template__name"]
    list_filter = ["term", "is_custom"]

    formfield_overrides = {
        django_models.JSONField: {"widget": JSONEditorWidget},
    }


class MemberScheduleOverrideAdmin(admin.ModelAdmin):
    list_display = ("id", "member_schedule", "date", "time_slot", "activity", "reason")
    list_per_page = 20
    search_fields = ["member_schedule__member__username", "reason", "activity__name"]
    list_filter = ["date", "time_slot__day_of_week"]

    formfield_overrides = {
        django_models.JSONField: {"widget": JSONEditorWidget},
    }


class SpecialDayAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "date", "is_school_closed", "alternate_schedule")
    list_per_page = 20
    search_fields = ["name"]
    list_filter = ["date", "is_school_closed"]
    filter_horizontal = ("affects_groups",)

    formfield_overrides = {
        django_models.JSONField: {"widget": JSONEditorWidget},
    }


class AttendanceAdmin(admin.ModelAdmin):
    list_display = ("id", "member", "date", "time_slot", "activity", "attended", "recorded_by")
    list_per_page = 20
    search_fields = ["member__username", "member__first_name", "member__last_name", "activity__name"]
    list_filter = ["date", "attended", "time_slot__day_of_week"]

    formfield_overrides = {
        django_models.JSONField: {"widget": JSONEditorWidget},
    }


class EventTypeAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "description")
    list_per_page = 20
    search_fields = ["name", "description"]

    formfield_overrides = {
        django_models.JSONField: {"widget": JSONEditorWidget},
    }


class EventAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "type", "term", "preview_date", "date_start", "date_end", "is_active")
    list_per_page = 20
    search_fields = ["name", "type__name"]
    list_filter = ["type", "term", "is_active"]
    filter_horizontal = ("affects_groups", "affects_subjects")

    formfield_overrides = {
        django_models.JSONField: {"widget": JSONEditorWidget},
    }


class MemberGroupAssignmentAdmin(admin.ModelAdmin):
    list_display = ("id", "member", "group", "date_assigned", "is_active")
    list_per_page = 20
    search_fields = ["member__username", "member__first_name", "member__last_name", "group__name"]
    list_filter = ["group", "is_active"]
    filter_horizontal = ("subject_offerings",)

    formfield_overrides = {
        django_models.JSONField: {"widget": JSONEditorWidget},
    }


# Register with custom admin classes
admin.site.register(Term, TermAdmin)
admin.site.register(Group, GroupAdmin)
admin.site.register(SubjectType, SubjectTypeAdmin)
admin.site.register(Subject, SubjectAdmin)
admin.site.register(SubjectOffering, SubjectOfferingAdmin)
admin.site.register(ActivityType, ActivityTypeAdmin)
admin.site.register(Activity, ActivityAdmin)
admin.site.register(TimeSlot, TimeSlotAdmin)
admin.site.register(ScheduleTemplate, ScheduleTemplateAdmin)
admin.site.register(ScheduleAssignment, ScheduleAssignmentAdmin)
admin.site.register(MemberSchedule, MemberScheduleAdmin)
admin.site.register(MemberScheduleOverride, MemberScheduleOverrideAdmin)
admin.site.register(SpecialDay, SpecialDayAdmin)
admin.site.register(Attendance, AttendanceAdmin)
admin.site.register(EventType, EventTypeAdmin)
admin.site.register(Event, EventAdmin)
admin.site.register(MemberGroupAssignment, MemberGroupAssignmentAdmin)
# Register other models as needed
